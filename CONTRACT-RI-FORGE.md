# CONTRACT: RI-FORGE — Reusable Build Library (Speed Under Constraint)

## Context (read first, do not skip)

This repo (`reality-infrastructure`) contains a proven engine: RFC 9162 Merkle log, Denœux cautious combination, PROV-DM provenance DAG, declarative rules engine, byte-identical replay CLI, 541+ passing tests, two proven domains (music split-sheet, Cook County parcels) running on the identical engine with zero architectural changes.

The problem this contract solves: every new build currently starts from scratch — fresh contract-writing, fresh scaffolding, fresh gate-running, multiple sessions across days. The proven patterns exist but are embedded in past work, not extracted as assembly-ready components.

**Goal of this contract:** a new domain build should start from assembly, not invention. Target: scaffold a new rigorous build (contract + pre-registration + test scoreboard + engine wiring + EP schema stub) in under 15 minutes with one command.

## Non-Goals (hard boundaries)

- Do NOT modify the v1.0.0 engine internals. The engine is proven; this contract packages access to it, it does not refactor it.
- Do NOT build new domains. The dummy domain in Gate 3 is a scaffold-validation fixture only, deleted or clearly marked as fixture.
- Do NOT invent new methodology. Extract what already exists and worked. If a pattern hasn't been used in a shipped build, it does not go in the library.
- Do NOT touch NEUTRALITY.md, CITATION.cff, LICENSE, or the public API surface.

## Deliverables

Create a `forge/` directory at repo root with this structure:

```
forge/
├── README.md                  # What this is, how to start a new build in <15 min
├── templates/
│   ├── CONTRACT.template.md   # The closed-contract skeleton: Context / Non-Goals /
│   │                          # Deliverables / Gates / Acceptance / Kill Criteria
│   ├── PREREG.template.md     # Pre-registration: hypothesis, metric, threshold,
│   │                          # decision rule — written BEFORE any data is touched
│   └── SCOREBOARD.template.md # Test scoreboard: named gates, pass/fail, evidence links
├── schemas/
│   └── ep.schema.json         # Extracted EP schema, domain-agnostic, with the two
│                              # proven domains referenced as examples in $comment fields
├── adapters/
│   └── new_domain.py          # Minimal adapter skeleton: the exact interface a new
│                              # domain must implement to run on the engine unchanged.
│                              # Derived by diffing the split-sheet and parcel adapters —
│                              # whatever is common is engine contract, whatever differs
│                              # is the domain surface.
├── scaffold.py                # One command: `python forge/scaffold.py <domain-name>`
│                              # Generates: contracts/<domain>/CONTRACT.md (from template),
│                              # PREREG.md, SCOREBOARD.md, adapters/<domain>.py (from
│                              # skeleton), tests/test_<domain>_gates.py (smoke suite
│                              # that fails until the adapter is real)
└── PATTERNS.md                # The extracted moves, one page each max:
                               # 1. Closed-contract structure (what makes a contract closed)
                               # 2. Pre-registration discipline (metric before data)
                               # 3. Test-scoreboard-as-endpoint (tests are the finish line)
                               # 4. Adversarial validation pass (how prior contracts red-teamed)
                               # 5. No-fabrication rule (source_url + observed_date or NULL)
```

## Method (ordered, do not reorder)

1. **Inventory pass.** Read the existing repo: past contract files, both domain implementations, test structure, replay CLI. Produce `forge/INVENTORY.md` listing every reusable pattern found, with file:line references. No pattern enters the library without a citation to where it shipped. This is the no-fabrication rule applied to the library itself.
2. **Diff the two domains.** Split-sheet vs. parcels: mechanically identify the common surface (engine contract) vs. the varying surface (domain adapter). This diff IS the adapter skeleton spec.
3. **Extract templates.** Pull the contract/prereg/scoreboard structure from the best prior contract in the repo (pick the one with the cleanest gates; state which one and why in INVENTORY.md).
4. **Build scaffold.py.** Pure stdlib, no new dependencies. Idempotent (refuses to overwrite an existing domain dir).
5. **Write PATTERNS.md** last, from what was actually extracted — not from theory.

## Gates (deterministic, all must pass)

- **Gate 1 — Inventory grounded:** every entry in INVENTORY.md has a file:line reference into the existing repo. Zero uncited patterns.
- **Gate 2 — Engine untouched:** full existing test suite (541+) passes unchanged. `git diff` shows zero modifications outside `forge/`.
- **Gate 3 — Scaffold works end-to-end:** run `python forge/scaffold.py demo_fixture`. It must generate all files, the generated smoke test must run (and fail with a clear "adapter not implemented" message, not an import error), and the generated CONTRACT.md must be valid against the template structure. Then delete `demo_fixture` output or commit it under `forge/fixtures/` clearly labeled.
- **Gate 4 — Timed dry run:** document in forge/README.md the exact sequence from `scaffold.py` invocation to "ready to write domain logic," with realistic step timing. If the honest path exceeds 15 minutes, report the actual number — do not fabricate the target.

## Acceptance

- All 4 gates pass with evidence (test output pasted into SCOREBOARD entries, not summarized).
- `forge/README.md` is readable by a future fresh Claude Code session with zero prior context — it must be self-contained enough to be the first file read in a new-build session.
- Single commit series on a branch `contract/ri-forge`, no merge to main in this contract.

## Kill Criteria

- If the two domains turn out NOT to share a clean common surface (i.e., the "zero architectural changes" claim doesn't survive the diff), STOP, report the actual coupling found, and do not paper over it with a leaky abstraction. That finding is more valuable than the library.
