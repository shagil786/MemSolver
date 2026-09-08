# MEMO: cost per resolved case (OP-03, for the CFO)

**What we started with.** The shipping agent resolved 63% of the 60 held-out
cases (38/60) at $0.00425 per resolved case, with a p95 latency of about 3 s.

**What we have now.** All numbers below come from the same 60 held-out cases,
measured on a local lab that runs the real agent and prices simulated budget
models at fixed list prices.

| setup | resolved | cost per resolved case | vs shipping |
|---|---|---|---|
| shipping agent (reference) | 63% | $0.00425 | 1.0x |
| shipping + free prompt cache | 63% | $0.00022 | 0.05x |
| cheapest tier + smaller prompts + cache | 65% | $0.00015 | 0.03x |
| cheapest tier + review step + cache | **87%** | $0.00068 | 0.16x |

Three changes did the work, in order of size.

1. A free cache for the part of each call that does not change. Every call
   re-sends the instructions and the conversation so far. Serve that unchanged
   prefix from a cache at no cost and only the new part is billed. This alone
   cut the shipping agent's cost per resolved case from $0.00425 to $0.00022.
2. A cheaper model for easier cases, plus sending each case only the tool
   descriptions it needs. Together these put the cheapest tier at 0.03x the
   shipping cost at the same accuracy (65%).
3. A review step before the agent finishes. Cheap models sometimes quietly do
   the wrong thing. A stronger model looks at the finished work and can send
   it back. That raised accuracy to 87%, above the quality floor, at 0.16x the
   shipping cost.

**What still does not work.** Two gaps remain on the review-step setup. It is
about 6x cheaper, not the full 10x, and a slow case can take ~12 s instead of
~3 s. Both come from the same place: the expensive retry and review calls on
the hard cases. We tried every cheaper version of that mechanism we could
think of, and each one lost the single resolved case that keeps us above the
quality floor, so we kept the expensive version and wrote the trade down.

**Where the risk sits.** The cheap setups keep identity checks and never cut a
policy corner; all savings come from caching, prompt size, and model choice.
Quality loss concentrates in the hard families (fraud, identity refusal,
injected instructions) where a cheap model guesses and commits, which is
exactly the case the review step fixes. Volume scales cost linearly, so the
ratios above hold at any volume; a mix shift toward hard families hurts the
cheap setups faster than the review setup.

**The decision.** Ship the 65% setup today at $0.00015 per resolved case (3% of
prior spend), or spend about 4.5x that to reach 87% accuracy at $0.00068 per
resolved case with the review step. I recommend the review setup. It is still
under 20% of prior cost, it clears the quality floor, and the two remaining
problems are latency and a last stretch of cost, not accuracy or policy.
