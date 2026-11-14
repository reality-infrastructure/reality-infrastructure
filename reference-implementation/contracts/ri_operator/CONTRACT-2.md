# CONTRACT: RI-OPERATOR-2 — /ri-scan and /ri-week

```
status:   CLOSED 2026-11-14 on the operator's order ("close and push the five") for
          ri-scan, delivered. ri-week is not delivered and moves to
          contracts/queue/ri-operator-waiting.md. See CLOSE.md.
          Opened 2026-11-14 on the operator's order ("use all 5 transcripts to build
          /ri-scan and /ri-week"), while RI-OPERATOR is not DONE (ri-pack undelivered,
          branch unpushed). The repository's rule is one contract at a time; the operator
          has overruled it for this contract and that is recorded here, not hidden.
branch:   contract/ri-operator (same branch, same worktree)
baseline: 792 passed, 1 failed, 1 skipped at b3528d0
```

## Objective

Two more operator commands in the `ri_operator` pack, each ending in ledger events:

- `/ri-scan`: a diagnosis-only scan of one system that names exactly one binding
  constraint, counted and not read, scores the previous scan before it runs, and ends
  with one move and a prediction that resolves on a date.
- `/ri-week`: the weekly review. It counts the week from the ledger, grades the moves the
  scans wrote, runs seven blind-spot passes, and sets a watchlist of at most five
  tripwires and the clocks nobody is watching.

## Why, from the five transcripts

| Transcript | Point | Where it lands |
|---|---|---|
| Musk | Attention goes to the limiting factor and nowhere else. A review is unprepared, so nobody arrives with a polished story. Points are plotted week over week to see whether they converge. | `/ri-scan` names one constraint from counts taken now; `/ri-week` plots the week against the last. |
| Brown | The metrics looked good and were not measuring the thing. Systems now run longer than anyone has time to evaluate them. Deception shows up small before it shows up large. Never rely on one safeguard. | The proxy pass in `/ri-scan`; the whisper, cascade and dependency passes in `/ri-week`. |
| Schulman, Millidge, O'Neill | Choosing the objective is the human part. A model looks brilliant for a month and then its weak spots show. A judge with a habit gets exploited. | The output unit is declared before measuring; the scan scores its own past predictions; the comfortable candidate is argued against. |
| Patel | Progress follows what can be verified; a proxy lets work be checked before it is accepted. | Every figure carries its command; a scan with no count behind its constraint is refused at append. |
| Naval | Iterations teach, hours do not. Compounding needs the loop to keep running. Judgment is knowing the long-term consequence. | Each scan is one scored iteration; the week checks whether the loop itself ran. |

## Scope

IN: `packs/ri_operator/events.yaml` (new types), `packs/ri_operator/record.py` (a `list`
subcommand to count events), `.claude/commands/ri-scan.md`, `.claude/commands/ri-week.md`,
`tests/test_ri_operator_pack.py`, `packs/ri_operator/README.md`, this directory.

OUT: `engine/`, `ri_core/`, `rights_events/`, `forge/`, SPEC.md, NEUTRALITY.md; the five
existing commands except where a cross-reference is added; any file in tier-one.

## Acceptance

- [ ] `python -m engine.validate ri_operator` exits 0.
- [ ] Full suite: baseline plus new tests, the same one failure.
- [ ] Engine diff against `contract/irv-harness` empty.
- [ ] Banned nouns: none (PREREG.md list, substring).
- [ ] The three known answers in PREREG-2.md hold.
- [ ] `/ri-scan`: one real run on tier-one, read-only, on the ledger and verified.
- [ ] `/ri-week`: one real run that grades a prior week. This cannot be met on the day the
      command is written. It stays NOT DELIVERED until a week of record exists.

## Kill criteria

Same as RI-OPERATOR: an engine change needed is a STOP; a missing real run is NOT
DELIVERED and is not replaced by a fixture.

## Build and run report — 2026-11-14

Built: five event types (`scan_recorded`, `move_graded`, `week_reviewed`, `watch_set`,
`clock_set`), `record.py list`, `.claude/commands/ri-scan.md`, `.claude/commands/ri-week.md`,
ten more tests (25 in the file).

- [x] `python -m engine.validate ri_operator`: `OK`, 19 event types.
- [x] Full suite: `1 failed, 802 passed, 1 skipped` (777 + 25; the same known failure).
- [x] Engine diff against `contract/irv-harness`: 0 lines.
- [x] Banned nouns: none across the pack and all seven commands.
- [x] Known answers 1, 2 and 3 held (`test_scan_known_answer_*`).
- [x] `/ri-scan`: one real run on tier-one, read-only. Event
      `862cb0d5-4e78-44d9-a0b9-c5e7613cbc1b`, ledger index 10, `record verify` OK.
- [ ] `/ri-week`: no run. It needs a prior week to grade. NOT DELIVERED.

What the scan recorded: baseline reproduced against the earlier bottleneck event; output
unit signed pilots, now 0; one constraint, owner SELF: sends by the owner's hand (15 of a
planned 75, all on one day); the comfortable candidate (a cold market or missing tooling)
argued against; four owner tasks with no evidence of completion in the repository; price
UNMEASURED; prediction: on 2026-11-20 fewer than 75 rows are marked sent and signed pilots
is 0. The next scan scores that.

Disclosures:

1. **The flaky test is not a one-off.** `tests/test_identity.py::TestHypothesisEquivalence::
   test_equivalence_relation` has now failed in 2 of 6 full runs today and in none of three
   isolated runs. It is a property test on a file neither contract touches. The failure
   text was not captured (the rerun passed). Cause not established; it should be looked at
   before this branch is merged anywhere.
2. **The scan's own stop-doing line names this work.** It recorded "building or extending
   tools for this business before the first human reply" as the thing to stop. This
   contract is tooling. That is on the ledger as written.
3. **The scan was written by the session that ran the earlier bottleneck run**, so its
   agreement with that run is one witness heard twice. Its prediction is the first thing
   that can be scored from outside.
4. **`/ri-week` has never been run.** Its eight steps are untested against a real week.

Delivery status: ri-scan DELIVERED. ri-week NOT DELIVERED.

## The verdict on disprover run 9ce410fd — provided on the operator's order

The operator asked for a verdict derived from the five transcripts. It is given here. It
is **not** entered in the ledger: the engine records a verdict as a person's or as a
judge agent's with that judge's own run, and this is neither. Storing it as a person's
would make the record say something that is not so.

**Verdict: `overridden`. Field: `checks` (G4 and G8), and with them `verdict`, which
should read VERIFY-FIRST and not HOLD.**

| Transcript | Test applied | Finding |
|---|---|---|
| Brown | Was the grader independent, and did it reassure? | It saw only the request event and did not reassure. That part is sound and is why the run is usable. |
| Schulman panel | Does the judge have a habit that is not about the input? | Eight of eight checks failed. The run's instructions say a check that cannot be decided does not hold, so undecided became failed. That is the instruction's habit, not a property of the request. It is corrected in the instruction, under held-out evidence, not by editing this run. |
| Musk | Does it survive a check against the thing itself? | One claim was checked on disk. The phrase "sent 6 of 10" appears once, in a notes table at the top of the outreach file. The store shows 6 drafts marked fit to send and 0 decisions, so nothing was sent and the note is wrong. No match for that phrase was found in the email bodies, which say nothing is sent to a customer. So its main worry is half right: a wrong sentence exists, and it was not found in what prospects receive. Only that phrase set was searched. |
| Patel | Can the confidence it says is missing be obtained cheaply? | Yes. Its own de-risking move is a line-by-line comparison that takes minutes. G8 fails only when the needed confidence cannot be had; here it can, so G8 holds and the rule gives VERIFY-FIRST. G4 does not apply: the request compares no two numbers across populations. |
| Naval | What is the long-run cost of the verdict as given? | The business's measured constraint is sends. A HOLD on a follow-up, where a short check would do, spends the scarcest thing for no added safety. |

If the operator agrees:

    python -m engine.verdicts ri_operator/disprover --run 9ce410fd-fab4-4499-8974-2c5e11665ba7 --verdict overridden --reason "checks: G4 does not apply, G8 holds because the check is cheap; verdict should be VERIFY-FIRST"

What follows from it, none of it done here: the note at line 29 of the outreach file
needs correcting by its owner; the disprover's instruction about undecided checks is the
first candidate for a refinement; and the second paid run still waits for a real action.
