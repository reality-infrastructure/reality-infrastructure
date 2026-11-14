---
description: Run the eight-step judgment checklist on a decision before committing to it — any consequential build, spend or irreversible action — and record the run on the ledger.
---

Run the judgment checklist on: **$ARGUMENTS**

(If no argument was given, run it on the decision currently on the table.)

Why this command exists: the more a decision is multiplied by tools and by other
people's effort, the more a small difference in judgment is worth, and the only
judgment that can be reviewed later is one that was written down before the
outcome was known.

Work the eight steps **in order**. REALITY before INVERT stops you inverting a
fantasy. INVERT before the rest stops you polishing a thing that can ruin you.

---

**1. REALITY — One fact that would prove me wrong. Have I looked?**
Name the single most damaging fact, then go and look. A step that produces no
tool call is not this step. If the fact cannot be checked, say so and lower
confidence; do not replace a look with an argument.
Root check: does the disproving fact come from a root independent of the claim? A
source that shares the claim's root (a page built from the record it is checking,
the person who made the claim, a re-run on the same data) is one witness heard
twice. Name a different root, or mark the claim UNTESTABLE.

**2. INVERT — How does this fail? Can the downside ruin me?**
Describe the failure mechanism, not a vague risk. Ruin means cannot continue:
money gone, account closed, reputation spent, data destroyed. If ruin is
reachable, STOP, or gate the action behind the specific control that removes the
ruin channel and name that control.

**3. CIRCLE — Is this inside what I actually know?**
Separate what is measured from what is assumed. Name the load-bearing assumption
nobody has verified. Shrink the claim to what survives, or defer.

**4. INCENTIVES — Who profits from my believing this, including me?**
Answer for yourself first. A good result that arrives exactly when it was wanted
is the highest-risk result there is. Then the counterparty, the platform, the
subsidy, the sunk cost.

**5. PROBABILITY — An honest percentage. Am I judging the process or the last outcome?**
Give a number for each distinct claim. Say whether the finding survives
correction for how many things were tried. Judge the process apart from how this
draw landed.

**6. OPPORTUNITY COST — The best other use of this money, time or attention.**
Name the specific alternative and why it loses, or concede it wins. The
highest-value hour is usually spent checking the load-bearing assumption from
step 3, not extending what already works.

**7. DOOR — Reversible? Decide fast at 70%. Irreversible? Slow down.**
Sort every part of the decision into reversible and irreversible. Do the
reversible part now. Gate the irreversible part explicitly. Do not pace the whole
decision to its slowest part.

**8. EMOTION — Am I hot?**
Check for momentum, relief, vindication or the pull of a streak. If hot: ship the
method, put the number in a drawer. Name what goes in the drawer and what event
takes it out.

---

Rules:

- Run this unprompted before any consequential decision, not only when asked.
- Steps 1 and 6 need evidence. If you did not look, write "did not look" and carry
  the uncertainty forward.
- Reaching a stop or a gate is a successful run.
- The irreversible part and anything that changes how much of someone's money or
  calendar is at risk go back to the person who owns them. This command does not
  decide those; it prepares them.
- One screen. A checklist, not an essay.

## RECORD — the run is not finished until this is done

Write a JSON object to a file:

```json
{"decision": "", "disproving_fact": "", "looked": true, "independent_root": "",
 "ruin_reachable": false, "load_bearing_assumption": "", "who_profits": "",
 "probability": "", "best_alternative": "", "reversible_part": "",
 "irreversible_part": "", "hot": false,
 "outcome": "PROCEED|PROCEED-REVERSIBLE-PART|GATED|DEFER|STOP"}
```

`looked` is true only if step 1 made a tool call that could have returned the
disproving fact. `independent_root` is the source that was opened, or `UNTESTABLE`.

Then, from the directory `$RI_HOME`:

```bash
python -m packs.ri_operator.record append judgment_run --entity-type decision --entity-id "<short-decision-name>" --payload @<file> --source agent:ri-judgment
```

Report the eight lines, the outcome, and the `event_id` the command printed. A
refused append is reported verbatim.
