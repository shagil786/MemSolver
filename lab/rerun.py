"""Reproduce every measured run from its recorded run.json config.

Each run directory in results/ (runs/*, baseline-ho, baseline-dev) already
stores the exact command config in run.json (model, harbour dir, levers).
This re-runs them all so a semantics change (or gateway/agent change) can be
propagated to every operating point deterministically:

    python3 -m lab.rerun [--only prune-nano-pc]

    python3 -m lab.rerun  (re-runs baseline-dev, baseline-ho and results/runs/*)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"
BASELINES = (ROOT / "results" / "baseline-dev", ROOT / "results" / "baseline-ho")


def rebuild_args(run_dir: Path) -> list[str]:
    meta = json.loads((run_dir / "run.json").read_text())
    args = [
        sys.executable, "-m", "lab.worker",
        "--cases", str(meta["cases_file"]),
        "--model", meta["model"],
        "--harbour-dir", str(meta["harbour_dir"]),
        "--run-dir", str(run_dir),
        "--seed", meta["seed"],
        "--tag", meta["tag"],
        "--quiet",
    ]
    if not meta.get("cache", True):
        args.append("--no-cache")
    if meta.get("ladder"):
        args += ["--ladder", meta["ladder"]]
    if meta.get("prune"):
        args.append("--prune")
    if meta.get("prefix_cache"):
        args.append("--prefix-cache")
    if meta.get("compact"):
        args.append("--compact")
    if meta.get("verify"):
        args += ["--verify", "--verify-model", meta.get("verify_model", "strong")]
        if meta.get("verify_scope"):
            args += ["--verify-scope", meta["verify_scope"]]
    return args


def rerun(run_dir: Path, quiet: bool = False) -> None:
    if not (run_dir / "run.json").exists():
        print(f"skip {run_dir} (no run.json)")
        return
    args = rebuild_args(run_dir)  # read the recorded config BEFORE deleting it
    shutil.rmtree(run_dir, ignore_errors=True)
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"FAILED {run_dir.name}: {proc.stderr[-600:]}")
        return
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    if not quiet:
        print(f"{run_dir.name}: {summary}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default=None, help="only rerun this one directory name")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    targets: list[Path] = []
    if args.only:
        for cand in list(RUNS.glob(args.only)) + [RUNS / args.only]:
            if cand.exists():
                targets.append(cand)
    else:
        targets = list(sorted(RUNS.iterdir())) + list(BASELINES)
    for t in targets:
        if not (t / "run.json").exists():
            print(f"skip {t.name} (no run.json; stale dir)")
            continue
        try:
            rerun(t, quiet=args.quiet)
        except Exception as exc:  # noqa: BLE001
            print(f"error {t.name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
