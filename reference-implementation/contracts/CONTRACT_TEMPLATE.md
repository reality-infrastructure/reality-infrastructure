# CONTRACT_TEMPLATE (canonical — closed-contract anatomy, library variant)
# Full form for shippable milestones; compress for intermediate fixes ending at "don't commit."

TASK — [one-line title] (M-RI-XX)

OBJECTIVE
[One shippable end-state. One sentence if possible.]

CONTEXT
[Exact files/lines only. No "look around." e.g. SPEC.md §5 ¶2; ARCHITECTURE.md module table; ri_core/log.py:1-40]

SCOPE
IN:
- [bullet]
OUT (explicitly forbidden this contract):
- [no unrelated refactors]
- [no new dependencies without approval]
- [do not touch <files/dirs>]

PLAN GATE
Before writing any code: state your implementation plan as the first output —
files you will change, the approach, and any assumption you're forced to make.
Do NOT begin implementation until the plan is stated and approved. If an assumption is
load-bearing and unverified, STOP and surface it instead of guessing.

CONSTRAINTS (MUST / NEVER)
- MUST [e.g. pure function of inputs; no wall-clock reads]
- MUST [tests deterministic; no network; no sleeps]
- NEVER [edit SPEC.md or anything in /research]
- NEVER [assert a value the spec does not determine]

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_x.py` passes (paste output)
- [ ] [specific behavior: exact command + exact expected output]

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite, not just new tests) → git status clean → commit with message
"M-RI-XX: <title>" → push origin/main. No deploy step exists for this repo.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate output (as approved)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main (paste)
5. Acceptance checklist above, each item with its proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: a constraint conflicts with the objective, the plan
would touch an OUT file, an acceptance test can't pass without violating a MUST, the
implementation would require editing SPEC.md, or a golden file's bytes would change.
