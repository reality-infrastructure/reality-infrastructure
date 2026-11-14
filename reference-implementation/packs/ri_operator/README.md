# ri_operator — the operator pack

An agent's report of its own work is not evidence. This pack makes each operator
decision leave a record on the engine's Merkle ledger: what was decided, on what
evidence, and by whom. Anyone holding the store can check that a record is still
the one that was written.

Nothing in `engine/` knows this pack exists.

## The five commands

Each lives in `.claude/commands/` at the repository root and ends by appending
exactly one event with `record.py`.

| Command | The question it answers | Event |
|---|---|---|
| `/ri-bottleneck` | What one thing limits this system, by measurement? | `constraint_named` |
| `/ri-judgment` | Should this decision be committed to? | `judgment_run` |
| `/ri-gate` | Can someone who did not build this action kill it? | `gate_requested`, then `gate_verdict` |
| `/ri-pack` | How is an agent fenced, run and judged? | the engine's own `verdict` |
| `/ri-evidence` | What does the source say, in its own words? | `evidence_submitted`, `fetch_logged` |

## Why each exists

The design follows five published interviews. One line each:

| Principle | Interview | Where it lands |
|---|---|---|
| The time to check agent output is the constraint on agent work. | Schulman, Millidge and O'Neill (the Minsky segment) | Every command ends in a checkable record, not a paragraph. |
| A model rewarded by a grader learns the grader. It will say a test passes after deleting the test. | Musk | `/ri-evidence`: the agent submits the excerpt; it never writes the conclusion. |
| Agents trained to cooperate agree with each other. Agreement between them is not a second witness. | Brown | `/ri-gate`: the disprover cannot read the author's files, only the stated request. |
| Work on the limiting factor and on nothing else. | Musk | `/ri-bottleneck`: one constraint at a time, and a faster non-constraint is logged as waste. |
| Deciding the objective is the part that stays with people. | Schulman | `/ri-judgment` and `/ri-gate` stop and hand the irreversible part back. |
| Progress follows whatever can be verified, and a worker that can check its own score can work in parallel. | Patel | Each event has a schema; a payload that does not fit is refused at append. |
| Iterations teach, hours do not. Judgment is the skill that leverage multiplies. | Naval | The ledger is the count of iterations, with each one's outcome attached. |
| Play long-term games; a reputation is built from a record. | Naval | Events are append-only. A mistake is corrected by a new event, never by an edit. |

## Use

From `reference-implementation/`:

    python -m engine.validate ri_operator
    python -m packs.ri_operator.record append constraint_named --entity-type system --entity-id checkout-api --payload @payload.json --source agent:ri-bottleneck
    python -m packs.ri_operator.record verify <event_id>
    python -m engine.run ri_operator/disprover --input '{"request_event_id": "<event_id>"}'
    python -m engine.replay <run_id>

The store defaults to `.harness/engine.sqlite3` under the directory the command is
run from; `--db` or `DATABASE_URL` points it elsewhere. One process per store.

## What is not here yet

- The disprover has an empty golden set and an empty held-out set. Both are filled
  only from runs a person has ruled on, so neither is a gate until such runs exist.
- No specialist and no adapters. `problem.md` says why.
