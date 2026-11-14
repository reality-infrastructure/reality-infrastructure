# CONTRACT: RI-OPERATOR-3 — /ri-foresight

```
status:   PARKED 2026-11-14: built, one real sheet written, nothing left to build.
          It waits on a date and is listed in contracts/queue/ri-operator-waiting.md.
          Opened 2026-11-14 on the operator's order ("use all 5 transcripts to build
          /ri-foresight"), with RI-OPERATOR and RI-OPERATOR-2 both not DONE. Third
          contract open at once on this branch, against the repository's rule; recorded.
branch:   contract/ri-operator
baseline: 802 passed, 1 failed, 1 skipped at 15e5359
on record: the scan of 2026-11-14 (event 862cb0d5) names "building or extending tools
          before the first human reply" as the thing to stop. This contract is more
          tooling. The operator ordered it after that scan was reported.
```

## Objective

The forecast journal as the eighth command: write down what is expected before the
window opens, score it against what happened, assign each miss to a cause, and revise a
belief only when the record of several misses says to. Every step is a ledger event.

## What is ported, and what is not

The source is a 1,169-line module with a 574-line companion, tied to one program's data
and to a third-party dataframe library. It is **not** copied. What is ported is its rules,
re-implemented in the pack on the standard library:

| Rule in the source | Kept |
|---|---|
| A forecast is an interval or a probability, never both; quantiles in order | yes |
| The author names the beliefs relied on, the reason, and the way it fails | yes |
| The pen is down when the window opens; a forecast written inside its window is refused | yes |
| A forecast written after its window closed is marked as written in hindsight | yes |
| A forecast is never rewritten | yes |
| Interval score (width plus penalty outside), bias in interval-widths, Brier for probabilities | yes |
| A mechanical rival built from the record itself, once five like windows exist | yes |
| A review names one cause from a closed list; a sheet where everything held is variance | yes |
| A belief is versioned; a revision carries its lesson | yes, and made stricter: see below |
| Skill against the rival; calibration; what is owed | yes |
| Splitting a dollar miss across four multiplied factors; the market-link model; per-item models; the haircut between simulated and live results | no: program-specific |

**Stricter than the source:** the source lets a belief be revised whenever a lesson is
supplied, and leaves "never revise on one sheet" to the reader. Here the revision is
refused unless the belief's own record flags it (three or more scored forecasts leaning
one way, or under half held on five or more), or evidence from outside the record is
given with `--force`.

## Why, from the five transcripts

| Transcript | Point | Where it lands |
|---|---|---|
| Musk | He interviewed thousands, then went back over the ones he got wrong to raise his own hit rate. He sets deadlines he expects to miss half the time. | The journal is that loop for any forecast; the middle value is meant to be missed high as often as low. |
| Schulman, Millidge, O'Neill | Thinking adds no information; only new observations do. One success-or-failure signal is small but clean. Many tiny updates destroy what was learned; large batches wash out noise. | Only a settled outcome changes anything, and a belief moves on a pattern of misses, not on one. |
| Brown | People inside the field keep being surprised, and one researcher shortened how far ahead he will predict from a year to three months. | Calibration is measured, not assumed, and the forecast horizon is whatever the record supports. |
| Patel | Train on history with the answer held back; predict the large run from the small one. | The mechanical rival: the record's own past windows forecast the next, and the author must beat it. |
| Naval | It is the number of iterations, not hours, that teaches. Judge the process, not the last result. | Each window is one iteration with a score; a sheet where everything held teaches nothing and is filed as variance. |

## Scope

IN: `packs/ri_operator/foresight.py`, `packs/ri_operator/events.yaml`,
`.claude/commands/ri-foresight.md`, `tests/test_ri_operator_foresight.py`,
`tests/test_ri_operator_pack.py` (command list only), `packs/ri_operator/README.md`,
this directory.

OUT: `engine/`, `ri_core/`, `rights_events/`, `forge/`, SPEC.md, NEUTRALITY.md; any new
dependency; any file outside this worktree.

## Acceptance

- [ ] `python -m engine.validate ri_operator` exits 0.
- [ ] Full suite: baseline plus new tests, the same one failure.
- [ ] Engine diff against `contract/irv-harness`: 0 lines.
- [ ] Banned nouns: none across the pack and all eight commands.
- [ ] The five known answers in PREREG-3.md hold.
- [ ] One real sheet written before its window opens, on the ledger and verified.
- [ ] That sheet settled after its window closes, reviewed with a cause, and the rival
      compared. This cannot be met before the window closes. Until then: NOT DELIVERED.

## Build and run report — 2026-11-14

Built: `packs/ri_operator/foresight.py` (about 330 lines, standard library only), four
event types (`belief_stated`, `forecast_written`, `forecast_settled`, `sheet_reviewed`),
`.claude/commands/ri-foresight.md`, `tests/test_ri_operator_foresight.py` (17 tests).

- [x] `python -m engine.validate ri_operator`: `OK`, 23 event types.
- [x] Full suite: `1 failed, 819 passed, 1 skipped` (777 + 25 pack + 17 journal; the same known failure).
- [x] Engine diff against `contract/irv-harness`: 0 lines.
- [x] Banned nouns: none across the pack and all eight commands.
- [x] Known answers 1 to 5 held (`test_known_answer_*`).
- [x] One real sheet written before its window opened: three beliefs and three forecasts
      for `support-outsourcing`, window 2026-11-15T00:00Z to 2026-11-21T00:00Z, written
      2026-11-14T17:11Z. Ledger indexes 11 to 16; all six events re-verified.
- [ ] Settled, reviewed and compared with a rival: NOT DONE. The window closes
      2026-11-21T00:00Z. The record is a rival only after five like windows.

The sheet, as written:

| Forecast | Value | Belief it rests on |
|---|---|---|
| Human replies in the prospect log (surroundings sheet) | 0 / 1 / 3 | cold-reply-rate (0.4) |
| Rows marked sent, cumulative | 15 / 30 / 60 | sends-in-bursts (0.6) |
| P(signed clients >= 1) | 0.05 | pilot-needs-chain (0.7), cold-reply-rate |

Disclosures:

1. **The forecasts are the agent's.** No person wrote or confirmed them. They rest on
   counts taken today and on the week plan's own targets.
2. **This is one sheet, unsettled.** Nothing about calibration or skill is known. The
   scoring, review, revision and rival rules have run only on test fixtures.
3. **The journal is stricter than its source** on belief revision (CONTRACT-3, above).
   That choice has not been tried on a real record.
4. **Not ported:** the split of a miss across multiplied factors, the link between
   surroundings and result in units, per-item models, and the discount between simulated
   and live results. A buyer who needs those gets them as later work, not from this file.
5. The command tells the author to forecast the surroundings first. That order is
   written in the command and is not enforced by the journal.

Delivery status: ri-foresight NOT DELIVERED until the sheet is settled and reviewed on or
after 2026-11-21.
