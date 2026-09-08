"""One measured run of Harbour over a set of cases through the lab gateway.

This is the lab's equivalent of the OP-03 assessment run: for every case a fresh
in-memory seeded Backend is created, the real ``agent.run_case`` drives the case
through the gateway, and the resulting DB + audit trail is scored by the
official ``goal_scorer``.  Cost is read only from the gateway ledger; the agent
never reports its own spend.

    python -m lab.worker --cases lab/splits/holdout.jsonl --model mini \\
        --harbour-dir vendor/challenge --run-dir results/run-001 \\
        --seed op03-lab-v1 [--limit 10] [--tag baseline-mini]

Writes under <run-dir>: ledger.jsonl (gateway), runs.jsonl, details.jsonl,
run.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lab.gateway import SimGateway, make_server  # noqa: E402


def run_one_case(agent, gw: SimGateway, case: dict, seed_path: str) -> dict:
    from harbour import backend as B
    from harbour import seed_data
    import goal_scorer

    cid = case["case_id"]
    backend = B.Backend(":memory:")
    seed_data.load_seed(backend.conn, seed_path)
    os.environ["LLM_EXTRA_HEADERS"] = json.dumps({"X-Harbour-Case-Id": cid})
    try:
        t0 = time.time()
        agent.run_case(
            backend,
            cid,
            case["customer_id"],
            case["message"],
            loan_id=case.get("loan_id"),
        )
        wall_ms = (time.time() - t0) * 1000.0
        trail = backend.audit_trail(cid)
        attempted = {row["tool"] for row in trail}
        succeeded = {
            row["tool"]
            for row in trail
            if row["ok"] == 1
        }
        score = goal_scorer.score(backend.conn, case)
        ledger = gw.totals_for(cid)

        if os.environ.get("LAB_DEBUG") and not score["goal_state_match"]:
            print(f"  [debug] {cid} {case['family']} failed")
            for row in trail:
                err = row["error"] or ""
                print(f"    {row['tool']:20s} ok={row['ok']} {err[:160]}")
            print(f"    failures: {score['failures']}")
            for tbl, where in (("payments", "status='scheduled' ORDER BY payment_id DESC"),
                               ("disputes", "status='open' ORDER BY dispute_id DESC"),
                               ("documents", "status='requested' ORDER BY document_id DESC"),
                               ("customers", "1=1")):
                rows = backend.conn.execute(
                    f"SELECT * FROM {tbl} WHERE {where}").fetchall()[:6]
                if rows:
                    print(f"    {tbl}:")
                    for r in rows:
                        print(f"      {dict(r)}")

        required = "escalate" in case["goal_state"].get("audit_must_include", [])
        escalated = "escalate" in attempted
        committed = "commit" in succeeded
        matched = score["goal_state_match"]
        deferred = bool(escalated and not (required and matched and committed))
        violations = sorted(set(case["goal_state"].get("audit_must_not_include", [])) & attempted)

        return {
            "case_id": cid,
            "family": case["family"],
            "difficulty": case["difficulty"],
            "goal_state_match": matched,
            "deferred": deferred,
            "committed": committed,
            "escalated": escalated,
            "policy_required_escalation": required,
            "policy_violations": violations,
            "latency_s": round(ledger["latency_ms"] / 1000.0, 3),
            "wall_ms": round(wall_ms, 1),
            "calls": int(ledger["calls"]),
            "input_tokens": int(ledger["input_tokens"]),
            "output_tokens": int(ledger["output_tokens"]),
            "spend_usd": round(ledger["cost_usd"], 9),
            "failures": score["failures"],
            "attempted_tools": sorted(attempted),
        }
    finally:
        backend.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, required=True, help="case JSONL subset to run")
    ap.add_argument("--model", default="mini")
    ap.add_argument("--harbour-dir", type=Path, default=ROOT / "vendor" / "challenge")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--seed", default="op03-lab-v1")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--defs", type=Path, default=ROOT / "vendor" / "challenge" / "cases.jsonl")
    ap.add_argument("--seed-data", type=Path,
                    default=ROOT / "vendor" / "challenge" / "harbour" / "seed.json")
    ap.add_argument("--p-override", type=float, default=None,
                    help="force the plan-correctness probability (debug/calibration only)")
    ap.add_argument("--ladder", default=None,
                    help="attempt ladder, e.g. 'nano,strong' (requires the solution harbour)")
    ap.add_argument("--prune", action="store_true",
                    help="advertise only the tools this case needs (system-prompt pruning)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--prefix-cache", action="store_true",
                    help="free self-hosted prompt-prefix cache (bills only the new suffix)")
    ap.add_argument("--compact", action="store_true",
                    help="structured compaction: projected read results + compact retry context")
    ap.add_argument("--verify", action="store_true",
                    help="grounded verification pass before commit (solution harbour)")
    ap.add_argument("--verify-model", default="strong")
    ap.add_argument("--verify-scope", default="all", choices=("all", "first"))
    ap.add_argument("--verify-max", default="2")
    args = ap.parse_args(argv)

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    # -- make the chosen Harbour importable (baseline or solution copy) ------
    # args.harbour_dir holds a `harbour` package (pristine or solution copy);
    # inserting it at the front of sys.path selects which one we run.
    sys.path.insert(0, str(args.harbour_dir))
    if str(args.defs.parent) not in sys.path:
        sys.path.append(str(args.defs.parent))
    import harbour  # noqa: PLC0415
    from harbour import agent  # noqa: PLC0415

    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    gw = SimGateway(args.defs, run_dir / "ledger.jsonl", args.seed,
                    cache=not args.no_cache, prefix_cache=args.prefix_cache)
    server = make_server(gw)
    thread = None
    import threading
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}/v1"
    os.environ.update(
        {
            "LLM_BASE_URL": base,
            "LLM_API_KEY": "lab-key",
            "LLM_MODEL": args.model,
            "LLM_FAKE": "",
            "LLM_TIMEOUT": "30",
            "LLM_MAX_RETRIES": "2",
            "HARBOUR_TRACE_FILE": str(run_dir / "traces.jsonl"),
            "HARBOUR_POLICY_FILE": str(args.harbour_dir / "harbour" / "policy.md"),
        }
    )
    if args.p_override is not None:
        os.environ["LLM_LAB_P_OVERRIDE"] = str(args.p_override)
    if args.ladder:
        os.environ["H_AGENT_LADDER"] = args.ladder
    if args.prune:
        os.environ["H_AGENT_PRUNE"] = "1"
    if args.compact:
        os.environ["H_AGENT_COMPACT"] = "1"
    if args.verify:
        os.environ["H_AGENT_VERIFY"] = "grounded"
        os.environ["H_AGENT_VERIFY_MODEL"] = args.verify_model
        os.environ["H_AGENT_VERIFY_MAX"] = args.verify_max
        os.environ["H_AGENT_VERIFY_SCOPE"] = args.verify_scope

    outcomes = []
    started = time.time()
    for i, case in enumerate(cases, 1):
        rec = run_one_case(agent, gw, case, str(args.seed_data))
        outcomes.append(rec)
        if (i % 25 == 0 or i == len(cases)) and not args.quiet:
            print(f"  {i}/{len(cases)} cases ...", flush=True)
    server.shutdown()

    outcomes.sort(key=lambda r: r["case_id"])
    with (run_dir / "runs.jsonl").open("w", encoding="utf-8") as fh:
        for r in outcomes:
            fh.write(json.dumps({
                "case_id": r["case_id"],
                "goal_state_match": r["goal_state_match"],
                "deferred": r["deferred"],
                "latency_s": r["latency_s"],
            }, ensure_ascii=False) + "\n")
    with (run_dir / "details.jsonl").open("w", encoding="utf-8") as fh:
        for r in outcomes:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {
        "model": args.model,
        "tag": args.tag,
        "cases_file": str(args.cases),
        "harbour_dir": str(args.harbour_dir),
        "seed": args.seed,
        "cache": not args.no_cache,
        "ladder": args.ladder,
        "prune": args.prune,
        "prefix_cache": args.prefix_cache,
        "verify": args.verify,
        "verify_model": args.verify_model if args.verify else None,
        "verify_scope": args.verify_scope if args.verify else None,
        "compact": args.compact,
        "n": len(outcomes),
        "wall_s": round(time.time() - started, 1),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    n = len(outcomes)
    resolved = sum(r["goal_state_match"] and not r["deferred"] for r in outcomes)
    quality = sum(r["goal_state_match"] for r in outcomes) / n
    deferred = sum(r["deferred"] for r in outcomes)
    total_cost = sum(r["spend_usd"] for r in outcomes)
    print(json.dumps({
        "n": n,
        "quality": round(quality, 4),
        "resolved": resolved,
        "deferred": deferred,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_resolved_case": round(total_cost / resolved, 6) if resolved else None,
        "wall_s": meta["wall_s"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
