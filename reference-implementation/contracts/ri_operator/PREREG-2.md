# PREREG: RI-OPERATOR-2

```
FROZEN at the commit that adds this file, before any change to the pack, the commands
or the tests for /ri-scan and /ri-week. Later changes are dated amendments below.
This time engine/validate.py, engine/events.py and engine/schema.py were read first.
```

## Sources, hashed at copy time into PROVENANCE.md

- `/ri-scan`: `~/ladder/rules/invariant-scan.md`; `~/hyperliquid/.claude/commands/morning.md`.
- `/ri-week`: `~/hyperliquid/.claude/commands/week.md`; `~/rich/scan/prompts/disprove.md`
  (the tripwire test only).

## Closed vocabulary

- Scan mode: `DEEP`, `STANDARD`.
- Outcome of the previous scan's prediction: `held`, `failed`, `unresolved`, `none`.
- Watch mark: `ACT`, `MONITOR`.
- Blind-spot pass: `premortem`, `dependency`, `cascade`, `clock`, `whisper`,
  `unpriced-branch`, `unseen-fact`.
- Clock status: `open`, `closed`.

## Known answers, declared before the build

1. A `scan_recorded` event with no `count_command` is refused at append. A constraint
   that was read and not counted cannot be recorded.
2. A `watch_set` event with `weeks_carried` of 3 is refused at append. An item is not
   carried a third week: it is dropped or it becomes the repeater.
3. A `scan_recorded` event whose `prediction_resolves_on` is not a ten-character date is
   refused at append. A prediction with no date cannot be scored.

If any behaves otherwise: STOP and report.

## Banned nouns

The list in PREREG.md, substring match, applied to the pack and to all seven commands.

## Amendments

(none)
