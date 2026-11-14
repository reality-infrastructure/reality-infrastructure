---
description: Put one agent to work inside a fence — scaffold its pack, declare what it may read and write, give it an output schema and guardrails, run it, have its run ruled on, and prove the run by replay. `new <pack>`, `check <pack>`, `run <pack>/<agent>`, `rule <pack>/<agent>`, `prove <run_id>`.
---

Argument: **$ARGUMENTS** — one of `new <pack>`, `check <pack>`, `run <pack>/<agent> <input JSON>`,
`rule <pack>/<agent>`, `prove <run_id>`. With no argument, print this list and stop.

Why this command exists: the time a person spends deciding whether an agent's
output can be accepted is the limit on how much agent work an organisation can
use. The fence moves that check from the person to the machine: what the agent
could touch, what shape its answer had to take, which rule passed it, and a
replay that anyone can run.

All commands run from the directory `$RI_HOME`. This command edits nothing under
`engine/`.

---

## `new <pack>` — start from the skeleton

```bash
python -m engine.scaffold new-domain <pack>
```

Then fill the pack in this order, and stop at the first step that cannot be done
honestly:

1. **The workflow of the past first.** `agents/<agent>/workflow.md`: who did this
   job by hand, how long it took, what they checked. If nobody did it by hand,
   there is nothing to harness yet: stop.
2. **Count the real cases before writing anything else.** The golden set
   (`eval/golden.jsonl`) is built from real historical inputs with their
   provenance. Fewer than ten real cases is a STOP. A made-up case is never
   written.
3. **Deny by default.** `access.yaml` lists every table and file the agent may
   read or write. Anything not listed fails the run closed. Start from nothing
   and add one line at a time.
4. **The output schema.** Every field a reader could act on is marked traceable
   and must carry a citation to the row it came from.
5. **A held-out set**, disjoint from the golden set, never tuned on. A change is
   adopted only if it does not get worse there.
6. **Events.** One declared type per real action, each with a payload schema.

## `check <pack>` — does it load

```bash
python -m engine.validate <pack>
```

Report the output verbatim. `INVALID` is a finding to fix in the pack, never in
the validator.

## `run <pack>/<agent> <input JSON>` — one run

This calls a model provider and costs money. Do not run it without the owner's
word that the spend is allowed; say what you were about to run and stop.

```bash
python -m engine.run <pack>/<agent> --input '<input JSON>'
```

Exit 0 is a certified output. Exit 2 means a guardrail, the verifier or the
access policy refused it: report the listed reasons as they are. A failed run is
logged exactly as a successful one is, and is not retried with a looser fence.

## `rule <pack>/<agent>` — a verdict on each run

```bash
python -m engine.verdicts <pack>/<agent> --pending
python -m engine.verdicts <pack>/<agent> --run <run_id> --verdict followed|overridden|wrong|n/a --reason "<why>"
```

- `followed`: the output is what the manual workflow would have produced.
- `overridden`: usable, but one named field should read differently.
- `wrong`: not usable.
- `n/a`: the input was not a real case.

A person's verdict outranks an agent judge's. Do not enter a verdict on a
person's behalf: list the pending runs and what each needs, and stop.

## `prove <run_id>` — the replay

```bash
python -m engine.replay <run_id>
```

`OK` means the stored run still matches its ledger entry and its judgement
re-derives byte for byte. `MISMATCH` is reported as it is and nothing is
repaired.

---

## What to refuse

- Widening `access.yaml` because a run was denied. The denial is the fence
  working; ask whether the agent should need that table at all.
- Growing the golden set from runs nobody has ruled on.
- Swapping the model for a cheaper one without the parity matrix
  (`python -m engine.eval <pack>/<agent> --models ...`).
- Adopting a prompt change while a drift reading says the inputs have moved.
- Treating a judge as trusted because it agrees. A judge is trusted after it
  catches planted errors, and suspended when it misses them.

## Output

```
PACK    : <pack>            CHECK: OK | INVALID <first error>
AGENT   : <agent> (<role>)  GOLDEN: <n> real cases   HELD-OUT: <n>
RUN     : <run_id> <status> cost <usd>   (or: not run — spend not authorised)
VERDICT : <followed|overridden|wrong|n/a|pending> by <human|agent:judge>
PROOF   : OK | MISMATCH | not run
STOPPED : <the step that could not be done honestly, or none>
```
