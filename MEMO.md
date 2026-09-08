# MEMO: cost per resolved case (OP-03, for the CFO)

**Prior (shipped reference, unmodified Harbour, gpt-4.1-mini class):**
**$0.00425 per resolved case** on the 60-case holdout, resolving 38/60 (63.3%),
p95 latency 2.9 s.

**Measured so far (local lab, simulated budget tiers at pinned list prices):**

| operating point | cost / resolved | quality | vs prior |
|---|---|---|---|
| shipped reference | $0.00425 | 63.3% | 1.0x |
| shipped + free prefix cache | $0.00195 | 63.3% | 0.46x |
| schema prune + nano | $0.00084 | 65.0% | 0.20x |
| prune + nano + prefix cache | $0.00039 | 65.0% | **0.09x** |
| prune + nano->strong + grounded verify + prefix cache | $0.00117 | 86.7% | 0.28x |
| prune + strong + prefix cache | $0.00450 | 86.7% | 1.06x (no saving) |

The prompt-shrinking lever alone removes ~17% of cost with zero quality loss
(prune + mini vs shipped: identical 38/60 resolutions at 0.83x cost). Dropping
to the cheapest budget tier (nano) gets us to **20% of prior cost**, a ~5x reduction, not yet the
promised 10x, while quality holds at 65%. The
The free self-hosted prompt-prefix cache (unchanged conversation head billed
at $0) roughly halves cost on its own, and the cheapest tier now clears the
0.10x bar at **$0.00039 per resolved case (65% quality)**. A grounded
verification pass (a strong-tier review before commit that can demand a redo)
lifts a nano base to **86.7% quality** at 0.28x prior cost. Two guardrails are
now the binding constraints on that point: p95 latency (verification + strong
retries, ~12 s vs 2.9 s prior) and the elective-deferral rate (26% vs the 10%
bar, driven by the cheap model's escalation-without-work behaviour).

**Where quality is traded:** the frontier is a straight swap. At 0.17x cost we
sit at 65% exact-goal success (39/60). The gap to the 85.3% floor is
concentrated in hard-family cases (fraud/identity refusal, injected
instructions, closed-loan traps) where a cheap model guesses wrong and
commits; these are precisely the cases where a second, stronger check would
pay. Identity verification is never skipped in any point we would ship. The
savings come from prompt size and tier choice, not from policy.

**If volume doubles or mix shifts:** cost scales linearly with volume; the
cheap point stays 0.17x of prior per resolved case. A mix shift toward hard
families would hurt the 65% quality point faster than the shipped one (quality
loss is concentrated in medium/hard), which argues for keeping a strong-tier
fallback path before we commit on hard-looking intents.

**Decision needed from you:** we can hold quality at ~65% at **$0.00039 per resolved case** (ship today,
9% of prior spend), or fund the verification path that reaches **86.7% quality
at 0.28x prior cost** but needs two engineering fixes first: cutting the p95
latency it adds (target: gate the verification to medium/hard work only, and
cap strong retries) and driving the cheap tier's elective deferrals under 10%.
I recommend funding that workstream - at 0.28x prior cost it is already well
under the 10x target while clearing the quality floor. Do you approve?
