# HARNESS — the agent engine on top of Reality Infrastructure

`engine/` is a domain-agnostic agent harness. Every agent it runs lives inside
RI: each candidate output is judged by signed observations on an RI evidence
log fused under the cautious rule; every event and every trace is bound to an
RFC 9162-style Merkle ledger; every judgement replays byte for byte. The engine
carries mechanism only; domain nouns live in packs.

## Layout

```
engine/
  run.py            python -m engine.run <pack>/<agent> [--input JSON|@file] [--model p/m] [--compact]
  replay.py         python -m engine.replay <run_id>          # RI proof: ledger inclusion + byte-identical judgement
  verdicts.py       python -m engine.verdicts <pack>/<agent> --pending | --run ID --verdict ... --reason ...
                    (a verdict carries its source: human, or agent:<judge> with the judge's run; a human's outranks)
  eval.py           python -m engine.eval <pack>/<agent> [--models p/a,p/b]   # PASS/FAIL + eval/matrix-<date>.*
  export.py         python -m engine.export <pack>/<specialist> --format sft|preference --out FILE  (gated)
  crank.py          python -m engine.crank <pack> --week YYYY-Www            # packs/<pack>/crank/<week>.md
  autoloop.py       python -m engine.autoloop <pack> --week YYYY-Www         # the closed loop: plan -> act -> judge -> crank -> refine -> export
  scaffold.py       python -m engine.scaffold new-domain <pack>
  validate.py       python -m engine.validate <pack>
  manifest.py       manifest + onboarding pack loading, fail-at-load invariants, hashing
  loop.py           iterate-until-done runner (propose -> guardrails -> verifier -> RI judgement)
  providers.py      anthropic | openai_compat | local(fixture); prices from config/prices.yaml
  tools.py          @tool registry; every call access-checked and traced
  builtin_tools.py  events.query/append, agent_output.read, agent_run.read, runs.list, files.read, tables.read, agent.<pack>.<agent>
  access.py         deny-by-default policy compiled from access.yaml
  guardrails.py     schema_valid, no_invented_keys, citations_resolve, no_fabrication, bounded_size, cited_values_match,
                    verdict_grounded (judge), batch_resolves (planner), edit_applies (refiner)
  citations.py      <kind>:<locator>:<id> resolver; event citations verify ledger inclusion
  verify.py         proposer/verifier contract (specialists must carry one)
  judgement.py      RI belief per candidate: checks are `measured`, model confidence is an
                    `asserted-by-interested-party` discount; conflict mass m(empty) is the calibration signal
  memory.py         working context, long-term (events + prior outputs + verdicts), compaction
  events.py         declared-type event log; engine-owned types added per pack
  store.py          Store (SQLite stdlib / Postgres psycopg), Ledger (ri_core.log.EvidenceLog), Engine
  traces.py         agent_runs writer; failures logged identically to successes
  adapters/base.py  Adapter interface + gateway (latency SLA, suppression, required flags, export_all)
  templates/        the new-domain skeleton the scaffolder copies
config/             prices, frontier pin, judgement masses, engine knobs, tool descriptions, JSON Schemas
migrations/         sqlite/ and postgres/ DDL: ledger, agent_runs (verdict columns only mutable), events (append-only)
packs/_reference/   the blueprint pack on labeled fixture data (worker, specialist+verifier, orchestrator, compactor,
                    judge, planner, refiner, 2 mock adapters)
IMPROVEMENT-ORDER.md
```

Storage: `DATABASE_URL` (`postgresql://...` or `sqlite:///path`), default
`.harness/engine.sqlite3`. Tests use `sqlite://:memory:`.

## Where RI is load-bearing

| Mechanism | RI primitive | Effect |
|---|---|---|
| events + agent_runs rows | `ri_core.log.EvidenceLog` (ledger table) | every row carries `ledger_index` + `leaf_hash`; a forged row fails its inclusion proof and cannot be cited |
| candidate judgement | `ri_core.project.submit/project`, `ri_core.reconcile.cautious_fuse`, `ri_core.identity.LocalAuthority` | guardrail/verifier votes and the model's confidence are signed EP-typed observations; the fused belief with retained m(∅) is stored on the trace |
| replay | `ri_core.replay.replay` | `engine.replay <run_id>` rebuilds the judgement from the stored export and checks byte identity |
| serialization | `ri_core.serialization.encode` | ledger entries and judgement exports are canonical bytes |

The accept/reject decision stays deterministic (all guardrails pass and the
verifier certifies). The RI belief is the auditable record of how that
decision was supported; rising conflict mass on an agent means the model is
confidently wrong more often, and the crank reports it per agent.

## Invariants the tests pin

- engine code has no domain nouns and no prompt strings (`tests/test_engine_c0.py`)
- unknown manifest key / tool / guardrail / verifier fails at load
- orchestrators, judges, planners and refiners are pinned to the frontier (`config/frontier.yaml`); specialists need a verifier and `problem.md`; one specialist per pack without an ADR
- the closed loop (C7): a judge's verdict never contradicts a deterministic check and is recorded as `agent`-sourced; a human verdict replaces it and is never replaced by one; a judge never judges its own run or another loop role's; a planner schedules only agents the pack can run, under the cap; a refiner edits one onboarding/prompt text file and the edit is adopted only if the agent's golden score does not fall (`<pack>.refinement` event, both scores)
- a non-frontier model outside a fixture pack needs `eval/matrix-*.json` showing parity
- unlisted table / file / tool / network target raises `AccessDenied`; the run fails closed as `access_denied`
- `events`, `ledger` reject UPDATE/DELETE; `agent_runs` freezes everything but the verdict columns
- undeclared event types and payload-schema violations are rejected before any write
- compaction summaries cite only events inside the window; raw events stay
- export refuses below 500 verdicted runs (human always; agent verdicts when `export.accept_agent_verdicts`) and for any non-specialist

## Dependencies

Python 3.11+, `ri_core` (this repo), `anthropic`, `psycopg[binary]` (only for Postgres),
`pyyaml`, `jsonschema`, `pytest`. No agent frameworks.
