---
description: The forecast journal loop — settle what came due, assign each miss a cause, revise a belief only where its record says to, and write the next sheet before its window opens, the surroundings first. Every step is a ledger event; a forecast written late or rewritten is refused.
argument-hint: "<subject>  (the system the forecasts are about)"
---

The subject: **$ARGUMENTS** (none given: ask which system, and stop.)

Why this command exists: thinking harder adds no information; only a new
observation does. The observation that teaches most is the gap between what was
written down beforehand and what happened. It is the count of scored forecasts
that improves judgment, not the hours spent, and one result is never a reason to
change a belief.

This command changes nothing in the system it forecasts. It reads, runs read-only
commands, and writes journal events. All commands run from the directory
`$RI_HOME`.

**The order of the steps is the discipline. Do not look at how the current window
is going before step 4 is done for any window about to open.**

---

## 1. Read the journal, then settle what came due

```bash
python -m packs.ri_operator.foresight report --subject "<subject>"
```

For each line under `SETTLEMENT OWED`, measure the metric now, with a command,
over exactly the window the forecast names. Then:

```bash
python -m packs.ri_operator.foresight settle --fid "<fid>" --actual <number> --evidence "<the command or file the number was read from, and when>"
```

- The number is read, not remembered. No command, no settlement.
- If the metric can no longer be measured, do not settle it with a guess. Say so
  in the report; the forecast stays open and counts as owed.
- A settlement before the window closes is refused. So is a second one.

## 2. Review every sheet the report says is owed

One review a sheet. The cause is one of:

- `variance`: every forecast held. Nothing is learned and nothing is changed. The
  journal refuses any other cause on such a sheet unless `--force` is given with
  evidence from outside the sheet.
- `model`: a belief about how the system behaves was wrong.
- `overfit`: the figure the forecast leaned on was a selection, and reality gave
  it back.
- `execution`: the plan was right and carrying it out cost more than expected.
- `ops`: stoppages, restarts, something not built or not run.
- `regime`: the world of the window was not the world of the record. Say what
  changed, with its date.
- `data`: the measurement or the instrument was broken.

Before writing the lesson, read in this order and say which of the three owned
the miss:

1. **The surroundings.** Was the forecast of the conditions wrong (step 4a)? If no
   forecast of the surroundings stood before the window, their share is unknown,
   not zero.
2. **The rule.** Given the conditions that occurred, did the method do what the
   belief said it would?
3. **The carrying-out.** Was the method right and the doing of it late, partial or
   costly?

Then read the premortem written with the forecast that missed. Did the miss
arrive by the road that was named? A miss by an unnamed road is the more valuable
one; say so in the lesson. Write the lesson as one that changes a number next
time:

```bash
python -m packs.ri_operator.foresight review --sheet "<sheet>" --cause <cause> --lesson "<surroundings, rule or carrying-out; the factor; what the next sheet does differently>"
```

## 3. Revise the model only where the record says to

Under `OWED`, a belief marked `REVISE` has had three or more scored forecasts miss
the same way; `TOO NARROW` has held under half the time on five or more. Only
those are revised, with a new version that carries the lesson:

```bash
python -m packs.ri_operator.foresight belief --key <key> --statement "<new>" --because "<evidence>" --conf <0 to 1> --lesson "<why>"
```

- **Never revise on one sheet.** The journal refuses a revision its own record
  does not flag. `--force "<evidence>"` exists for evidence from outside the
  record, and the event says it was forced.
- Read the `SKILL` line. If the author does not beat the record, the next sheet
  starts from the record's interval and departs from it only with a stated reason.
- A belief that would change what the system should do is a proposal for whoever
  owns the system. It is named in the report. It is never acted on here.

## 4. Write the next sheet before the window opens

Every subject has, at all times, a sheet for the next window.

**a. The surroundings first.** A sheet named `<sheet>-env`, same window: the two
or three conditions the result depends on and that the system does not control.
Forecast those before forecasting the result.

**b. The record's forecast, if it exists.**

```bash
python -m packs.ri_operator.foresight persist --subject "<subject>" --sheet "<sheet>" --metric <metric> --start <ISO> --end <ISO>
```

Before five like windows are settled this prints how many there are, and writes
nothing.

**c. The author's sheet.** A new belief is written first, with what it rests on:

```bash
python -m packs.ri_operator.foresight belief --key <key> --statement "<what is believed>" --because "<the observation behind it>" --conf <0 to 1>
```

Then each metric, as an 80 percent interval or as a probability:

```bash
python -m packs.ri_operator.foresight forecast --subject "<subject>" --sheet "<sheet>" --metric <metric> --start <ISO> --end <ISO> --q=<lo>,<mid>,<hi> --beliefs <key1,key2> --why "<reason, and where it departs from the record>" --premortem "<the way this number fails, and what that would mean>"
python -m packs.ri_operator.foresight forecast --subject "<subject>" --sheet "<sheet>" --metric <metric> --start <ISO> --end <ISO> --p <0 to 1> --op ">=" --x <threshold> --beliefs <key> --why "..." --premortem "..."
```

- Write `--q=lo,mid,hi` with the equals sign; a negative low is otherwise read as
  a flag.
- The middle value is the one you expect to be missed high as often as low. An
  interval is meant to hold four times in five. If yours always hold, they are too
  wide, and the journal will say so.
- Where quantities multiply to a total, forecast the factors and the total, and
  check that the middles multiply out.
- **The pen is down once a window opens.** A forecast written inside its window is
  refused. One written after the window closed is stored as hindsight and never
  counts toward skill. A sheet that was not written in time is not written at all:
  say so in the report. Never pass an earlier time.
- A forecast is never rewritten.

## 5. Report

Under 120 words: what was settled and whether it held; whose miss it was (the
surroundings, the rule, the carrying-out); the lesson; coverage against the 80
percent aim; skill against the record, or how many windows remain before the
record is a rival; what is open and when it closes; any belief flagged, and any
proposal that belongs to the system's owner.

```
SETTLED   : <n> forecasts; held <n>
THE MISS  : <surroundings | rule | carrying-out>: <factor>
THE LESSON: <one line>
CALIBRATION: held <x>% of <n> (aim 80%), mean bias <+/-x>
SKILL     : <+/-x on n pairs | record is a rival after <k> more windows>
THE MODEL : <beliefs flagged, revised, or unchanged>
OPEN      : <sheet, closes when>
EVENTS    : <event_ids>
```
