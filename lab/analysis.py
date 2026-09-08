"""Fold measured runs into OP-03 evidence artifacts.

Reads ``results/runs/*`` (worker output: ledger.jsonl, runs.jsonl, details.jsonl,
run.json) plus the shipped baseline (``results/baseline-ho``) and emits:

    results/final/manifest.json   run_id -> config + provenance
    results/final/pareto.jsonl    operating points (official pareto_schema.json)
    results/final/report.md       gates, ablations, decompositions, family view

Metrics are computed the way the official reader does: cost comes only from the
ledger, quality is exact goal-state match, and cost-per-resolved-case divides by
*resolved* (deferred/failed stay in the numerator).  A separate consistency
check runs the vendored ``ledger_reader.py`` over each run's ledger+runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"
BASELINE_DIR = ROOT / "results" / "baseline-ho"
OUT = ROOT / "results" / "final"
CASES = ROOT / "vendor" / "challenge" / "cases.jsonl"
READER = ROOT / "vendor" / "challenge" / "ledger_reader.py"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_case_defs() -> dict[str, dict]:
    return {c["case_id"]: c for c in
            (json.loads(l) for l in CASES.read_text().splitlines() if l.strip())}


def summary_of(directory: Path) -> dict:
    details = [json.loads(l) for l in (directory / "details.jsonl").read_text().splitlines() if l.strip()]
    runs = [json.loads(l) for l in (directory / "runs.jsonl").read_text().splitlines() if l.strip()]
    meta = json.loads((directory / "run.json").read_text())
    n = len(details)
    return {"directory": directory, "details": details, "runs": runs, "meta": meta, "n": n}


def compute(directory: Path, defs: dict[str, dict]) -> dict:
    d = summary_of(directory)
    details, runs = d["details"], d["runs"]
    n = d["n"]
    case_ids = [r["case_id"] for r in runs]
    required_ids = {cid for cid in case_ids
                    if "escalate" in defs[cid]["goal_state"].get("audit_must_include", [])}
    eligible = len(case_ids) - len(required_ids)

    matched = sum(r["goal_state_match"] for r in details)
    deferred = [r for r in details if r["deferred"]]
    elective = [r for r in deferred if r["case_id"] not in required_ids]
    violations = sum(1 for r in details if r["policy_violations"])

    total_cost = sum(json.loads(l)["cost_usd"]
                     for l in (directory / "ledger.jsonl").read_text().splitlines() if l.strip())
    resolved = sum(r["goal_state_match"] and not r["deferred"] for r in details)
    lat = sorted(float(r["latency_s"]) for r in runs)
    p95 = lat[max(0, int(0.95 * (len(lat) - 1)))] if lat else None

    # decompositions from the ledger
    cost_by_model: dict[str, float] = defaultdict(float)
    cost_by_family: dict[str, float] = defaultdict(float)
    fam_of = {c["case_id"]: c["family"] for c in defs.values()}
    for line in (directory / "ledger.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cost_by_model[row["model"]] += row["cost_usd"]
        cost_by_family[fam_of.get(row["case_id"], "?")] += row["cost_usd"]

    quality_by_family = {}
    for r in details:
        f = r["family"]
        b = quality_by_family.setdefault(f, [0, 0])
        b[0] += 1
        b[1] += 1 if r["goal_state_match"] else 0

    return {
        "run_id": d["meta"]["tag"] or directory.name,
        "label": directory.name,
        "config": d["meta"],
        "n": len(details),
        "quality": round(matched / n, 4),
        "resolved": resolved,
        "deferred": len(deferred),
        "required_escalations": len(required_ids),
        "elective_deferrals": len(elective),
        "elective_deferral_rate": round(len(elective) / eligible, 4) if eligible else None,
        "deferral_rate": round(len(deferred) / n, 4),
        "policy_violations": violations,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_resolved_case": round(total_cost / resolved, 6) if resolved else None,
        "latency_p95_s": round(p95, 3) if p95 is not None else None,
        "cost_by_model": {k: round(v, 6) for k, v in cost_by_model.items()},
        "cost_by_family": {k: round(v, 6) for k, v in cost_by_family.items()},
        "quality_by_family": {k: (round(v[1] / v[0], 3), v[1], v[0])
                              for k, v in quality_by_family.items()},
    }


def consistency_check(directory: Path, defs_path: Path) -> dict | None:
    """Run the official ledger_reader; return its report if it accepts the files."""
    try:
        proc = subprocess.run(
            [sys.executable, str(READER), "--ledger", str(directory / "ledger.jsonl"),
             "--runs", str(directory / "runs.jsonl"), "--cases", str(defs_path)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return {"error": proc.stderr[:400]}
        return json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

ORDER = [
    ("shipped-baseline", "shipped agent, gpt-4.1-mini class (reference)", False,
     "Frozen starter reference: unmodified Harbour, single mini model, full prompt."),
    ("shipped-prefixcache", "shipped + free prefix cache", False,
     "Reference agent but every unchanged conversation head is served from the "
     "free self-hosted prompt-prefix cache."),
    ("sol-noprune-mini", "solution no-op, mini", False,
     "Solution copy with no levers enabled (equivalence check)."),
    ("prune-mini", "schema prune, mini", False,
     "Per-family tool-schema pruning (smaller system prompt on every call)."),
    ("prune-nano", "schema prune, nano", False,
     "Prune + downgrade to the cheapest budget tier."),
    ("nano-noprune", "nano, full prompt", False,
     "Downgrade to nano only (no pruning)."),
    ("ladder-ns-prune", "nano->strong ladder + prune", False,
     "Prune + start on nano, escalate failed attempts to strong."),
    ("prune-nano-pc", "schema prune, nano + prefix cache", False,
     "Prune + nano + free prefix cache (bills only the new suffix per call)."),
    ("prune-mini-pc-verify", "prune, mini->strong + verify + prefix cache", False,
     "Mini with a strong grounded verification pass before commit (redo on "
     "detected flaws), prefix-cached."),
    ("prune-nano-ladderNS-verify-pc", "nano->strong + grounded verify + prefix cache", False,
     "Nano on attempt 0, strong on retry, strong grounded verification before "
     "commit, free prefix cache - the cheap quality play."),
    ("prune-nano-ladderNS-verify", "nano->strong + verify, NO prefix cache", True,
     "Same as above without prefix caching - verify re-reads the whole "
     "transcript each time (rejected: verification only pays with caching)."),
    ("prune-strong", "schema prune, strong", False,
     "Prune + upgrade to the strongest budget tier (quality push)."),
    ("prune-strong-pc", "schema prune, strong + prefix cache", False,
     "Strong tier with the free prefix cache (quality + cheaper retries)."),
    ("strong-noprune", "strong, full prompt", False,
     "Upgrade to strong only (quality ceiling probe)."),
]


def main() -> int:
    defs = load_case_defs()
    OUT.mkdir(parents=True, exist_ok=True)
    runs_dir = BASELINE_DIR if not RUNS.exists() else RUNS
    names = [name for name, *_ in ORDER]
    metrics = {}
    reader_reports = {}
    for name in names:
        directory = BASELINE_DIR if name == "shipped-baseline" else RUNS / name
        if not (directory / "details.jsonl").exists():
            print(f"missing run: {name}", file=sys.stderr)
            continue
        metrics[name] = compute(directory, defs)
        metrics[name]["reader"] = consistency_check(directory, CASES)

    # pareto.jsonl in the official schema
    pareto = []
    for name, label, rejected, what_changed in ORDER:
        if name not in metrics:
            continue
        m = metrics[name]
        pareto.append({
            "run_id": name,
            "label": label,
            "cost_per_resolved_case": m["cost_per_resolved_case"],
            "quality": m["quality"],
            "latency_p95_s": m["latency_p95_s"],
            "deferral_rate": m["deferral_rate"],
            "elective_deferral_rate": m["elective_deferral_rate"],
            "policy_violations": m["policy_violations"],
            "what_changed": what_changed,
            "rejected": rejected,
        })
    with (OUT / "pareto.jsonl").open("w", encoding="utf-8") as fh:
        for row in pareto:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {name: {
        "label": label,
        "config": metrics[name]["config"],
        "reader_ok": metrics[name]["reader"].get("error") is None,
    } for name, label, rejected, what in ORDER if name in metrics}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # gates report
    base = metrics["shipped-baseline"]
    floor = max(0.853, base["quality"] - 0.03)
    cost_bar = 0.1 * base["cost_per_resolved_case"]
    lines = [
        "# OP-03 gates report (local 60-case holdout)",
        "",
        f"Reference (shipped mini): quality {base['quality']:.3f} ({base['quality']*60:.0f}/60), "
        f"cost/resolved ${base['cost_per_resolved_case']:.6f}, p95 {base['latency_p95_s']}s.",
        f"Quality floor: {floor:.3f} (=52/60). Cost bar: 0.10x = ${cost_bar:.6f}/resolved.",
        "",
        "| run | quality | cost/res | 0.1x? | floor? | p95<=ref | elect.defer<=10% | viol<=ref |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in pareto:
        q_ok = row["quality"] >= floor
        c_ok = row["cost_per_resolved_case"] is not None and row["cost_per_resolved_case"] <= cost_bar
        l_ok = row["latency_p95_s"] <= base["latency_p95_s"]
        e_ok = (row["elective_deferral_rate"] or 0) <= 0.10
        v_ok = row["policy_violations"] <= base["policy_violations"]
        lines.append(
            f"| {row['run_id']} | {row['quality']:.3f} | "
            f"${row['cost_per_resolved_case']:.6f} | {'Y' if c_ok else 'N'} | "
            f"{'Y' if q_ok else 'N'} | {'Y' if l_ok else 'N'} | {'Y' if e_ok else 'N'} | "
            f"{'Y' if v_ok else 'N'} |"
        )
    lines += [
        "",
        "## Ablations (each lever alone vs shipped baseline, holdout)",
        "",
        "| lever | quality | cost/res | vs baseline cost/res |",
        "|---|---|---|---|",
    ]
    for name, label, *_ in ORDER:
        if name in ("shipped-baseline", "sol-noprune-mini"):
            continue
        m = metrics[name]
        ratio = m["cost_per_resolved_case"] / base["cost_per_resolved_case"]
        lines.append(f"| {label} | {m['quality']:.3f} | ${m['cost_per_resolved_case']:.6f} | {ratio:.2f}x |")
    lines += [
        "",
        "## Cost decomposition by model (selected runs, ledger USD)",
        "",
    ]
    for name in ("shipped-baseline", "prune-mini", "prune-nano", "prune-strong", "ladder-ns-prune"):
        m = metrics[name]
        lines.append(f"- {name}: {m['cost_by_model']}")
    lines += ["", "## Quality by family (prune-strong, matches/total)", ""]
    m = metrics["prune-strong"]
    for fam in sorted(m["quality_by_family"]):
        rate, ok_, tot = m["quality_by_family"][fam]
        lines.append(f"- {fam}: {rate:.2f} ({ok_}/{tot})")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for name in ("shipped-baseline", "prune-nano", "prune-strong"):
        r = metrics[name]["reader"]
        if "error" in r:
            print(f"reader rejected {name}: {r['error']}")
        else:
            print(f"reader OK {name}: success={r['success_rate']} cpr=${r['cost_per_resolved_case']} "
                  f"elective={r['elective_deferral_rate']}")
    print(f"wrote {OUT / 'pareto.jsonl'}, manifest.json, report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
