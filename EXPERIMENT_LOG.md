# EXPERIMENT LOG

Deterministic local lab; every run is reproducible with the same command
(`lab/worker.py --cases <split> --model <tier> --harbour-dir <dir> [--prune]
[--ladder ...] --run-dir results/runs/<name> --seed op03-lab-v1`).

## 2026-09-08 — lab bring-up and first frontier

- **M1 substrate:** vendored pristine OP-01/OP-03 material; re-pinned
  `memsolver.pricing` to budget-class tiers (nano/mini/strong) at list prices;
  per-model capability tables.
- **M2 controller:** rewrote the simulated model as a per-step policy machine.
  Pure-controller ceiling (p=1.0): dev 117/120 (0.975), holdout 56/60 (0.933);
  the residual failures are six strict-scorer-unsatisfiable identity cases and
  one already-open-dispute trap.
- **M3 calibration:** measured single-model quality on the holdout across
  `p_correct` scales; set `simconfig.P_SCALE = {nano:.55, mini:.45, strong:.85}`
  so mini (the reference model) lands at 0.633 (38/60), matching the published
  reference. Baseline validated by the official `ledger_reader.py`.
- **M4 levers:** solution copy of Harbour with schema pruning (≈17% token cut,
  quality-neutral here) and attempt ladder (mini/strong; silent-wrong commits
  don't trigger it). No-op solution run bit-for-bit matches the baseline.
- **M5 frontier (holdout, 60):**

| point | quality | $/resolved | ×baseline |
|---|---|---|---|
| shipped (mini, reference) | 0.633 | 0.008424 | 1.00 |
| prune+mini | 0.633 | 0.007005 | 0.83 |
| prune+nano | 0.650 | 0.001435 | 0.17 |
| ladder nano→strong +prune | 0.650 | 0.001806 | 0.21 |
| prune+strong | 0.850 | 0.013023 | 1.55 |

  Gates: quality floor 0.853 and cost bar 0.10× are not jointly met by any
  point yet; the cheapest point is 0.17× (≈6x cheaper) at equal-or-better
  quality, and the strong point clears quality but raises cost. Frontier shape:
  cheap tiers buy ~6x at 65%; the missing 12-13 quality points need a
  verification/rework lever, not a flat tier upgrade.

Next session: implement the verification pass (strong-tier review before
commit on medium/hard intents) and transcript compaction; re-run the frontier.
