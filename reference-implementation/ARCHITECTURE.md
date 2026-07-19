# ARCHITECTURE — Reference Implementation

## Governing principle
This codebase demonstrates that SPEC.md can be built. It is a library, not a service.
The invariants force a dependency DAG, not a pipeline. Modules mirror the spec's
Minimal Reference Architecture (§12), one module per normative component.

## Module layout (ri-core/)
```
ri_core/
├── serialization.py   # canonical deterministic byte encoding (M-RI-01)
├── log.py             # append-only Merkle history tree; inclusion + consistency proofs (M-RI-02)
├── identity.py        # identity-anchor interface; source identities; A1 (M-RI-05 partial)
├── clock.py           # Lamport logical clock (HLC later if needed); A2
├── provenance.py      # PROV-DM-compatible DAG; semiring annotations (M-RI-05)
├── reconcile.py       # ⊕: cautious-rule fusion; CAI laws; contradiction first-class (M-RI-07)
├── project.py         # deterministic fold Log → BeliefState; justification terms (M-RI-06)
├── rules.py           # versioned verification-rule store (logged as evidence)
└── replay.py          # replay + counterfactual = replay over modified log (M-RI-08)
```

## Hard rules
- **Dependency direction:** serialization ← log ← {identity, clock, provenance, rules} ← reconcile ← project ← replay.
  Lower layers NEVER import higher layers.
- **Purity:** reconcile, project, replay are pure functions. submit is the only mutator, and it only appends.
- **No deletion path exists anywhere.** Retraction = new appended entry.
- **Uncertainty representation:** conjunctive-weight (Denœux cautious rule) profile is the v0.1 choice;
  scalar-only confidence is non-conformant per SPEC §7. Representation code isolated in reconcile.py
  so the credal-set profile can be added without touching the log or projection.
- **Byte-identical replay is the master test.** Any change that alters the serialized belief state of the
  golden logs in tests/golden/ is a spec-conformance event, not a refactor: STOP and report.

## Explicitly out of architecture (do not build)
Network transport, consensus, storage backends beyond local files, UI, async runtime,
performance optimization before conformance. Sharding, HLC, and knowledge compilation
are post-v1.0 unless a contract says otherwise.
