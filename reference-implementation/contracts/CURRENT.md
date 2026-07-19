TASK — Canonical deterministic serialization for RI records (M-RI-01)

OBJECTIVE
Ship ri_core/serialization.py: a canonical, deterministic byte encoding for RI Observations,
provenance terms, and belief-state snapshots, such that encode(x) is byte-identical across
processes, platforms, and Python runs — closing the Spec Completeness Review's #1 gap and
unblocking Merkle hashing in M-RI-02.

CONTEXT
- SPEC.md §4 (Observation tuple: id, source_id, proposition, payload, ltime, sig), §5 (Evidence
  Log requirements), §11 (byte-identical replay conformance test), Completeness Review item 4
  (canonical serialization = largest gap).
- ARCHITECTURE.md module table (serialization is the bottom layer; imports nothing from ri_core).
- CONFORMANCE.md C1, C5.
- Empty repo: ri-core/ contains no code yet. Create the package as ri_core/ with __init__.py.

SCOPE
IN:
- ri_core/__init__.py, ri_core/serialization.py
- tests/test_serialization.py
- tests/golden/serialization/ with 5+ frozen golden byte files
OUT (explicitly forbidden this contract):
- No log/Merkle code (that is M-RI-02)
- No new runtime dependencies (stdlib only; `hypothesis` permitted as dev-dependency for
  property tests per CONFORMANCE C8 — declare it in a requirements-dev.txt)
- Do not touch SPEC.md, /research, ARCHITECTURE.md, CONFORMANCE.md, ROADMAP.md

PLAN GATE
Before writing any code: state (a) the encoding choice — recommend a deterministic canonical
scheme in the spirit of RFC 8949 CBOR deterministic encoding or a strictly-specified canonical
JSON (sorted keys, no whitespace, explicit UTF-8 NFC normalization, no floats — integers and
decimal strings only), with your reasoning; (b) how non-string payloads are handled; (c) how
version-tagging works so the format can evolve without breaking old logs. Floats are a
load-bearing hazard for byte-identity: if any input type would force float encoding, STOP and
surface it. Do not begin implementation until the plan is stated and approved.

CONSTRAINTS (MUST / NEVER)
- MUST: encode() is a pure function; decode(encode(x)) == x round-trip for every supported type
- MUST: byte output independent of dict insertion order, platform, and PYTHONHASHSEED
- MUST: reject unsupported types with a typed error (no silent coercion)
- MUST: format carries an explicit version byte/prefix
- MUST: every test deterministic; no network; no wall-clock
- NEVER: use pickle, repr(), or hash() as any part of the encoding
- NEVER: encode floats (spec confidence values are conjunctive weights — represent as decimal
  strings or rationals; surface at Plan Gate if this bites)

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_serialization.py` passes; paste output
- [ ] Round-trip property test over generated Observation-shaped structures passes (hypothesis)
- [ ] Golden test: encoding the 5 fixture records byte-matches tests/golden/serialization/*.bin
- [ ] Cross-run determinism test: same input encoded in two subprocesses with different
      PYTHONHASHSEED values produces identical bytes; paste the assertion
- [ ] `python -c "from ri_core.serialization import encode, decode"` imports cleanly

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-01: canonical deterministic
serialization" → push origin/main.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate output (as approved)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main
5. Acceptance checklist, each item with proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: any supported input type cannot be encoded without
floats; the encoding choice would require a runtime dependency; a golden file's bytes would
change after being frozen; or any constraint conflicts with the objective.
