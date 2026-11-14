---
description: The scan — read the ground, score the last scan, name exactly ONE binding constraint from a count and not from a reading, write one move and a prediction with a date, record it on the ledger, and stop. Diagnosis only; it fixes nothing.
argument-hint: "<system> [DEEP | STANDARD]  (default DEEP)"
---

Scan: **$ARGUMENTS** (no mode given: DEEP. No system given: the one in front of you.)

Why this command exists: attention belongs on the limiting factor and nowhere
else, and the limiting factor is found by counting, in a review nobody prepared
for. A measure that looks good can still be measuring the wrong thing, so every
scan first checks what its own last prediction was worth.

**It is read-only.** It runs read-only commands and appends one event. It does not
fix, retune, write a plan, or propose the next project. Use `/ri-bottleneck` to
remove a constraint; this command only names one.

## The rule that decides whether the scan is worth running

**A constraint is counted, never read.** Every figure in the report carries the
command that produced it, run now, or it reads `UNMEASURED`. Never infer a number
and present it as read. `UNKNOWN` is an acceptable answer everywhere. A filled-in
form is not. The event cannot be recorded without a count command.

## The two modes

They change the standard of proof, never the parts and never the permissions.

| | STANDARD | DEEP |
|---|---|---|
| Counts | the output unit and each stage's in and out | the same, plus the age of everything waiting |
| Blind-spot passes | A and B | A, B and C |
| The comfortable-candidate gate | stated | argued in writing, both sides |

If the last scan was STANDARD and this one is DEEP, a changed verdict may be a
changed standard and not a changed world. Say which.

---

## PART 0 — Read the ground

1. **The baseline.** Find the numbers the last scan recorded and reproduce each
   with the same command. If a number that should not have moved has moved,
   record `baseline: not-reproduced`, report the delta as `field: old → new
   (command)`, and stop before PART 1. Only a revised belief closes that; an
   observation is never edited to match.
2. **The output unit is declared, not discovered.** Write what the system exists
   to produce, in units that can be counted, before measuring anything. If the
   owner's stated goal and the unit you can count disagree, say so; do not pick.
3. **The clocks.** Every date the system is working against, each from the file
   that states it.

Reality is the final authority: when your model and an observation disagree, the
observation stays and the model is revised.

## PART 0.5 — Score the previous scan before running a new one

From the directory `$RI_HOME`:

```bash
python -m packs.ri_operator.record list --type scan_recorded --entity-id "<system>" --limit 1
```

Take its `constraint`, `test`, `next_constraint`, `prediction` and
`prediction_resolves_on`, and answer with counts:

- Did the named constraint move? Cite what shows it.
- Was the test run? If not, why not is a pile for PART 2, and usually the same
  pile that produced the constraint.
- Has the prediction's date passed? Then it `held` or it `failed`. Before the
  date it is `unresolved`. No prior scan is `none`.
- If the previous constraint was removed and output did not rise, the previous
  scan was wrong that it was binding. Say so plainly. That is the most useful
  thing this command can find and it is not softened.

A scan that cannot be wrong is not an instrument.

## PART 1 — The production line

One row per stage from first input to the output unit. The stage that produces
the output unit is graded first and by name.

| # | Stage | In (count, command) | Out (count, command) | Waiting (count, oldest age) | Owner |
|---|---|---|---|---|---|

## PART 2 — Where work piles up

List every pile: work finished at one stage and not started at the next, and
decisions asked for and not given. Each with its count and the age of its oldest
item. The largest, oldest pile sits in front of the constraint.

## PART 3 — The blind-spot passes

- **A, the proxy.** For each number relied on: does it measure the thing, or a
  stand-in for the thing? A status file, a heartbeat, a dashboard and a summary
  are stand-ins. Open the records the next stage will actually consume.
- **B, the comparison.** Is every pair of compared numbers over the same cases
  and the same dates? Is a sample that grows being compared with a fixed target?
- **C, the premortem, twice (DEEP).** It is a month on and the system has been
  dark or wrong for a week and nobody saw. Once as the machinery failing; once as
  a trusted number having been wrong. What is the earliest sign, and can it be
  seen today?

## PART 4 — The comfortable-candidate gate  *(before selecting)*

Name the candidate that is most comfortable to believe: the one that puts the
problem in tooling, in an outside party, or in someone else. State it. Then argue
against your leading candidate and for the uncomfortable one as hard as the
evidence allows. Four uncomfortable candidates are always on the table:

- **(a) The owner is the constraint.** Decisions waiting, attention divided,
  standing instructions not acted on. Count the decisions waiting on the owner and
  their ages. **A scan that cannot name the owner is a failed scan.**
- **(b) The thing cannot work, and more effort does not change that.**
- **(c) The measurement is the problem, not the result.**
- **(d) The work is excellent and pointed at the wrong thing.** Clean execution
  with zero output is its signature.

Only after that argument, select.

## PART 5 — The verdict: exactly one constraint

Not "several factors". If two tie, name the tie and the one measurement that
breaks it.

- **THE CONSTRAINT** — one sentence, with its count.
- **OWNER** — `SELF` (the owner can move it today), `DEPENDENT` (it waits on
  another party; the constraint is then exposure to that party and the move is to
  reduce it, never to wait attentively), `STRUCTURAL` (it cannot be moved with
  what there is; say what to do instead).
- **THE TEST** — the cheapest observation that would show this identification is
  wrong within 48 hours, runnable without a decision from anyone and without
  spending.
- **THE PRICE** — as a count, how many units of output removing it is worth. A
  repair worth +0 is not a repair, however well tested.
- **EXPLOIT** — more output from the constraint with no new scope. If the
  constraint is about integrity or measurement, the exploit protects the standard;
  it never loosens one.
- **SUBORDINATE** — what is consuming effort and is not the constraint, set aside
  until the constraint moves.
- **NEXT CONSTRAINT** — where it moves once this one breaks. The next scan scores
  this.
- **PREDICTION** — one statement about a number, with the date it resolves.

## PART 6 — The three questions and the move

Answered against the named constraint, not in the abstract.

- **LEVERAGE:** the action that removes the constraint fastest, and whose hand it
  needs.
- **STOP DOING:** one thing being done that does not touch the constraint. One
  removal, named, with what it costs to keep.
- **ATTENTION:** the one thing that deserves the best hour today.
- **THE MOVE:** one sentence. If the number behind the move is an estimate, a
  memory or a summary, the move is to measure it. If the move is expensive to
  undo or already feels certain, its first step is `/ri-gate`, and it says so.

The move and the exploit must point at the same constraint, or the scan
contradicts itself and is reconciled before it is recorded.

## RECORD

Write the JSON to a file; every field is required:

```json
{"system": "", "mode": "DEEP", "output_unit": "", "baseline": "reproduced|not-reproduced|no-baseline",
 "previous_scan": null, "previous_outcome": "held|failed|unresolved|none",
 "constraint": "", "owner": "SELF|DEPENDENT|STRUCTURAL",
 "count_command": "", "count_result": "",
 "comfortable_candidate": "", "why_not_comfortable": "", "owner_pending": "<count and oldest age, or UNMEASURED>",
 "test": "", "price": "", "exploit": "", "subordinate": "", "next_constraint": "",
 "prediction": "", "prediction_resolves_on": "YYYY-MM-DD",
 "move": "", "stop_doing": "", "attention": "", "unknowns": []}
```

```bash
python -m packs.ri_operator.record append scan_recorded --entity-type system --entity-id "<system>" --payload @<file> --source agent:ri-scan
```

Report in one message, then **stop**:

```
SCAN            : <system>  <mode>   baseline: <...>
LAST SCAN       : <event_id or none>  prediction: <held | failed | unresolved | none>
OUTPUT UNIT     : <unit>  now: <count> (cmd)
THE CONSTRAINT  : <one sentence + count>   OWNER: <...>
COUNTED BY      : <command> → <result>
COMFORTABLE WAS : <candidate>, rejected because <...>
WAITING ON OWNER: <count, oldest age>
THE TEST        : <...>            THE PRICE: <...>
NEXT CONSTRAINT : <...>
PREDICTION      : <statement>, resolves <date>
THE MOVE        : <one sentence, whose hand>
STOP DOING      : <one thing>
UNKNOWNS        : <...>
EVENT           : <event_id>
```

## What goes wrong when this is run

1. The constraint is read off a document instead of counted.
2. Several constraints are named.
3. The comfortable candidate is chosen without the argument against it.
4. The scan starts fixing.
5. The previous scan is not scored, so nothing is learned from having been wrong.
