# ROADMAP — Milestones

Each milestone = one closed contract. Each leaves the repo working (tests green).
Order deviates from the original plan in ONE place, logged here: serialization moved ahead of
the evidence log, because the Spec Completeness Review names canonical serialization the single
largest gap and the Merkle log cannot hash an entry without canonical bytes.

| # | Contract | Milestone | Status |
|---|----------|-----------|--------|
| M-RI-00 | (done in chat) | Repository + structure + constitution docs | DONE 2026-07-19 |
| M-RI-01 | contracts/CURRENT.md | Canonical deterministic serialization (serialization.py) | ACTIVE |
| M-RI-02 | queue | Append-only Merkle evidence log; inclusion + consistency proofs (log.py) | — |
| M-RI-03 | queue | Logical clock + identity anchor interface (clock.py, identity.py) | — |
| M-RI-04 | queue | Provenance recorder, PROV-DM-compatible + semiring annotations (provenance.py) | — |
| M-RI-05 | queue | Versioned rule store as logged evidence (rules.py) | — |
| M-RI-06 | queue | Reconciliation ⊕: cautious rule, CAI laws, contradiction first-class (reconcile.py) | — |
| M-RI-07 | queue | Projection engine: deterministic fold + justification terms (project.py) | — |
| M-RI-08 | queue | Replay + counterfactual (= replay over modified log) (replay.py) | — |
| M-RI-09 | queue | Conformance test suite incl. Sybil-calibration ablation + byte-identical replay | — |
| M-RI-10 | queue | Examples: single-parcel title-belief dossier walk-through | — |

Post-v1.0 (not scheduled): credal-set representation profile; HLC; safe-query classifier;
benchmark corpus (moves to /benchmarks); second clean-room implementation for the
interoperability test.
