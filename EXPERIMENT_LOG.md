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

## 2026-09-08 (later) — audit fixes corrected the frontier
Independent code audit found two HIGH flaws in the simulated model's flawed
regimes that contaminated every stored run:
1. FLAW_ESCALATE never terminated — it re-escalated for the full 12-step budget
   and never committed (~13/60 cases in mini runs, ~6-10x the normal cost of an
   escalate+commit, and the real driver of the 0.38 elective-deferral figure).
2. FLAW_OBEY_INJECTION was dead code (injection check ran on the stripped
   message), so injected-instruction cases never exhibited the "model follows
   the planted instruction" failure mode and ESCALATE was effectively weighted
   2/5.
Both fixed with regression tests; cache key now includes case_id+attempt;
close_dispute parses the customer message. Mini scale re-centred to 0.40 so the
reference still lands at 0.633 (38/60). Frontier re-measured (all numbers
above are post-fix):

| point | quality | $/resolved | ×baseline |
|---|---|---|---|
| shipped (mini, reference) | 0.633 | 0.004249 | 1.00 |
| prune+mini | 0.633 | 0.003515 | 0.83 |
| prune+nano | 0.650 | 0.000842 | 0.20 |
| ladder nano→strong +prune | 0.650 | 0.001213 | 0.29 |
| prune+strong | 0.867 | 0.010646 | 2.51 |

prune+strong now clears the 85.3% quality floor (52/60) but at 2.5x cost and
worse p95; no point yet jointly passes the 0.10x cost bar and the quality
floor. Next: verification pass + transcript compaction + prefix caching.

## 2026-09-08 (final) - prefix caching + grounded verification levers
Implemented and measured (post audit-fix baseline, holdout 60):
- **Free prompt-prefix cache** (`--prefix-cache`): any unchanged leading part of
  the conversation is served from a free self-hosted cache, so only the new
  suffix is billed each call. Roughly halves total cost on the shipped agent
  ($0.00425 -> $0.00195/resolved).
- **Grounded verification** (`--verify`, solution agent): before committing,
  a strong model reviews the transcript; if it flags the attempt, the next
  attempt runs with the next ladder model. Simulated as a grounded re-check:
  clean attempts always pass, flawed attempts are caught with tier-dependent
  probability. Only affordable with the prefix cache (verification without it:
  $0.0173/resolved vs $0.00117 with it).
- New frontier highlights (holdout): prune+nano+prefix-cache hits $0.00039/
  resolved (0.09x, passes the 0.10x bar) at 65% quality; prune+nano->strong+
  verify+prefix-cache reaches 86.7% quality (52/60, above the floor) at 0.28x
  cost but with 12 s p95 and 26% elective deferrals. No point yet jointly
  passes cost bar + quality floor + p95 + elective-deferral gates; the two
  open fixes are scoping verification to medium/hard work and reducing cheap
  tier deferrals.

## 2026-09-08 (final+) - global system-prompt cache and token diagnostic
- Token-spend diagnostic on the ledgers showed that with per-case prefix
  caching, ~93-97% of remaining cost is the FIRST call per case, and that call
  is ~95% system prompt. Added a cross-case system-prompt cache (the pruned
  system prompt is identical across cases -> cached once, reused free), which
  is the same "stable system block" idea as provider prompt caching.
- Result: shipped (mini) + prefix+system cache = $0.000217/resolved (0.05x),
  prune+nano = $0.000146 (0.034x, quality 0.65), prune+nano->strong+verify =
  $0.000956 (0.225x, quality 0.867 above the floor). The remaining cost in the
  verify config is strong-tier redo attempts and verification calls, not the
  prompt. Gate state: the 0.10x cost bar and the 85.3% quality floor are each
  met by different points; verification point is ~2.3x over the cost bar and
  also fails p95 and elective-deferral gates.

## 2026-09-08 (final++) - structured compaction lever
- Implemented `--compact` (solution agent): lookup_loan results are projected
  to the exact fields the decisions read, and a retried attempt's context is
  the machine-parseable tool-result lines instead of a full transcript replay.
  (Naive (tool,args)->result memoization saves nothing here: the transcript is
  the cost, not tool execution - the projected/compact store is the equivalent
  that does save.) One bug during bring-up: the compacted note must keep the
  exact "Previous attempt transcript:" prefix or attempt indexing shifts and
  quality drops - fixed.
- Verify play at 86.7% quality: cost/resolved $0.000956 -> $0.000787 with
  compaction (0.185x baseline). Gate state unchanged qualitatively: the
  0.10x cost bar ($0.000425) and the quality floor are each met by separate
  points; the verify point is ~1.85x over the cost bar and still fails p95
  (~12 s, strong redo latency) and the elective-deferral gate (~26%).
