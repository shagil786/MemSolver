# MemSolver — local lab for OP-03 "Ten Times Cheaper"

A reproducible lab that runs the **real published Harbour** loan-servicing agent
over the **real 180 published cases**, measures exact-goal quality with the
official `goal_scorer.py`, and prices every model call only through a gateway
ledger at pinned budget-class list prices — mirroring the OP-03 grading
contract (`ledger_reader.py`, `pareto_schema.json`, vendored verbatim).

## Layout
- `vendor/challenge/` — pristine upstream (never edit): Harbour, cases,
  scorers, schemas.
- `lab/` — the lab: `plans.py` (deterministic simulated-model controller),
  `gateway.py` (OpenAI-compatible gateway + ledger), `worker.py` (one measured
  run), `split.py` (120/60 dev/holdout), `analysis.py` (pareto/manifest/gates),
  `solution/harbour/` (working copy where cost levers live).
- `memsolver/` — shared substrate: pinned prices, capability tables, RNG.
- `results/` — run artifacts (gitignored).
- `MEMO.md`, `DECISIONS.md`, `EXPERIMENT_LOG.md` — OP-03 analysis docs.

## Commands
```
python3 -m lab.split                                  # (re)make the 120/60 split
python3 -m lab.worker --cases lab/splits/holdout.jsonl --model mini \
    --run-dir results/runs/<name> --seed op03-lab-v1 --tag <name>
python3 -m lab.worker ... --harbour-dir lab/solution --prune --ladder nano,strong
python3 -m lab.analysis                              # pareto.jsonl + report.md
python3 -m pytest
```

## Reproduce one frontier run
```
python3 -m lab.worker --cases lab/splits/holdout.jsonl --model nano \
    --harbour-dir lab/solution --prune --run-dir results/runs/prune-nano \
    --seed op03-lab-v1 --tag prune-nano
```
See `EXPERIMENT_LOG.md` for the measured frontier and `DECISIONS.md` for the
simulation's semantics and known biases.
