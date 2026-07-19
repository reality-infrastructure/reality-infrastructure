# Reality Infrastructure — Reference Implementation

## FIRST: Read the current contract
Read /contracts/CURRENT.md before doing anything else.
The contract defines your task, scope, acceptance criteria, and stop conditions.
Do NOT proceed without understanding the contract. Do NOT work outside it.

## SOURCE OF TRUTH
SPEC.md is the specification. It is frozen. You implement it; you never edit it.
If the contract conflicts with SPEC.md: STOP and report. Research Claude revises specs; you do not.

## CONTEXT (read only what the contract requires)
- Specification: /SPEC.md
- Architecture rules: /ARCHITECTURE.md
- Conformance criteria: /CONFORMANCE.md
- Milestone plan: /ROADMAP.md
- Contribution/contract discipline: /CONTRIBUTING.md

## RULES (always)
- One contract at a time. Plan Gate before code. Fresh session per contract.
- Python 3.11+ stdlib-first. No new dependency without explicit approval in the contract.
- Determinism is law: no wall-clock reads, no dict-iteration-order dependence, no randomness
  without a logged seed, anywhere in ri-core.
- Every function in ri-core that computes belief MUST be a pure function of its inputs.
- NEVER touch /research (immutable artifacts, lives outside this folder). NEVER edit SPEC.md.
- Tests are the acceptance instrument: pytest, deterministic, no network, no sleep-based timing.

## COMPLETION
A contract is complete ONLY when:
1. All acceptance criteria in CURRENT.md are met (paste proof).
2. All tests pass (`pytest -q` output pasted).
3. git status clean, committed, pushed (hashes pasted).
4. The five-gate DONE report in the contract is answered in full.
5. CURRENT.md moved to /contracts/completed/ with the DONE report appended.
