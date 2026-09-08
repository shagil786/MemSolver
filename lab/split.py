"""Deterministic 120/60 dev/holdout split of the 180 published cases.

The private OP-03 holdout is "the same twelve families and the same difficulty
mix".  Every published family is exactly 8 easy / 4 medium / 3 hard, so we hold
out 3 easy + 1 medium + 1 hard per family = 5 * 12 = 60 cases, and tune only on
the other 120.  The split is fixed by a seed and committed so every run is
comparable.

    python -m lab.split [--seed 20260915]
Writes lab/splits/dev.jsonl and lab/splits/holdout.jsonl (case objects).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent.parent / "vendor" / "challenge" / "cases.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "splits"

FAMILIES = [
    "fee_waiver", "payment_reschedule", "hardship_request", "dispute_open",
    "dispute_close", "document_request", "statement_request", "contact_update",
    "autopay_cancel", "identity_challenge", "out_of_scope", "injected_instruction",
]
PER_FAMILY = 5  # 3 easy + 1 medium + 1 hard


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split(cases: list[dict], seed: int = 20260915) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    by_family_diff: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in cases:
        by_family_diff[c["family"]][c["difficulty"]].append(c)

    holdout_ids: set[str] = set()
    for family in FAMILIES:
        for diff, take in (("easy", 3), ("medium", 1), ("hard", 1)):
            pool = list(by_family_diff[family][diff])
            rng.shuffle(pool)
            holdout_ids.update(c["case_id"] for c in pool[:take])

    holdout = [c for c in cases if c["case_id"] in holdout_ids]
    dev = [c for c in cases if c["case_id"] not in holdout_ids]
    assert len(dev) == 120 and len(holdout) == 60, (len(dev), len(holdout))
    return dev, holdout


def write(cases: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=20260915)
    args = ap.parse_args(argv)
    cases = load_cases()
    dev, holdout = split(cases, args.seed)
    write(dev, OUT_DIR / "dev.jsonl")
    write(holdout, OUT_DIR / "holdout.jsonl")
    print(f"dev={len(dev)} holdout={len(holdout)} seed={args.seed} -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
