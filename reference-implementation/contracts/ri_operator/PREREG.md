# PREREG: RI-OPERATOR

```
FROZEN at the commit that adds this file. Written before any pack file, command file
or test exists on this branch. Changes after that commit are dated amendments below.
```

## What is being claimed

Five operator commands can run inside the harness with their outputs as ledger events,
with no change to the engine, and each can be shown working by one replayable run on a
real repository.

## Inputs, pinned at copy time

Each source is copied once. PROVENANCE.md records its path and sha256 on the day of the
copy. Sources:

| Command | Source |
|---|---|
| ri-bottleneck | `~/.claude/commands/bottleneck.md` |
| ri-judgment | `~/.claude/commands/judgment.md` |
| ri-gate | `~/hyperliquid/.claude/commands/gate.md`, `~/rich/scan/prompts/disprove.md` |
| ri-pack | `HARNESS.md`, `engine/` (this branch) |
| ri-evidence | `forge/README.md` (this branch), `~/power-path/agents/PROTOCOL.md` |

## Closed vocabulary

- Gate verdicts: `PROCEED`, `VERIFY-FIRST`, `RESTRUCTURE`, `HOLD`. No others.
- Delivery status per command: `DELIVERED` (validated, tested, one real run replayed) or `NOT DELIVERED` (with the reason). No partial status.
- A quantity with no command behind it is written `UNKNOWN`.

## Banned nouns (the genericity check)

The pack and the five commands must not contain, case-insensitive:
`atlas`, `hyperliquid`, `venue`, `clip`, `leg`, `VPS`, `pump`, `polymarket`, `wallet`,
`newce`, `Irvin`, `PPG`, `rich/`, `hood`, `ladder`, `mimicry`.
A hit is removed by rewriting the sentence, never by weakening the check.

## Known answers, declared before the build

1. `python -m engine.validate ri_operator` on the bare scaffold exits non-zero until the disprover agent carries a held-out set disjoint from its golden set.
2. A gate event whose verdict is outside the closed vocabulary is refused at append.
3. Replaying a gate run after altering one byte of its stored evidence fails.

If any of the three behaves otherwise, STOP and report. It is a finding, not a bug to tune away.

## Baseline

777 passed, 1 failed, 1 skipped at 1be79e5, run 2026-11-14 from the worktree
`C:\Users\newce\ri-operator\reference-implementation`. The failing test embeds an absolute
path and is expected to fail from any directory other than the original checkout.

## STOP conditions

- An engine, core or frozen-module file would have to change.
- A banned noun cannot be removed without changing what a command does.
- A real run would require credentials, spend or network access the operator has not granted.

## Amendments

(none)
