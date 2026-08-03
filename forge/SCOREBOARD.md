# RI-FORGE TEST SCOREBOARD — the four gates, with evidence

Instance of forge/templates/SCOREBOARD.template.md, applied to this contract
itself. Evidence pasted verbatim, not summarized.

Baseline at contract open (2026-08-03, HEAD 72ab7d2, clean tree): 675 tests.
Finding (INVENTORY.md §9 A1): the suite is invocation-path-case-sensitive —
`pytest -q` from `C:\Users\newce\Reality-Infrastructure\reference-implementation`
gives 675 passed; the same command from the lowercase casing of the same
directory gives 674 passed, 1 failed
(test_audit_remediation.py::test_shipped_artifacts_match_live_machine, which
byte-compares shipped artifacts embedding the capitalized absolute path).
Cause-traced pre-existing property of M-RI-16's shipped artifacts; all gate
runs below use the capitalized path the artifacts recorded.

## Gate 1 — Inventory grounded

- [x] Every entry in INVENTORY.md has a file:line reference into the
      existing repo. Zero uncited patterns.

Command (mechanical check over every pattern-table row):

    python - <<'EOF'
    import re
    text = open("forge/INVENTORY.md", encoding="utf-8").read().splitlines()
    rows = [l for l in text if re.match(r"^\| \d+\.\d+ \|", l)
            or (l.startswith("| ") and " | ri/" in l)]
    uncited = [r for r in rows if not re.search(r"\.(md|py|json|yaml):\d", r)]
    print(f"pattern-table rows checked: {len(rows)}")
    print(f"rows without a strict file:line citation: {len(uncited)}")
    EOF

Evidence (verbatim):

    pattern-table rows checked: 64
    rows without a strict file:line citation: 0

Note for honesty: a first-pass check with the looser regex `:\d` reported 74
rows / 0 uncited but was false-passing row 7.1 (its "1:1" prose matched the
pattern while the citation was filename-only). Row 7.1 was re-cited to true
file:line references and the check re-run with the strict regex above.
Line-number accuracy was additionally spot-checked by command for 12 engine
citations (all matched their named definitions).

## Gate 2 — Engine untouched (amended baseline: no reduction from 675)

- [x] Full existing test suite passes unchanged; verbatim count reported;
      no reduction from 675 (operator amendment A1).

Command:

    cd C:\Users\newce\Reality-Infrastructure\reference-implementation
    python -m pytest tests/ -q

Evidence (verbatim, run at RI-FORGE-P4 tree state):

    675 passed in 25.54s

- [x] `git diff` shows zero modifications outside `forge/`.

Command:

    git diff --name-only $(git merge-base main HEAD)..HEAD | grep -v "^forge/"

Evidence (verbatim):

    CONTRACT-RI-FORGE.md

That single path outside forge/ is the contract file itself — status `A`
(added; it was untracked at contract open), not a modification of any
existing file. Every other change in the series is an addition under forge/.
Per amendment A3, reference-implementation/audit/out/analysis-2026-08-03/ is
excluded from the cleanliness assessment — and (discrepancy surfaced in
INVENTORY.md §9 A3) it is in fact already tracked at the baseline commit
72ab7d2, so no exclusion was ever exercised; this contract neither touched
nor committed anything under it.

## Gate 3 — Scaffold works end-to-end

- [x] `python forge/scaffold.py demo_fixture` generates all files.

Evidence (verbatim):

    Scaffolded domain 'demo_fixture' into C:\Users\newce\Reality-Infrastructure\reference-implementation:
      contracts\demo_fixture\CONTRACT.md
      contracts\demo_fixture\PREREG.md
      contracts\demo_fixture\SCOREBOARD.md
      rights_events\adapters\demo_fixture.py
      tests\test_demo_fixture_gates.py

    CONTRACT.md template validation: OK (7 required sections present, in order)

- [x] The generated smoke test runs and fails with a clear "adapter not
      implemented" message, not an import error.

Command: `python -m pytest tests/test_demo_fixture_gates.py -q`
Evidence (verbatim, trimmed to the failure and summary):

    >           pytest.fail(f"ADAPTER NOT IMPLEMENTED: {exc}")
    E           Failed: ADAPTER NOT IMPLEMENTED: adapter not implemented: parse_events() is the scaffold skeleton. Implement the six domain-surface declarations in this module's docstring, then replace the generated smoke suite with real gate tests.

    FAILED tests/test_demo_fixture_gates.py::test_adapter_produces_events - Faile...
    1 failed, 1 passed in 0.88s

(The 1 passed is test_engine_wiring: a RightsEvent constructed and
round-tripped through the frozen schema — the scaffold sits on the engine.)

- [x] The generated CONTRACT.md is valid against the template structure
      (evidence: the "template validation: OK" line above; the validator
      requires every `## ` heading of CONTRACT.template.md, in order).

- [x] Idempotence: a second run refuses to overwrite.

Evidence (verbatim):

    REFUSED: refusing to overwrite existing paths (idempotence rule):
      C:\Users\newce\Reality-Infrastructure\reference-implementation\contracts\demo_fixture\CONTRACT.md
      ...
    exit=1

- [x] demo_fixture output committed under forge/fixtures/ clearly labeled
      (forge/fixtures/demo_fixture/README.md: "FIXTURE — Gate 3
      scaffold-validation output. Not a domain."), and removed from the
      live reference-implementation tree (Gate 2's 675-passed run above is
      the proof the live tree carries no fixture residue).

## Gate 4 — Timed dry run

- [x] The exact sequence from scaffold.py invocation to "ready to write
      domain logic" is documented in forge/README.md with realistic step
      timing, mechanical steps measured:

    scaffold.py run:            0.168s  (time python forge/scaffold.py timing_probe)
    generated smoke suite run:  3.1s    (time python -m pytest tests/test_timing_probe_gates.py -q)

Honest total, stated in README.md: ~11-12 minutes to "ready to write domain
logic" — under two conditions (source data already on disk; author knows the
domain), with the caveat that PREREG §2's measure-the-input step can alone
exceed 15 minutes when data must be fetched, and first-ever runs reading
PATTERNS.md land nearer ~20 minutes. The sub-15-minute target is met for the
data-on-disk, known-domain case and is not claimed beyond it.

## Close

Full suite at close: 675 passed in 25.54s. Delta vs baseline: 0 new tests, 0
modified (this contract adds a library, not suite tests; the generated smoke
suite lives in fixtures, not in the live tree).
