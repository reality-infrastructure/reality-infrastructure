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

### A1 — 2026-11-14 — known answer 1 was wrong; four corrections of fact

Made after the build, in the commit that adds the pack. Nothing below changes a
threshold or a verdict rule.

1. **Known answer 1 FAILED as declared.** `python -m engine.validate ri_operator` on the
   bare scaffold exited 0, not non-zero. The declaration was written without reading
   `engine/validate.py`: the scaffolder is built to load green, and a held-out set with
   no case yet is not a gate (JH-C9). This is an error in the pre-registration, not a
   defect in the engine. The engine was not changed to make the declaration true.
   Known answers 2 and 3 held (tests `test_known_answer_2_*`, `test_known_answer_3_*`).
2. **Known answer 3 is tested on an event row.** A non-fixture pack cannot declare a
   local model, so no agent run can be produced inside the test suite. The test alters
   one field of a stored `gate_requested` row and confirms `ledger.verify_row` refuses it.
3. **Event types live in `events.yaml`**, as every pack's do. The contract said
   `events.py`. There are six types, not three: `constraint_named`, `judgment_run`,
   `gate_requested`, `gate_verdict`, `evidence_submitted`, `fetch_logged`.
4. **PROVENANCE.md is at `contracts/ri_operator/`**, not in the pack: the source paths
   contain banned nouns. The banned-noun check was applied as a substring match, the
   strict reading, and passes.
5. **Replay.** Three commands (`ri-bottleneck`, `ri-judgment`, `ri-evidence`) end in an
   event and not an agent run, so `engine.replay <run_id>` does not apply to them. Their
   proof is `python -m packs.ri_operator.record verify <event_id>`, which re-derives the
   ledger entry and checks its inclusion proof. `engine.replay` applies to `ri-gate`
   route A and to `ri-pack run`.

Baseline after the build: 792 passed, 1 failed, 1 skipped (777 + 15 new; the same one
failure). One of three full runs also failed
`tests/test_identity.py::TestHypothesisEquivalence::test_equivalence_relation`; it passed
in the other two full runs and in three isolated runs. It is a property test on a file
this contract does not touch. Recorded as observed; cause not established.
