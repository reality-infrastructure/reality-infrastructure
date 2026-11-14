---
description: The weekly review and blind-spot scan — count the week from the ledger, grade the moves the scans wrote, name the repeater, the miss and the loop, run seven passes for what nothing is tracking, and set a watchlist of at most five tripwires plus the clocks nobody is watching. All of it recorded on the ledger.
argument-hint: "<system> [YYYY-Www]  (default: the week that just ended)"
---

Review: **$ARGUMENTS**

Why this command exists: work now runs for longer than anyone has time to check
it, so what fails is rarely the thing being watched. Trouble shows up small before
it shows up large, and one safeguard is never enough. The daily scan decides what
is done; this decides what is looked at.

It reads, counts and records. It changes nothing in the system under review and
proposes no rule change. Never reassure. Unknown is a valid answer. A number
without its command or file is not written.

All commands run from the directory `$RI_HOME`.

---

## 1. The sheet first, nothing before it

Count the week from the ledger and from nothing else. `<monday>` is the first day
of the week under review.

```bash
python -m packs.ri_operator.record list --entity-id "<system>" --since <monday>T00:00:00Z
python -m packs.ri_operator.record list --type watch_set --entity-id "<system>" --limit 10
python -m packs.ri_operator.record list --type clock_set --entity-id "<system>" --limit 50
python -m packs.ri_operator.record list --type week_reviewed --entity-id "<system>" --limit 1
```

Write down: scans run, moves written, gate verdicts and what each ruled,
constraints named, judgments run, the last review's repeater and bet, the open
watchlist, the open clocks. If a count cannot be had, it is `UNKNOWN`.

## 2. Grade the week's moves

For each `scan_recorded` event of the week, read its `move` and look for evidence
that it happened: a commit, a file, a later event, a message. One line each:

```bash
python -m packs.ri_operator.record append move_graded --entity-type system --entity-id "<system>" --payload '{"scan_event_id": "<id>", "executed": "Y|N", "evidence": "<what shows it, or the obstacle>", "waited_on": "<whose hand, or nobody>"}' --source agent:ri-week
```

No evidence is N. A move that waited on a person and did not happen is N with
that person named. It is not excused.

## 3. Name three things, one line each

- **THE REPEATER:** the item named again and again and not done that costs the
  goal most. What it has cost, in the sheet's own numbers, and whose hand it
  needs.
- **THE MISS:** what reality did this week that no scan predicted. If the same
  cause owns two weeks running, say so.
- **THE LOOP:** did the routine itself run? Late starts, refused steps, errors,
  scans that were skipped. A step refused on every run is not a step; name it for
  removal or for the permission it needs.

## 4. The seven passes

Aimed at the whole system, not at the known constraint. The scans already track
the constraint; do not list it again. Look for what is consequential and on no
sheet. Look before writing: every item has a file, a log line or a command behind
it, or it is marked `speculation`.

1. **PREMORTEM.** It is thirty days on and the system has been dark or wrong for a
   week and nobody saw. Write the story twice: once as the machinery failing, once
   as a number everyone trusted having been wrong. What is the earliest sign, and
   is it visible today?
2. **DEPENDENCY.** What has always just worked: the machine that must be awake,
   the bill that must be paid, the key and its expiry, the one login, the one
   address. Which have no backup?
3. **CASCADE.** What takes out two things at once?
4. **CLOCK.** Anything with a date that is not already an open clock: a result due
   to be read, a decision that expires, a renewal, storage running down at the
   measured rate.
5. **WHISPER.** What happened once in the logs and was explained away?
6. **UNPRICED BRANCH.** Which pending result has no written answer for the case
   where it comes back bad? A good result that would pull attention off the main
   thing is priced too.
7. **UNSEEN FACT.** One structural fact that has been true so long nobody sees it.

## 5. Test each item before it goes on the list

Check in this order and stop at the first that removes it:

1. **Already managed.** Is there a guard, a check or a rule that already catches
   it? Search for it. If so, drop the item and name the file.
2. **Not real.** Does the file or number it cites say what the item says? Open it.
3. **Same root.** Is the item's evidence the same source as the thing it doubts (a
   heartbeat cited to show a feed is alive)? Keep it only with an independent
   source; otherwise mark `speculation`.
4. **Cannot fire.** Can the tripwire be observed, does its threshold sit on the far
   side of today's value, and would it fire before the damage? A tripwire already
   past its line is a fault, not a tripwire: say so. If it cannot fire, the
   tripwire is null and the item is `speculation`.
5. **Duplicate.** Two items that one event would trip are one item.
6. **Not consequential.** If it happened tomorrow, would anything that matters
   change?

## 6. The watchlist: five rows at most

Ranked by how probable times how much is lost. One event each:

```bash
python -m packs.ri_operator.record append watch_set --entity-type system --entity-id "<system>" --payload '{"week": "YYYY-Www", "blind_spot": "", "found_by": "premortem|dependency|cascade|clock|whisper|unpriced-branch|unseen-fact", "tripwire": "<earliest observable sign, or null>", "tripwire_source": "<file or command, or null>", "mark": "ACT|MONITOR", "action": "<cheapest de-risking act>", "whose_hand": "", "weeks_carried": 0, "basis": "evidence|speculation"}' --source agent:ri-week
```

An item that was on last week's list with its tripwire untripped and nothing done
is `weeks_carried: 1`. One that would be carried a third week is refused by the
ledger: it is dropped, or it is the repeater.

Each silent clock found in pass 4, and each one that has been met:

```bash
python -m packs.ri_operator.record append clock_set --entity-type system --entity-id "<system>" --payload '{"what": "", "due": "YYYY-MM-DD", "source": "<file>", "status": "open|closed"}' --source agent:ri-week
```

## 7. Once a month, or after a hard shift

On the first review of a month, or in the week of a shutdown, a budget reached, a
cutover or new money: run `/ri-gate` on the action "keep running the system as it
stands for another month", through an agent that has not seen this session.

## 8. Rep check

If last week's review named a repeater and it is still open with no graded move
and no decision against it, say this first: the review ran and its output was not
used. A review whose output is another review is the avoidance.

## RECORD, then report

```bash
python -m packs.ri_operator.record append week_reviewed --entity-type system --entity-id "<system>" --payload '{"week": "YYYY-Www", "scans": 0, "moves_written": 0, "moves_executed": 0, "repeater": "", "miss": "", "loop": "", "prior_repeater_open": "yes|no|no-prior-week", "bet": ""}' --source agent:ri-week
```

Under 150 words, no encouragement:

```
WEEK         : <YYYY-Www>  <system>
EXECUTION    : <moves executed> of <moves written>; scans <n>
THE REPEATER : <...>   (still open from last week: yes | no | no prior week)
THE MISS     : <...>
THE LOOP     : <...>
WATCHLIST    : <each row: blind spot | tripwire | ACT or MONITOR | whose hand>
NEAREST CLOCKS: <two>
THE ONE I'D BET ON: <the single item most likely to matter>
EVENTS       : <event_ids>
```
