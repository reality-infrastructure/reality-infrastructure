TASK — Append-only Merkle evidence log with inclusion + consistency proofs (M-RI-02)

OBJECTIVE
Ship ri_core/log.py: an append-only Merkle history tree over canonically serialized entries
(RFC 6962-style), with root hashes, inclusion proofs, consistency proofs, and standalone
verifier functions — satisfying CONFORMANCE C2 and providing the hashing substrate for
everything above it.

CONTEXT
- SPEC.md §5 (Evidence Log: append-only, authenticated, inclusion + consistency proofs;
  retraction = new entry, never deletion), §11 (Producer MUSTs)
- CONFORMANCE.md C1, C2, C5
- ARCHITECTURE.md dependency rule: log.py imports ri_core.serialization and stdlib only
- ri_core/serialization.py public API: encode(obj) -> bytes, decode(data) -> obj

SCOPE
IN:
- ri_core/log.py
- tests/test_log.py
- tests/golden/log/ with frozen golden root hashes for fixture logs
OUT (explicitly forbidden this contract):
- No identity, clock, provenance, reconcile, project code (later milestones)
- No file/DB persistence layer (in-memory tree this contract; persistence is a later contract)
- No new dependencies (stdlib hashlib; hypothesis stays dev-only)
- Do not touch SPEC.md, /research, serialization.py, or frozen golden files

PLAN GATE
Before writing any code, state: (a) the exact hash construction — recommend RFC 6962 domain
separation: leaf_hash = SHA-256(0x00 || entry_bytes), node_hash = SHA-256(0x01 || left || right),
empty-tree root = SHA-256 of empty string — and confirm or argue an alternative; (b) the tree
strategy for non-power-of-two sizes (RFC 6962 split rule); (c) the public API (class + function
signatures) including how a Log entry pairs an index, its canonical bytes, and its leaf hash;
(d) proof object shapes (what a caller stores/transmits). If any spec ambiguity surfaces
(e.g. whether the version byte sits inside entry_bytes — it does, per M-RI-01), STOP and surface it.

CONSTRAINTS (MUST / NEVER)
- MUST: append(obj) canonically serializes via ri_core.serialization.encode, then hashes;
  entries are immutable after append
- MUST: expose root() (current root hash), inclusion_proof(index, tree_size),
  consistency_proof(old_size, new_size), and pure verifier functions verify_inclusion(...)
  and verify_consistency(...) that need no Log instance
- MUST: domain-separate leaf and node hashes (0x00/0x01 prefixes)
- MUST: deterministic — same appended sequence ⇒ same root bytes, cross-process
- MUST: every test deterministic; no network; no wall-clock
- NEVER: expose any delete/mutate path; no method may alter an existing leaf
- NEVER: hash Python objects directly (only canonical bytes from encode())

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_log.py` passes; paste output
- [ ] Inclusion proofs verify for EVERY index at every tree size 1..17 (exhaustive loop test)
- [ ] Consistency proofs verify for EVERY (old_size, new_size) pair with old ≤ new ≤ 17
- [ ] Tamper test: flipping any single bit of any leaf's bytes makes its inclusion proof fail
      (loop over at least one full 8-leaf tree, every byte's high bit)
- [ ] Golden test: root hashes of 3 fixture logs byte-match tests/golden/log/*.bin
- [ ] Cross-process determinism: same append sequence in 2 subprocesses with different
      PYTHONHASHSEED ⇒ identical root; paste assertion
- [ ] Property test (hypothesis): for random entry lists, verify_inclusion holds for all
      entries and verify_consistency holds for a random prefix

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite, 74 prior tests must still pass) → git status clean →
commit "M-RI-02: Merkle evidence log with inclusion + consistency proofs" → push origin/main.
Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate output (as approved)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main (paste push confirmation)
5. Acceptance checklist, each item with proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: the RFC 6962 split rule conflicts with any SPEC.md
statement; an acceptance test can't pass without violating a MUST; any frozen golden file's
bytes would change; or push fails.

---

DONE REPORT — M-RI-02

1. PLAN GATE OUTPUT (as approved, with amendments A1–A2)

Hash construction: RFC 6962 §2.1 — leaf_hash = SHA-256(0x00 || entry_bytes),
node_hash = SHA-256(0x01 || left || right), empty_root = SHA-256(""). entry_bytes
includes the M-RI-01 serialization version byte.

Split rule: k = 1 << ((n - 1).bit_length() - 1) — largest power of 2 strictly less than n.

Verification algorithms (A1): verify_inclusion per RFC 9162 §2.1.3.2 and
verify_consistency per RFC 9162 §2.1.4.2 — fn/sn index-walking form, not from-scratch
reconstruction.

Index-confusion test (A2): A valid proof for index i FAILS verification when presented
with index j != i (exhaustive over all i,j pairs in an 8-leaf tree).

No spec ambiguities found.

2. pytest -q FULL-SUITE OUTPUT

........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 4.53s

3. git status CLEAN

On branch main
nothing to commit, working tree clean

4. COMMIT HASH(ES) PUSHED TO origin/main

[main f45585d] M-RI-02: Merkle evidence log with inclusion + consistency proofs
To https://github.com/P9428/reality-infrastructure-.git
   d3ca9e3..f45585d  main -> main

5. ACCEPTANCE CHECKLIST

- [x] pytest -q tests/test_log.py passes — 19 passed
- [x] Inclusion proofs verify for EVERY index at every tree size 1..17 —
      TestInclusionExhaustive::test_all_inclusion_proofs (153 index/size combinations)
- [x] Consistency proofs verify for EVERY (old, new) pair with old <= new <= 17 —
      TestConsistencyExhaustive::test_all_consistency_proofs (171 pairs)
- [x] Tamper test — TestTamper::test_bit_flip_breaks_inclusion: flips high bit of every
      byte of every leaf in an 8-leaf tree, confirms inclusion proof fails each time
- [x] Golden test — 3 fixture logs (1, 4, 7 entries) byte-match tests/golden/log/*.bin
      (TestGolden::test_root_matches_golden)
- [x] Cross-process determinism — TestCrossProcessDeterminism::test_same_root_different_hashseed:
      3 subprocesses (PYTHONHASHSEED=0, 42, 99999), identical root
- [x] Property test (hypothesis) — TestHypothesis::test_inclusion_holds_for_all (100 examples)
      and test_consistency_holds_for_random_prefix (100 examples) pass
- [x] A2 index-confusion — TestIndexConfusion::test_wrong_index_fails: valid proof for each
      index i fails for all j != i in 8-leaf tree (56 negative assertions)
