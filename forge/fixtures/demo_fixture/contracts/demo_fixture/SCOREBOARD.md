# DEMO-FIXTURE TEST SCOREBOARD — the finish line, as named gates

<!-- Test-scoreboard skeleton. No file named "scoreboard" existed before forge;
     the shipped pattern this extracts is the acceptance checklist with pasted
     evidence: `- [ ]` at open, `- [x]` with verbatim proof at close
     (M-RI-02-merkle-log.md:52→122, M-RI-08-replay.md:79→149,
     M-RI-14-crm-reality-audit.md:56-66→105-119).

     Rules:
     - Tests are the finish line: the contract is DONE when every gate below is
       [x] with evidence, and not before.
     - Evidence is the command plus its verbatim output, pasted, never
       summarized (C2-second-domain.md:163-173 is the canonical example: the
       wall proof is the empty diff output itself).
     - Full-suite count + runtime stated at every close
       (C1-event-layer.md:180-184).
     - A gate that cannot pass with real data closes as FAIL with the finding
       recorded — never waived silently (C2-second-domain.md:72-74). -->

Baseline at contract open: {{n}} tests passing in {{t}}s
(`pytest -q` from {{dir}}, {{date}}).

## Gates

### Gate 1 — {{name}}

- [ ] {{deterministic pass condition}}

Command:

    {{command}}

Evidence (pasted at close, verbatim):

    {{output}}

### Gate 2 — Existing suite unchanged

- [ ] All pre-existing tests pass; zero modifications to existing expectations.

Command:

    pytest -q

Evidence:

    {{output — count + runtime}}

### Gate 3 — Known answer

- [ ] {{pre-declared input}} → {{pre-declared verdict}} from frozen inputs.

Evidence:

    {{output}}

### Gate 4 — Determinism

- [ ] Two runs byte-identical (sha256 of every output equal); goldens hold under
      PYTHONHASHSEED 0 and 1.

Evidence:

    {{hashes}}

## Close

Full suite at close: {{n}} passed in {{t}}s. Delta vs baseline: {{+n new tests,
0 modified}}.
