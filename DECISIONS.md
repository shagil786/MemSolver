# DECISIONS

Record of the load-bearing choices in this lab and why they were made.

## Simulation fidelity
- **Real Harbour, real cases.** The lab vendors the published Harbour service
  (`vendor/challenge/`) and runs the real agent loop, real tools/backend/policy,
  and real 180-case `goal_state` scoring via the official `goal_scorer.py`.
  Quality is exact end-state match, not a probability at the end.
- **Gateway ledger is the only cost.** A local OpenAI-compatible gateway sits
  behind `LLM_BASE_URL`; every completion is billed at pinned budget-class
  list prices and written to the ledger. The agent never reports its own spend,
  and the vendored `ledger_reader.py` is used verbatim for authoritative
  metrics (it rejects our files if ledger/runs disagree — a per-run check).
- **Simulated model behaviour.** The gateway's controller is a policy machine
  over the real servicing policy (escalation triggers, identity-before-money,
  caps, windows, injected-instruction refusal) with tier×difficulty capability
  and deterministic failure regimes. It never reads `goal_state`.
- **Calibration anchor.** Per-model `p_correct` scales were chosen so a single
  `mini` (reference) model lands at ~0.633 on the 60-case local holdout,
  matching the published reference ballpark (37/60 ≈ 0.617).

## Scorer semantics (documented, not fudged)
- `goal_state_match` is the vendored scorer, strict. Six published cases
  (c_0030, c_0134, c_0144–46, c_0148) require a *successful* `verify_identity`
  while the customer's digits are wrong and `verified:0` is expected — these
  are unsatisfiable under strict scoring; our agent attempts the intended
  verify→escalate path and the scorer marks them failed. This caps achievable
  quality near 0.93 (local holdout), so the 85.3% gate is nearly maxing the
  metric rather than the agent.
- `deferred` = escalate was attempted and the run did not end in a matched,
  committed, required-escalation resolution. Elective deferral = deferred on a
  case that does not require escalation. Reported per OP-03.

## Levers shipped (solution copy, each isolated behind config)
- **Schema pruning** (`--prune`): advertise only the tools the case needs;
  shrinks the system prompt re-sent on every call (the dominant input cost).
  In this simulation the model does not read the schema list, so pruning is
  quality-neutral here; real-model runs may need a small penalty knob.
- **Attempt ladder** (`--ladder nano,strong`): cheap model on attempt 0,
  stronger on retries. Only fires when a tool *errors* (silent wrong commits do
  not retry), which is why ladder results track the first-tier model closely.

## Known sim biases (be honest with reviewers)
- Token counting is chars/4, not a real tokenizer; the system prompt dominates
  cost, so ratios between levers are the trustworthy numbers, not absolutes.
- The deterministic exact-match cache rarely fires in single-shot loops; a
  real prompt-prefix cache would cut retry costs further (modelled later).
- Schema pruning is quality-neutral by construction (see above).

## Next levers to try (in priority order)
1. Verification pass on hard-looking intents before `commit` (a strong-tier
   review call), to lift the 65% cheap point toward the 85% floor.
2. Transcript compaction between steps (tool results re-sent verbatim each
   call today — the second-largest token cost).
3. Prompt-prefix caching in the gateway (self-hosted = free) for retries.
4. Content-based easy→nano routing (family keywords), keeping mini for the
   hard families instead of a flat tier.
