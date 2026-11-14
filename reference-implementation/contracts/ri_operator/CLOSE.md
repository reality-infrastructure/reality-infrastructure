# CLOSE: RI-OPERATOR and RI-OPERATOR-2, the delivered five

```
closed:  2026-11-14, on the operator's order: "yes to all three, close and push the five"
branch:  contract/ri-operator, pushed with this commit
```

## Why it is organised this way, from the five transcripts

| Transcript | Point | What follows |
|---|---|---|
| Musk | Work on the limiting factor and on nothing else. | The limiting factor is the first deployment's own sends, not this pack. Building stops here. |
| Schulman, Millidge, O'Neill | Thinking adds no information; only new observations do. | Nothing parked is worked on. Each parked item has a trigger and waits for it. |
| Schulman, Millidge, O'Neill | What is learned from one's own deployment is the part that cannot be copied. | The ledger is the asset. It was in one ignored file; it now has a dated copy outside the worktree. |
| Brown | Work whose proof needs weeks of record cannot be accepted in a day. | The three undelivered commands are parked, not in progress. |
| Patel | Independent gates: no command's acceptance depends on another's. | The five that passed are closed and pushed without waiting for the three that cannot pass yet. |
| Naval | Proof of work is the calling card; accountability is taken under one's own name. | The delivered five are what a buyer is shown. The verdict below is the operator's. |

## Delivered

| Command | Contract | Real run on the ledger |
|---|---|---|
| `/ri-bottleneck` | RI-OPERATOR | `bf661f2d-7602-453e-bdaf-b3247f7b700b` |
| `/ri-judgment` | RI-OPERATOR | `f8640bac-19fe-4e8b-b95b-f944f25a054a` |
| `/ri-gate` | RI-OPERATOR | request `4f290c6a-aeb1-48d3-9935-e18db87d948f`, run `9ce410fd-fab4-4499-8974-2c5e11665ba7`, verdict `3d05ba72-60f8-4421-8f14-4776be96f643` |
| `/ri-evidence` | RI-OPERATOR | `ee577e01`, `73bcb44b` and three fetch events; the claim is unresolved |
| `/ri-scan` | RI-OPERATOR-2 | `862cb0d5-4e78-44d9-a0b9-c5e7613cbc1b` |

## The verdict on the checker's run

Run `9ce410fd-fab4-4499-8974-2c5e11665ba7` (HOLD, eight of eight checks failed) is ruled
`overridden`: G4 does not apply, G8 holds because the check is cheap, and the verdict
should have been VERIFY-FIRST. Reasoning: CONTRACT-2.md. Recorded as event
`7b40cf2a-5423-44c6-bd14-e5da8428ac53`.

The decision is the operator's, given as "yes" to the proposed verdict on 2026-11-14. The
agent typed the command on that order, and the stored reason says so. The checker's
instruction is not changed by this; that change needs held-out evidence first.

## At close

- Suite: `1 failed, 819 passed, 1 skipped` (baseline 777 / 1 / 1 plus 42; the one failure is the path-dependent
  test queued as contracts/queue/artifact-path-determinism.md).
- Engine diff against `contract/irv-harness`: 0 lines.
- The ledger store is ignored by git and is not in this push. A dated copy was taken
  outside the worktree on the same disk; its sha256 is `7eeb916c6cd2d08da2c2e04e6e6a27d8168ced58e2738b49e4373349a33b6b0c`.

## What this close does not claim

1. The checker has one run and has never returned PROCEED. Its golden and holdout sets
   are empty.
2. The gate request and the scan were written by the same session that built the pack.
3. The market-size claim behind `/ri-evidence` is unresolved, and its hypotheses were
   fixed by the agent.
4. Two commands of the original scope (ri-pack here, ri-week in RI-OPERATOR-2) are not
   delivered. This close narrows the scope to what passed; it does not pass them.
