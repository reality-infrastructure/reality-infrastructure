# CONTRACT: RI-OPERATOR-WAITING — what is built and waits for an observation

```
status: QUEUED 2026-11-14. Nothing here is to be built. Each item waits for the
        trigger beside it, and is accepted by the gate already written in its
        own contract (contracts/ri_operator/).
rule:   no new tooling for this pack before the first deployment has a human
        reply (the scan of 2026-11-14, event 862cb0d5).
```

## Waiting on a date

| On or after | Action | Then |
|---|---|---|
| 2026-11-20 | `/ri-scan` on the same system scores the prediction written on 2026-11-14 | the scan has its first scored prediction |
| 2026-11-21 | `/ri-foresight support-outsourcing`: settle sheets `so-1120` and `so-1120-env`, review, compare | ri-foresight DELIVERED (CONTRACT-3.md, last acceptance line) |
| 2026-11-21 | `/ri-week`, once a week of ledger exists to grade | ri-week DELIVERED (CONTRACT-2.md) |

## Waiting on someone else

| Trigger | Action | Then |
|---|---|---|
| A prospect of the first deployment forwards ten real tickets | `/ri-pack` real run; no substitute repository | ri-pack DELIVERED (CONTRACT.md) |
| A real action that should pass the gate | Write the expected verdict into the prereg first, then the second paid checker run | first evidence on whether the checker can return PROCEED |
| Held-out cases exist for the checker | Correct the instruction that turns "cannot decide" into "failed" | the eight-of-eight habit is tested, not assumed fixed |

## Review after the first paid deployment

Ruling R1 (open source, paid fixed-price deployment) is revisited then, with the dissent
recorded under it in CONTRACT.md.
