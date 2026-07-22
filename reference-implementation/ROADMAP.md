# ROADMAP — Milestones

Each milestone = one closed contract. Each leaves the repo working (tests green).
Order deviates from the original plan in ONE place, logged here: serialization moved ahead of
the evidence log, because the Spec Completeness Review names canonical serialization the single
largest gap and the Merkle log cannot hash an entry without canonical bytes.

| # | Contract | Milestone | Status |
|---|----------|-----------|--------|
| M-RI-00 | (done in chat) | Repository + structure + constitution docs | DONE 2026-07-19 |
| M-RI-01 | contracts/completed/M-RI-01-serialization.md | Canonical deterministic serialization (serialization.py) | DONE 2026-07-19 |
| M-RI-02 | contracts/completed/M-RI-02-merkle-log.md | Append-only Merkle evidence log; inclusion + consistency proofs (log.py) | DONE 2026-07-19 |
| M-RI-03 | contracts/completed/M-RI-03-clock-identity.md | Logical clock + identity anchor interface (clock.py, identity.py) | DONE 2026-07-19 |
| M-RI-04 | contracts/completed/M-RI-04-provenance.md | Provenance recorder, PROV-DM-compatible + semiring annotations (provenance.py) | DONE 2026-07-19 |
| M-RI-05 | contracts/completed/M-RI-05-rules.md | Versioned rule store as logged evidence (rules.py) | DONE 2026-07-19 |
| M-RI-06 | contracts/completed/M-RI-06-reconcile.md | Reconciliation ⊕: cautious rule, CAI laws, contradiction first-class (reconcile.py) | DONE 2026-07-19 |
| M-RI-07 | contracts/completed/M-RI-07-project.md | Projection engine: deterministic fold + justification terms (project.py) | DONE 2026-07-21 |
| M-RI-08 | contracts/completed/M-RI-08-replay.md | Replay + counterfactual (= replay over modified log) (replay.py) | DONE 2026-07-21 |
| M-RI-09 | queue | Conformance test suite incl. Sybil-calibration ablation + byte-identical replay | ACTIVE |
| M-RI-10 | queue | Examples: single-parcel title-belief dossier walk-through | — |

Post-v1.0 (not scheduled): credal-set representation profile; HLC; safe-query classifier;
benchmark corpus (moves to /benchmarks); second clean-room implementation for the
interoperability test.
