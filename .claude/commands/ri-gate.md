---
description: The disconfirmation gate on one action that is expensive to undo, or that already feels certain — the author writes down what it rests on, then an agent that did not build it tries to kill it. PROCEED, VERIFY-FIRST, RESTRUCTURE or HOLD, both halves recorded on the ledger.
---

The action: **$ARGUMENTS** (none given: the action on the table.)

Why this command exists: agents that work together tend to agree with each other,
and a second agent that read the first one's notes is the first agent again. A
check counts only when it comes from someone with no stake in the answer and no
view of the author's reasoning.

**When it fires.** Before an irreversible act, before a proposal goes to whoever
rules on it, before data is deleted, and whenever the session is already certain.
A cheap, reversible, uncertain act gets no gate: do it. If running the gate has
become the way to avoid the act, say that and go.

**It changes nothing.** The gate reads and records. It does not perform the
action, and its verdict does not decide anything that belongs to a person: money,
budgets, rules and irreversible acts stay theirs whatever it returns.

---

## Half one — the author states the action  *(this session)*

List every assumption the action rests on. For each one: `VERIFIED` (by a command
or a file read now, named in `evidence`) or `BELIEF`. Mark the load-bearing ones.
List the roots the evidence comes from. Say whether any urgency is `stated` by
someone outside, `inferred` by you, or `none`.

Write it as a JSON object to a file, with no argument for the action and no
conclusion in it:

```json
{"action": "<one sentence>", "author": "<who built it>",
 "assumptions": [{"statement": "", "status": "VERIFIED|BELIEF", "evidence": "", "load_bearing": true}],
 "evidence_roots": ["<each distinct source>"], "urgency": "stated|inferred|none"}
```

From the directory `$RI_HOME`:

```bash
python -m packs.ri_operator.record append gate_requested --entity-type action --entity-id "<short-action-name>" --payload @<file> --source agent:author
```

Keep the `event_id`. From here on the author says nothing more about the action.

## Half two — the disprover rules  *(never this session)*

Use the first route that is available.

**Route A, the fenced agent.** It can read only the event log.

```bash
python -m engine.run ri_operator/disprover --input '{"request_event_id": "<event_id>"}'
python -m engine.replay <run_id>
```

This calls a model provider and costs money. Do not run it without the owner's
word that the spend is allowed.

**Route B, a fresh subagent.** Hand a new subagent the block below and the
`event_id`, the paths it may read, and none of your conclusions. Report its
verdict unedited.

> You are the disprover. Someone else wrote an action and what it rests on. Your
> job is to kill it before reality does. Do not reassure. An unknown stays
> unknown. You may read and run read-only commands; you change nothing.
>
> Read the request event. Do not agree by reading what the author read: for each
> load-bearing assumption, go to a source the author did not cite.
>
> **Pass 1, the eight checks**, each yes or no with its evidence:
> - G1 root: is the evidence from a source the claim does not share?
> - G2 falsifiable: could the check have returned a disproof?
> - G3 frozen: were the rule, the population and the reporting line written
>   before the result?
> - G4 population: is every compared number over the same cases and dates?
> - G5 null: is a missing value being read as a value?
> - G6 contradiction: was a disagreement closed by dropping a source?
> - G7 time: is the data as old as it is being treated?
> - G8 required against attainable: does the consequence need more confidence
>   than these sources can give?
>
> **Pass 2, the premortem.** It is some weeks on and this was a visible failure.
> Four to six stories with root causes, covering: a wrong assumption;
> self-deception (the number was tuned to the wish); a single point outside
> control; building more while the real problem sat untouched; a leak of money,
> keys or the record's integrity; a person's decision that never arrived. Rank
> the two most likely, and weight the one nobody would notice above the visible
> ones.
>
> **Pass 3, self-deception.** Where is the wanted result? Would a disproof be
> reported as it lands? Who gains if this is right, the builder included?
> Tripwire: a method changed after its result was seen is the failure in
> progress.
>
> **Pass 4, the reversal.** What would have to be undone? Pre-commit: "if
> <specific observable evidence> appears, <specific undoing>".
>
> **Pass 5, the fallback from calm.** The next move if it fails, chosen now. The
> one mitigation available today that attacks the top failure mode.
>
> **The verdict rule.** A load-bearing BELIEF, or G1, G2, G5 or G7 failing:
> VERIFY-FIRST. G3, G4 or G6 failing: RESTRUCTURE. G8 failing: HOLD. Otherwise
> PROCEED. The most severe that applies wins: HOLD, RESTRUCTURE, VERIFY-FIRST,
> PROCEED.
>
> Write the verdict as JSON and append it from `$RI_HOME`:
>
> ```json
> {"request_event_id": "", "verdict": "", "failed_checks": ["G1"],
>  "top_failure_mode": "", "reversal_trigger": "", "de_risking_move": "",
>  "run_by": "agent:fresh-subagent"}
> ```
>
> ```bash
> python -m packs.ri_operator.record append gate_verdict --entity-type action --entity-id "<same name as the request>" --payload @<file> --source agent:disprover
> ```

If neither route is available, the gate did not run. Say so; do not rule on your
own action.

---

## Output

```
REQUEST EVENT            : <event_id>
ASSUMPTIONS TO VERIFY    : <load-bearing beliefs, each with the command that checks it, or none>
G1-G8                    : <the ones that fail, with evidence, or all hold>
TOP 2 FAILURE MODES      : <ranked; the self-deception one flagged>
THE HONEST-FAILURE FALLBACK: ...
THE REVERSAL TRIGGER     : <if X appears, undo Y>
TODAY'S DE-RISKING MOVE  : <one act, and whose hand>
VERDICT                  : PROCEED | VERIFY-FIRST | RESTRUCTURE | HOLD
VERDICT EVENT            : <event_id>   RUN BY: <route A run_id, or route B>
```

A verdict other than PROCEED is a successful run.
