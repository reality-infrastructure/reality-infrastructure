# FIXTURE — Gate 3 scaffold-validation output. Not a domain.

This directory is the verbatim output of the Gate 3 run of

    python forge/scaffold.py demo_fixture

executed 2026-08-03 (CONTRACT-RI-FORGE.md, Gate 3), relocated here from its
generation paths under `reference-implementation/` so the live tree stays
clean. Layout mirrors the generation targets:

    contracts/demo_fixture/{CONTRACT,PREREG,SCOREBOARD}.md
        was reference-implementation/contracts/demo_fixture/
    adapters/demo_fixture.py
        was reference-implementation/rights_events/adapters/demo_fixture.py
    tests/test_demo_fixture_gates.py
        was reference-implementation/tests/test_demo_fixture_gates.py

Per CONTRACT-RI-FORGE.md Non-Goals: this is a scaffold-validation fixture
only — no domain was built. The smoke test FAILS BY DESIGN
("ADAPTER NOT IMPLEMENTED", 1 passed / 1 failed) and is not runnable from
this relocated position (its `rights_events` imports resolve only at the
generation path); the recorded Gate 3 evidence lives in forge/SCOREBOARD.md.
To reproduce, run the command above and delete the generated paths after.
