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
