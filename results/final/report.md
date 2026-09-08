# OP-03 gates report (local 60-case holdout)

Reference (shipped mini): quality 0.633 (38/60), cost/resolved $0.004249, p95 2.944s.
Quality floor: 0.853 (=52/60). Cost bar: 0.10x = $0.000425/resolved.

| run | quality | cost/res | 0.1x? | floor? | p95<=ref | elect.defer<=10% | viol<=ref |
|---|---|---|---|---|---|---|---|
| shipped-baseline | 0.633 | $0.004249 | N | N | Y | N | Y |
| shipped-prefixcache | 0.633 | $0.000217 | Y | N | Y | N | Y |
| sol-noprune-mini | 0.633 | $0.004243 | N | N | Y | N | Y |
| prune-mini | 0.633 | $0.003509 | N | N | Y | N | Y |
| prune-nano | 0.650 | $0.000841 | N | N | Y | N | Y |
| nano-noprune | 0.650 | $0.001018 | N | N | Y | N | Y |
| ladder-ns-prune | 0.650 | $0.001212 | N | N | Y | N | Y |
| prune-nano-pc | 0.650 | $0.000145 | Y | N | Y | N | Y |
| prune-nano-pc-compact | 0.650 | $0.000145 | Y | N | Y | N | Y |
| prune-mini-pc-verify | 0.850 | $0.001025 | N | N | N | N | Y |
| prune-nano-ladderNS-verify-pc | 0.867 | $0.000814 | N | Y | N | Y | Y |
| prune-nano-ladderNS-verify-pc-compact | 0.867 | $0.000681 | N | Y | N | Y | Y |
| verify-all-mini | 0.850 | $0.000621 | N | N | N | Y | Y |
| verify-first-strong | 0.850 | $0.000648 | N | N | N | Y | Y |
| verify-first-mini | 0.833 | $0.000512 | N | N | N | N | Y |
| prune-nano-ladderNS-verify | 0.867 | $0.014919 | N | Y | N | Y | Y |
| prune-strong | 0.867 | $0.010619 | N | Y | N | Y | Y |
| prune-strong-pc | 0.867 | $0.001695 | N | Y | N | Y | Y |
| strong-noprune | 0.867 | $0.012843 | N | Y | N | Y | Y |

## Ablations (each lever alone vs shipped baseline, holdout)

| lever | quality | cost/res | vs baseline cost/res |
|---|---|---|---|
| shipped + free prefix cache | 0.633 | $0.000217 | 0.05x |
| schema prune, mini | 0.633 | $0.003509 | 0.83x |
| schema prune, nano | 0.650 | $0.000841 | 0.20x |
| nano, full prompt | 0.650 | $0.001018 | 0.24x |
| nano->strong ladder + prune | 0.650 | $0.001212 | 0.29x |
| schema prune, nano + prefix cache | 0.650 | $0.000145 | 0.03x |
| prune, nano + prefix cache + compact context | 0.650 | $0.000145 | 0.03x |
| prune, mini->strong + verify + prefix cache | 0.850 | $0.001025 | 0.24x |
| nano->strong + grounded verify + prefix cache | 0.867 | $0.000814 | 0.19x |
| verify + prefix cache + compact context | 0.867 | $0.000681 | 0.16x |
| verify with mini (cheaper), all attempts | 0.850 | $0.000621 | 0.15x |
| verify attempt 0 only, strong | 0.850 | $0.000648 | 0.15x |
| verify attempt 0 only, mini | 0.833 | $0.000512 | 0.12x |
| nano->strong + verify, NO prefix cache | 0.867 | $0.014919 | 3.51x |
| schema prune, strong | 0.867 | $0.010619 | 2.50x |
| schema prune, strong + prefix cache | 0.867 | $0.001695 | 0.40x |
| strong, full prompt | 0.867 | $0.012843 | 3.02x |

## Cost decomposition by model (selected runs, ledger USD)

- shipped-baseline: {'mini': 0.161452}
- prune-mini: {'mini': 0.133326}
- prune-nano: {'nano': 0.032792}
- prune-strong: {'strong': 0.552213}
- ladder-ns-prune: {'nano': 0.032052, 'strong': 0.015224}

## Quality by family (prune-strong, matches/total)

- autopay_cancel: 0.60 (3/5)
- contact_update: 1.00 (5/5)
- dispute_close: 1.00 (5/5)
- dispute_open: 0.80 (4/5)
- document_request: 1.00 (5/5)
- fee_waiver: 1.00 (5/5)
- hardship_request: 1.00 (5/5)
- identity_challenge: 0.60 (3/5)
- injected_instruction: 1.00 (5/5)
- out_of_scope: 1.00 (5/5)
- payment_reschedule: 0.80 (4/5)
- statement_request: 0.60 (3/5)
