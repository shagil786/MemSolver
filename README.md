# MemSolver

A practice lab for the "OP-03: Ten Times Cheaper" hiring problem. The goal of
that problem: take a working AI loan-servicing agent and cut the cost of each
case it resolves by 10x without wrecking accuracy, speed, or policy safety.

This repo is a safe place to try cost-cutting ideas. It runs the real agent
against the real 180 published cases, but the language models behind it are
simulated, so experiments are free, fast, and repeatable.

## The setup, in plain words

Three pieces work together.

1. **The agent and the cases are real.** `vendor/challenge/` is a pristine copy
   of Harbour, the loan-servicing agent from the challenge, plus its 180 cases
   and the official scorer. Each case is a customer request (waive a fee, pause
   a payment, dispute a charge) with an exact expected end state.

2. **The models are stand-ins.** `lab/` contains a gateway that pretends to be
   a budget language model. It reads the customer message, decides the next
   tool call the way a real model would, and gets things wrong at a rate that
   depends on the model tier and case difficulty. Three tiers exist: `nano`
   (cheapest, weakest), `mini` (mid, the reference model), `strong` (priciest,
   best). Every call is priced at fixed list prices and written to a ledger.

3. **The ledger is the only cost that counts.** Quality is scored by the
   official scorer against the database the agent actually changed. Cost comes
   only from the gateway ledger. A vendored copy of the challenge's own reader
   checks our numbers, so we cannot fool ourselves about the price.

Why simulate at all? Real model calls cost money and vary run to run. With a
deterministic simulated gateway, the same command always produces the same
ledger, so you can compare ideas honestly and cheaply.

## What we found

Measured on 60 held-out cases (kept separate from the 120 used for tuning):

| Setup | Cases fully resolved | Cost per resolved case | vs. shipping agent |
|---|---|---|---|
| Shipping agent (reference) | 63% (38/60) | $0.00425 | 1x |
| Cheapest tier + smaller prompts + free caching | 65% (39/60) | $0.00015 | **0.03x** |
| Cheap tier, but a review step before finishing | 87% (52/60) | $0.00068 | 0.16x |

Three ideas moved the needle, in order of impact.

- **Free prompt caching.** Every call re-sends the instructions and the
  conversation so far. When the unchanged part is served from a cache at zero
  cost, only the new part is billed. This alone took the reference agent from
  $0.00425 to $0.00022 per resolved case.
- **Cheaper models for easy work.** Combined with sending each case only the
  tool schemas it needs (the biggest single token cost), the cheapest tier hit
  0.03x the shipping cost at the same accuracy.
- **A review step before the agent finishes.** Cheap models quietly do the
  wrong thing sometimes. Letting a stronger model look at the finished work and
  demand a redo fixed most of those mistakes. That raised accuracy to 87%,
  above the challenge's quality floor, at 0.16x the shipping cost.

Two gaps stay open. The review-step setup is about 6x cheaper, not the full
10x, and it is slower (a tail case can take ~12 seconds versus ~3 seconds for
the reference). Both trace to the same cause: the expensive retry-and-review
calls on hard cases. Every cheaper version of that mechanism we tried cost the
one extra resolved case that keeps us above the quality floor, so we stopped
there and documented the trade.

## What is honest about this lab, and what is not

The scorer, the reader, the ledger, the agent, and the cases are real. Two
things are approximations you should know about.

- **Token counts are rough.** We count a token as roughly four characters, and
  the measured prices assume that. The ratios between setups are trustworthy;
  the dollar figures are relative, not exact.
- **Prompt shrinking looks free here.** A real model can lose accuracy when
  you cut its instructions; our simulated model never reads them, so cutting
  them costs nothing by construction. Treat the pruning savings as an upper
  bound.
- **Six published cases can never pass the scorer.** They ask the agent to
  verify a customer with phone digits the customer never supplied, then score
  that verification as required. The best any agent can do is escalate, which
  the scorer marks wrong. That caps the maximum reachable score near 93%.

## How to run it

Requirements: Python 3.11+, no packages to install.

```bash
python3 -m pytest                 # 55 tests
python3 -m lab.split              # (re)create the 120/60 dev/holdout split
python3 -m lab.worker --cases lab/splits/holdout.jsonl --model mini \
    --run-dir results/runs/example --seed op03-lab-v1 --tag example
python3 -m lab.analysis           # rebuild results/final (pareto, gates report)
python3 -m lab.plots              # refresh the SVG charts in results/final
```

Levers on the worker command: `--prune` (per-case tool schemas), `--prefix-cache`
(free caching), `--compact` (shorter retry context), `--ladder nano,strong`
(cheap first, stronger on retry), `--verify` (review step before finishing).
`lab/rerun.py` rebuilds any run from its recorded configuration.

## Layout

```
vendor/challenge/   pristine upstream: the agent, 180 cases, scorer, reader
lab/                gateway, simulated models, worker, analysis, plots, rerun
memsolver/          shared pricing and capability tables
lab/solution/       working copy of the agent where the cost levers live
results/final/      pareto points, gates report, manifest, SVG charts
MEMO.md             one-page summary written for a CFO
DECISIONS.md        why each modelling choice was made
EXPERIMENT_LOG.md   what was tried and what it cost
```

## Where this goes next

Two ideas remain untried: redo only the failed step instead of re-planning the
whole case, and a latency-aware ladder that routes retries by how hard the
case looks. Both target the same remaining cost and speed gap. Nothing else on
the frontier looked worth a trade.
