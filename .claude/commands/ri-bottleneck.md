---
description: Find and remove the single binding constraint of any system — measure first, falsify before fixing, verify against the baseline, then record the result on the ledger. Works on code, pipelines, data, process or people.
---

Run the constraint-removal protocol on: **$ARGUMENTS**

(If no argument was given, run it on the system currently in front of you.)

Your output is **throughput delta, verified**. Nothing else counts. A run that ends
in "the constraint is X, it is outside my authority, here is the memo" is a
successful run. A run that ends in a plausible fix with no before/after number is a
failed run, even if the code came out better.

Why this command exists: attention spent anywhere but the limiting factor buys
nothing, and a report of improvement that carries no measurement cannot be checked
by the person who has to accept it.

---

## INVARIANTS — these hold in every phase

1. **No number without a command.** Every quantity carries the exact command that
   produced it and when it was run. If you did not run it, the value is `UNKNOWN`.
   An estimate is allowed only when labelled `EST` with its basis.
2. **Disk beats memory.** Re-read the source of truth this run. Earlier context,
   earlier sessions and documentation are hypotheses, not evidence.
3. **Measure before you name.** No bottleneck is named before Phase 2 is complete.
   Reading code and concluding "this looks slow" is banned.
4. **WIP = 1.** One constraint is in play at a time. Everything else goes to the
   PARKING LOT unfixed.
5. **One change at a time.** If you cannot say which edit moved the number, you did
   not measure anything.
6. **Local gains are waste.** Improving a non-constraint tenfold moves throughput by
   nothing. If you did it, report it as waste.
7. **Andon cord.** STOP and report on any of: an irreversible action you were not
   explicitly authorised for; production data or state at risk; the measurement is
   itself perturbing the system; scope has drifted outside what was named.

---

## PHASE 0 — Scope contract and state  *(no fixing)*

Write these four lines before touching anything. If you cannot fill one, ask: every
later phase is meaningless without it.

```
SYSTEM      : <the bounded thing, entry point to exit point>
UNIT OF FLOW: <what must come out the end: orders, rows, requests, resolved tickets>
THROUGHPUT  : <units> per <time>, measured by: <exact command or observation>
TARGET      : <the rate that would make this not a problem>
```

Then classify the state and take its one entry move.

| State | Signature | Entry move |
|---|---|---|
| **DARK** | No timing, no logs, no counters | Instrument first, with the cheapest timing at each stage boundary. |
| **DEAD** | Not running at all | Throughput is 0. The constraint is whatever prevents it starting. |
| **GATED** | Runs, but a hard gate is shut: a credential, an approval, a rule, money | A closed gate multiplies everything by zero. Go straight to Phase 5 with the gate as the constraint. |
| **STARVED** | Stages sit idle waiting for input | The constraint is upstream of what you were shown. Widen scope and redo Phase 0. |
| **SATURATED** | A resource pinned near 100% | Strong candidate. Still must survive Phase 4. |
| **THRASHING** | The same work goes round repeatedly | Suspect a rework loop, not capacity. Measure yield per pass. |
| **SLOW-BUT-HEALTHY** | Everything works, nothing is pinned | Full Phases 1 and 2. |
| **UNSCOPED** | You cannot name the unit of flow | Stop and get Phase 0 answered. |

## PHASE 1 — Map the value chain  *(observe only)*

Walk the path one unit of flow takes. Every row needs a source of truth you
**actually opened**.

| # | Stage | Source of truth (path / command / person) | In | Out | Owner |
|---|---|---|---|---|---|

- A stage nobody owns and nobody can explain is marked `ORPHAN` and is the
  highest-suspicion row.
- Each stage is explained in one plain sentence, or you do not understand it yet.
- Where the source of truth is a person, say so and state what you would ask. Do
  not simulate their answer.
- Mark every queue, buffer, retry, sleep, batch window, scheduled gap, manual
  hand-off and approval step. That is where time goes, and it is invisible in
  code review.

By substrate: code is run and timed, not read; a data pipeline is counted at each
stage boundary; operations are the live process, not the config file; a process
with people in it is its artifacts in timestamp order, and its cycle time is
wall-clock.

## PHASE 2 — Measure  *(still no fixing)*

Per stage: cycle time as p50 / p95 / max, wait time, utilisation, yield, and the
capacity ceiling. Then:

```
STAGE SHARE = stage cycle time / total end-to-end cycle time
```

**Amdahl guard:** a stage under about 20% share cannot be the constraint. Kill
those candidates in writing now.

If real numbers cannot be had, write `MEASUREMENT BLOCKED: <why>` and stop. Do not
go on by intuition.

## PHASE 3 — Name the single constraint

One sentence with the number attached, then its class.

| Class | Signature | Fix direction |
|---|---|---|
| capacity | Pinned resource, queue growing | More, faster or parallel — last resort |
| latency | Nothing pinned, wall clock high | Remove waits |
| serialisation | Idle resources, work in lockstep | Break the dependency chain |
| queue | Wait time far above work time | Reduce work in progress; do not add capacity |
| rework | Yield below 1 | Fix the defect source upstream |
| starvation | Stage idle | The real constraint is upstream |
| cadence | Work waits for a window | Shrink the window |
| policy | Only a rule stops it | Change the rule — usually free, usually the largest win |
| knowledge | One person or one unknown gates everything | Escalate |
| gate | Hard zero | Outranks everything else |

State also **what becomes binding next** once this one is removed.

## PHASE 4 — Falsify it before fixing it

Write a prediction that could fail:

> If X is the constraint, relieving X by k% raises end-to-end throughput by about
> `k% × share`, **and** adding capacity anywhere else changes nothing.

Test it the cheapest way: starve a different stage and confirm nothing moves; stub
X and confirm something does; arithmetic on the measured numbers. If the prediction
fails, say so in one line and return to Phase 3.

## PHASE 5 — Remove it, in this order

1. **Question the requirement.** Whose requirement is it, by name? One owned by
   "the system" or "best practice" is unowned.
2. **Delete it.** Confirm nothing consumes the output first.
3. **Simplify.** Fewer branches, fewer hops, less work in progress, smaller batches.
4. **Accelerate.** Only now.
5. **Automate.** Last. Automating a step that should have been deleted makes the
   wrong thing permanent.

Re-measure with the Phase 0 command after each single change.

## PHASE 6 — Verify, then re-identify

Re-run the exact Phase 0 command under the same conditions and report
`before → after`. If throughput did not move, the hypothesis failed: say so, log
the change as waste, return to Phase 3. If it moved, name the new constraint and
say whether another cycle is worth it.

## STOP CONDITIONS — reaching one is a successful run

- Target met.
- The constraint is a gate, a policy, a person, money or a matter of law: write
  the escalation memo (what is blocked, what decision unblocks it, who owns it,
  what each day costs) and stop. Do not route around a closed gate.
- The next constraint costs more to remove than it buys.
- Measurement blocked.
- Andon condition.

## RECORD — the run is not finished until this is done

Write the output contract as a JSON object to a file, with every field present and
`UNKNOWN` where nothing was measured:

```json
{"system": "", "state": "", "unit_of_flow": "", "throughput_command": "",
 "throughput_before": "", "throughput_after": "", "constraint": "",
 "constraint_class": "", "prediction": "", "prediction_held": "yes|no|not-tested",
 "action": "", "result": "", "next_binding": "", "parking_lot": [], "unknowns": []}
```

Then, from the directory `$RI_HOME`:

```bash
python -m packs.ri_operator.record append constraint_named --entity-type system --entity-id "<short-system-name>" --payload @<file> --source agent:ri-bottleneck
```

Report the one-screen ledger below and the `event_id` the command printed. If the
append is refused, report the refusal verbatim; do not reshape the payload to make
it pass.

```
SYSTEM      : ...
STATE       : ...
THROUGHPUT  : <before> → <after>   (cmd: ..., run: <when>)
CONSTRAINT  : <one sentence + number>   [class: ...]
FALSIFIED?  : <the prediction, and whether it held>
ACTION      : <the single change actually made, or none>
RESULT      : <verified delta, or "no movement — hypothesis failed">
NEXT BINDING: ...
PARKING LOT : ...
UNKNOWNS    : ...
EVENT       : <event_id>
```

## BANNED

- Naming a bottleneck from reading instead of measuring.
- Reporting a number no command produced.
- Changing several things at once and claiming the improvement.
- Optimising a non-constraint because it was easy to reach.
- "Should be faster now" with no after-measurement.
- Simulating what a person would have said.
- Continuing past a stop condition because the run feels unfinished.
