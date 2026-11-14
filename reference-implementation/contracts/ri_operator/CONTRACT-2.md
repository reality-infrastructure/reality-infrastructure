# CONTRACT: RI-OPERATOR-2 — /ri-scan and /ri-week

```
status:   opened 2026-11-14 on the operator's order ("use all 5 transcripts to build
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
