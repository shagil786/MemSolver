# MEMO — Cost per resolved case (OP-03, to the CFO)

**Prior (shipped reference, unmodified Harbour, gpt-4.1-mini class):**
**$0.00842 per resolved case** on the 60-case holdout, resolving 38/60 (63.3%),
latency p95 ≈ 11.4 s.

**Measured so far (local lab, simulated budget tiers at pinned list prices):**

| operating point | cost / resolved | quality | vs prior |
|---|---|---|---|
| shipped reference | $0.00842 | 63.3% | 1.0x |
| schema prune + mini | $0.00701 | 63.3% | 0.83x |
| schema prune + nano | $0.00144 | 65.0% | **0.17x** |
| schema prune + strong | $0.01302 | 85.0% | 1.55x (cost up) |

The prompt-shrinking lever alone removes ~17% of cost with zero quality loss
(prune + mini vs shipped: identical 38/60 resolutions at 0.83x cost). Dropping
to the cheapest budget tier (nano) gets us to **17% of prior cost** — a ~6x
reduction, not yet the promised 10x — while quality holds at 65%. Buying
quality up to the 85% floor with the strongest tier instead *raises* cost
1.5x, so we do not ship that.

**Where quality is traded:** the frontier is a straight swap. At 0.17x cost we
sit at 65% exact-goal success (39/60). The gap to the 85.3% floor is
concentrated in hard-family cases (fraud/identity refusal, injected
instructions, closed-loan traps) where a cheap model guesses wrong and
commits; these are precisely the cases where a second, stronger check would
pay. Identity verification is never skipped in any point we would ship — the
savings come from prompt size and tier choice, not from policy.

**If volume doubles or mix shifts:** cost scales linearly with volume; the
cheap point stays 0.17x of prior per resolved case. A mix shift toward hard
families would hurt the 65% quality point faster than the shipped one (quality
loss is concentrated in medium/hard), which argues for keeping a strong-tier
fallback path before we commit on hard-looking intents.

**Decision needed from you:** we can hold quality at ~65% at **$0.00144 per
resolved case** (ship today, 17% of prior spend), or spend up to a further
~2-3x of that budget on verification/strong-tier retries to try to clear the
85% quality bar. I recommend approving the verification workstream — at ~2x of
the nano point it would still be under 40% of prior cost — rather than
freezing the 65% point. Do you approve the added verification spend?
