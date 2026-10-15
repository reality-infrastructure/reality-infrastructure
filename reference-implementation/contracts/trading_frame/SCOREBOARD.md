# TRADING-FRAME TEST SCOREBOARD — the finish line, as named gates (PATH B)

Baseline at contract open: 700 pre-existing tests passing (PATH A closed). PATH B adds a
sibling domain layer on `ri_core`; it modifies no frozen module. The known-answer is
pinned in PREREG.md before any fold code (commit ordering is the proof).

## Gates

### Gate 1 — Known-answer conflict mass (SYNTHETIC + REAL)

- [ ] Fold of the SYNTHETIC capture (displayed GAIN vs chain LOSS) and the REAL
      2026-10-15 capture (displayed LOSS vs chain GAIN) each yield conflict_mass 0.165,
      chain-bucket 0.385, displayed-bucket 0.135, unresolved 0.315, all else 0. Folding
      twice is equal.

Command:

    (filled at close)

Evidence (verbatim):

    (filled at close)

### Gate 2 — Engine untouched

- [ ] Full pre-existing suite passes; frozen-module diff empty; new tests only add.

Command / Evidence:

    (filled at close)

### Gate 3 — Logged + reproducible + tamper

- [ ] Events ingested as signed observations; all inclusion proofs verify; belief logged;
      reload re-verifies signatures and RE-FOLDS the belief byte-for-byte; one-bit fill
      tamper makes reload raise.

Command / Evidence:

    (filled at close)

### Gate 4 — Honest, not rigged

- [ ] Agreement case yields conflict_mass 0, agreed bucket 0.55, Ω 0.45.

Command / Evidence:

    (filled at close)

## Close

(filled at close: full-suite count + runtime, belief-log root, deltas vs baseline)
