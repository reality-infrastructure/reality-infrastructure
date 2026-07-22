TASK — Replay + counterfactual over serialized logs (M-RI-08)

OBJECTIVE
Ship ri_core/replay.py: replay(log_bytes, ...) reconstructing a byte-identical BeliefState
from serialized evidence alone, and counterfactual(log_bytes, delta) = replay over a
modified log (evidence removal/addition, rule-binding substitution) — making T1/T6 executable
and S4/S6 testable, and closing the A2 deviation if one was found.

CONTEXT
- SPEC.md §6 (replay MUST equal project byte-for-byte; counterfactual(Log, Δ) ≡
  replay(Log ⊕ Δ)), §14 (retroactive/as-of semantics), §8 I7
- ARCHITECTURE.md: replay.py may import everything; it is the top layer
- M-RI-07 shipped: project(log, graph, authority, rule_store, rule_bindings, as_of);
  submit() wiring; justification checker in tests
- HMAC trust model (M-RI-03): verification requires the anchor's key store — this constrains
  what replay can verify without the original authority; address honestly in Plan Gate

SCOPE
IN:
- ri_core/replay.py
- tests/test_replay.py
- tests/golden/replay/ with 1 frozen counterfactual BeliefState encoding
OUT (explicitly forbidden this contract):
- No new fusion semantics, no persistence, no CLI, no new dependencies
- Do not touch SPEC.md, /research, existing modules (EXCEPTION: if A2-DEVIATION was flagged,
  amend the M-RI-07 test checker to read rule specs from log bytes — smallest possible diff,
  reported separately in DONE), or frozen golden files

PLAN GATE
Before writing any code, state:
(a) LOG TRANSPORT FORM: the serialized form replay consumes. Recommend: encodable dict
    {kind: 'log_export', entries: [entry_bytes as bytes, ...]} produced by a new
    export_log(log) helper — entries are the EXACT canonical bytes appended in M-RI-02, so
    the Merkle root recomputed from imported entries MUST equal the original root (state
    this as replay's integrity gate: import → rebuild EvidenceLog → assert root equality
    against a caller-supplied expected_root; mismatch = typed ReplayError).
(b) TRUST MODEL ON REPLAY — the honest answer: with HMAC, a replayer WITHOUT the original
    authority cannot re-verify sigs. State the resolution: replay takes the authority as an
    input (same trust root as projection — the LocalAuthority model's documented limit), and
    the Merkle root check covers log integrity independent of sigs. Do NOT silently skip sig
    verification; state exactly what replay re-verifies (recommend: re-verify every
    observation sig via the provided authority, since replay re-submits through submit()).
    Also state what identity LINKS mean here: shared_provenance lives in the authority, not
    the log — replay with a different link-state yields a different justification structure
    (same belief, per idempotence). Name this as a documented v0.1 limitation: link state is
    an authority-side input to replay, not yet logged evidence — flag for SPEC v0.2.
(c) REPLAY ALGORITHM: import entries → verify root → fresh EvidenceLog + fresh
    ProvenanceGraph → for each entry in order: observations re-enter via submit()
    (re-verifying sigs), rule_version entries re-register into a fresh RuleStore (state how
    they're recognized: kind == 'rule_version') → project(as_of) → return BeliefState.
    Assert byte-identity against original in tests.
(d) COUNTERFACTUAL DELTA SHAPE: an encodable dict with exactly three optional keys:
    remove_entry_indices (list[int] — indices into the ORIGINAL export),
    add_entries (list[bytes] — canonical entry bytes to append),
    rule_bindings_override (proposition → [rule_id, version]).
    Semantics: removal happens before addition; the counterfactual log is a NEW log (its own
    Merkle root — no consistency relation to the original claimed); rule overrides replace
    bindings for named propositions only. State validation (out-of-range index, malformed
    added entry → typed error before any construction).
(e) API: export_log(log) -> dict; replay(export, authority, rule_bindings, as_of,
    expected_root) -> BeliefState; counterfactual(export, delta, authority, rule_bindings,
    as_of) -> BeliefState (no expected_root — the modified log is new by construction; state
    what integrity IS claimed for it).

CONSTRAINTS (MUST / NEVER)
- MUST: replay of an unmodified export is byte-identical to the original projection's
  BeliefState (the T1 test)
- MUST: root mismatch, bad index, malformed entry → typed ReplayError before any state built
- MUST: counterfactual with empty delta ≡ replay (tested byte-identical)
- MUST: full suite stays green (344 prior)
- NEVER: skip sig re-verification silently; never mutate the input export or the original
  log/graph/store objects
- NEVER: floats, wall-clock, unsorted iteration

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_replay.py` passes; paste output
- [ ] T1 test: full M-RI-07 end-to-end fixture → export → replay ⇒ byte-identical
      BeliefState AND identical Merkle root
- [ ] Tamper test: flip one byte in one exported entry ⇒ ReplayError at root check
- [ ] Counterfactual REMOVE: removing the sole contradicting observation ⇒
      is_contradictory() flips True→False; belief matches hand-computed remainder
- [ ] Counterfactual ADD: adding a retroactive observation (ltime ≤ as_of) ⇒ belief
      reflects it; derived entity id shows the new size (M-RI-07 A1 behavior)
- [ ] Counterfactual RULE SUBSTITUTION: same log, rule v1 vs v2 binding ⇒ different
      exclusion sets, different beliefs; both justifications complete per the independent
      checker (reading rule specs FROM LOG BYTES — this criterion enforces A2 correctness)
- [ ] Empty delta ≡ replay: byte-identical
- [ ] S6 determinism: same counterfactual in 2 subprocesses, different PYTHONHASHSEED ⇒
      identical bytes; golden file byte-match
- [ ] Full suite green (344 prior + new; if A2-DEVIATION fix touched the M-RI-07 checker,
      all M-RI-07 tests still pass)

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-08: replay + counterfactual" →
push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist with per-box pasted proofs, PLUS a separate line stating whether A2-DEVIATION
existed and what the fix diff touched.

STOP CONDITIONS
Halt and report — do not proceed — if: root-check-first ordering cannot be maintained;
byte-identity in the T1 test fails for any reason (that is a determinism bug somewhere
below — surface, do not patch around); rule_version entries in the log are insufficient to
reconstruct the RuleStore (spec gap — surface); any frozen golden file would change; or
push fails.

---

## DONE REPORT — M-RI-08

### 1. PLANNED
Plan Gate approved with three amendments:
- A1: replay log preserves ALL entries in original order (observations via submit(),
  rule_version via register() + log.append()); postcondition tested entry-for-entry.
- A2: malformed entries (decode failure) → ReplayError("malformed_entry") with index,
  before any replay state exists; tested with truncated bytes.
- A3: delta add_entries containing rule_version that violates version discipline →
  ReplayError wrapping RuleError, identifying the offending entry; tested with duplicate
  (rule_id, version).

### 2. IMPLEMENTED
- `ri_core/replay.py` — `ReplayError`, `export_log()`, `replay()`, `counterfactual()`;
  internal helpers `_decode_entry()`, `_verify_root()`, `_validate_export()`,
  `_replay_entries()`.
- `tests/test_replay.py` — 16 tests across 8 test classes.
- `tests/golden/replay/counterfactual_belief_state.bin` — 1 frozen golden file.
- `tests/test_project.py` — A2-DEVIATION fix: 13 lines added, 4 removed in
  `TestIndependentChecker::test_checker_recomputes`.

### 3. TESTED
```
tests/test_replay.py — 16 passed in 0.90s
Full suite — 360 passed in 16.82s (344 prior + 16 new)
```

### 4. COMMITTED
Commit `c9d9387` — "M-RI-08: replay + counterfactual over serialized logs"

### 5. PUSHED
`d6c3d8d..c9d9387  main -> main` — pushed to origin/main, working tree clean.

### Acceptance Criteria

- [x] `pytest -q tests/test_replay.py` passes: 16 passed in 0.90s
- [x] T1 test: `test_replay_byte_identical` — byte-identical BeliefState;
  `test_replay_root_identical` — identical Merkle root;
  `test_replay_entry_for_entry` — element-for-element bytes match (A1 postcondition)
- [x] Tamper test: `test_flipped_byte` — flipped byte ⇒ ReplayError;
  `test_truncated_entry` — truncated bytes ⇒ ReplayError("malformed_entry") (A2);
  `test_empty_bytes_entry` — empty bytes ⇒ malformed_entry
- [x] Counterfactual REMOVE: `test_remove_contradicting` — removing bob's observation ⇒
  is_contradictory() flips True→False; belief matches alice-only hand computation
- [x] Counterfactual ADD: `test_add_retroactive` — retroactive observation (ltime=1 ≤
  as_of=10) ⇒ belief reflects fused result; 2 provenance classes
- [x] Counterfactual RULE SUBSTITUTION: `test_rule_substitution` — v1 excludes charlie,
  v2 excludes bob; different beliefs; independent checker reads rule specs FROM LOG BYTES
- [x] Empty delta ≡ replay: `test_empty_delta_byte_identical` — byte-identical
- [x] S6 determinism: `test_cross_process_determinism` — PYTHONHASHSEED 42 vs 9999 ⇒
  identical bytes; golden file `counterfactual_belief_state.bin` byte-match
- [x] Full suite green: 360 passed (344 prior + 16 new); all 30 M-RI-07 tests pass

### A2-DEVIATION

**A2-DEVIATION existed.** Fix in `tests/test_project.py::TestIndependentChecker::test_checker_recomputes`:
1. Added `log.append(record)` after `rs.register()` (SPEC §11: rules as first-class evidence).
2. Added log-scanning block: extracts rule_version entries from log bytes into
   `rule_specs: dict[(rule_id, version), dict]`.
3. Changed line 830 from `r_spec = rs.get(r_id, r_ver)` to
   `r_spec = rule_specs[(r_id, r_ver)]`.

Diff: 13 lines added, 4 removed. All 30 M-RI-07 tests still pass.
