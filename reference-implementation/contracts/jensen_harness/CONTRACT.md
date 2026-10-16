# CONTRACT JH-C0..C6 — Jensen Harness Engine on Reality Infrastructure

Source spec: `SPEC-JENSEN-HARNESS.md` (verbatim, beside this file). Operator
instruction 2026-10-16: build the full engine on top of Reality Infrastructure so
every agent in the harness uses RI for decisions, beliefs and judgement; no
boilerplate; production code. The seven contracts were executed in one session
on branch `contract/jensen-harness` (branched from `main`), as one body of work
with one test suite per contract.

## OBJECTIVE
`python -m engine.run <pack>/<agent>` executes a manifest-defined agent end to
end, guarded, access-enforced, judged inside RI, traced to `agent_runs` and
bound to an RI Merkle ledger; the `_reference` pack exercises every mechanism
on labeled fixture data; a new domain scaffolds and validates with zero engine
changes.

## CONTEXT
- `ri_core/` (frozen; invoked, never modified — `git diff main -- ri_core/` is empty)
- the pasted spec, PART 2 (engine), PART 3 (C0–C6), PART 4 (pack interface)
- repo rules: `CLAUDE.md`, `CONTRIBUTING.md`; no-fabrication rule

## SCOPE
IN: `engine/`, `config/`, `migrations/`, `packs/_reference/`, `IMPROVEMENT-ORDER.md`,
`HARNESS.md`, `tests/test_engine_*.py`, `tests/conftest.py`, `.gitignore` (`.harness/`),
`README.md` (one section), this contract.
OUT: `ri_core/`, `rights_events/`, `audit/`, `trading_frame/`, `/research`, `SPEC.md`,
`contracts/CURRENT.md`; any real vendor integration; any real outbound action; any
training; the first REAL domain pack (C6 second half — see STOP below).

## PLAN GATE (answered)
(a) manifest JSON Schema: `config/manifest.schema.json` (+ pack/access/events/adapters schemas).
(b) `agent_runs` DDL: `migrations/{sqlite,postgres}/0002_agent_runs.sql` — spec columns plus
`input`, `judgement`, `judgement_hash`, `access_denied`, `failure_reasons`, `ledger_index`,
`leaf_hash`.
(c) access enforcement call path: `ToolRegistry.call` → `AccessPolicy.check_tool` (model-originated
calls) → `spec.targets(args)` → `AccessPolicy.check(target)` → tool body. Grounding/memory reads
skip the allowlist but never the target checks. `AccessDenied` propagates to `Runner.run`, which
records status `access_denied`, `access_denied=true`, output null.
(d) fixture domain: arithmetic sheet QA (worker), 0/1 knapsack with a DP verifier (specialist),
a brief citing only certified figures (orchestrator), event summaries (compactor); two mock
vendors on one slot. All golden cases `fixture: true` with provenance strings.
C2 boundary (knapsack): MODEL owns `selected`, `explanation`, `confidence` and the copied
`weight`/`value` it cites; CODE owns `total_weight`, `total_value` (recomputed), feasibility,
row existence/uniqueness, optimality (DP).
RI integration decision: judgement masses live in `config/judgement.yaml` (hashed onto every
trace); they are discretionary, the replay guarantee covers the fold, not the numbers.

## CONSTRAINTS
- MUST keep engine code free of domain nouns and prompt strings — pinned by test
- MUST enforce access in code, fail closed — pinned by tests
- MUST log every run including failures — pinned by tests
- NEVER add dependencies beyond spec list (anthropic, psycopg, pyyaml, jsonschema, pytest) — held
- NEVER fabricate golden cases/events/outcomes — all fixture data is labeled `fixture: true`
- NEVER let the model self-certify — verifier/guardrails are code; model confidence is a
  discounted interested-party observation

## ACCEPTANCE — proof (scratch DB `accept.sqlite3`, 2026-10-16)

C0
1. `python -m engine.run _reference/checker --input '{"sheet_id":"S1"}'` → exit 0,
   `run_id=54b97a0f-de71-4bbf-94a2-dad8e926bcd6 status=succeeded cost_usd=0.00204200`;
   row: iterations non-null (7310 bytes), cost 0.00204200, latency 10 ms, manifest_hash
   `d656529f…fa316` — verified with `select` (see DONE 2).
2. `python -m engine.eval _reference/checker` → `PASS (2/2 >= 1.0)`.
3. pytest `test_unlisted_table_read_fails_closed`: status `access_denied`, AccessDenied in trace.
4. pytest `test_malformed_output_fails_guardrail`: `failed_guardrail`, output null, both iterations logged.
5. pytest `test_manifest_load_errors` (unknown key / tool / guardrail / verifier).
6. Model swap, no code change: `29ad3d19-cc81-488e-8455-590399bb9367` (local/checker-v1) and
   `19218fd0-8dcf-4aec-849e-688b6dc1d782` (local/checker-v2), same manifest_hash, both succeeded.
7. pytest green (below).

C1
1. `test_undeclared_event_type_rejected` — undeclared type, payload schema, entity_type, source.
2. `test_events_are_append_only` / `test_run_rows_freeze_everything_but_the_verdict`.
3. `test_compaction_writes_cited_summary_and_keeps_raw_events` — `compaction.summary` event,
   all citations resolve to the window, raw rows retained, idempotent, surfaces in long-term memory.
4. `test_verdict_recorded_on_run_and_as_event` + `test_verdict_cli` — `_reference.verdict` event.
5. `test_long_term_memory_reads_appear_in_trace` — `events.query` + `agent_output.read` calls traced.

C2
1. `test_infeasible_proposal_fails_verifier` → `failed_verifier`.
2. `test_misstated_figure_is_a_recompute_violation` → "total_value misstated: proposal says 111, recomputed 110".
3. `test_second_specialist_needs_adr` → load error without ADR; loads with `adr/` + `max_specialists: 2`.
4. `test_orchestrator_cannot_leave_the_frontier` → load error on `anthropic/claude-sonnet-5-5`.
5. Orchestrator run `c4d6d51a-9cc2-41a4-9f36-2f8094f047fb` → child allocator
   `6446c763-8736-49e6-bbb5-21f47d4823f9` with `parent_run_id` set; figures
   `total_value=270`, `total_weight=50` cite `run:agent_runs:6446c763…` and equal the source
   (`cited_values_match`). `python -m engine.replay c4d6d51a…` → `OK … root=d6589381…`.

C3 (`tests/test_engine_c3.py`)
1. ingest → events within SLA; a stale record logs `_reference.latency_breach`.
2. suppressed `rec-3` → blocked + `_reference.command_blocked`; missing `disclosure` → blocked.
3. `export_all` returns every record and command.
4. `mock_a → mock_b` binding change; briefer runs unchanged (two run ids, same manifest_hash).

C4
- `packs/_reference/agents/allocator/eval/matrix-2026-10-16.{md,json}`: allocator-v1 1.0000 vs
  allocator-greedy 0.5000 (greedy fails cap20 — the verifier's optimality check).
- `test_downgrade_without_parity_is_refused`, `test_orchestrator_never_downgrades_even_with_parity`,
  `test_fixture_provider_forbidden_in_real_pack`.

C5
- `packs/_reference/crank/2026-W42.md` (fixture week) — all sections; `test_crank_report_sections_and_recommendation`.
- export: `<500 verdicts` → refused (exit 2); orchestrator → refused (exit 2);
  `test_export_with_500_verdicts_writes_dataset` → 450 SFT rows + preference pairs.

C6
- `test_scaffold_loads_and_validates`: `engine.scaffold new-domain acme_ops` → `engine.validate` OK,
  zero engine changes. Real-domain pack: STOP (below).

## DONE
1. Plan Gate: above.
2. `pytest -q` (full suite, from `C:\Users\newce\Reality-Infrastructure\reference-implementation`):
   `746 passed, 1 skipped in 54.71s` (skip = Postgres round-trip, needs `DATABASE_URL`).
   Migration verified with select on the acceptance DB: 11 `agent_runs` rows, 4 `events`, 15 `ledger`.
3. git status clean at commit (see 4).
4. Commit on `contract/jensen-harness` — hash in the commit message trailer of this file's commit.
5. Acceptance checklist: above, each item with proof.

## STOP CONDITIONS HIT (reported, not coded around)
- C6 second half (first REAL domain pack in its own repo, worker on a real manual workflow,
  ≥10 real golden cases): requires the real historical data count before code. Not in this
  repo; the-registry-signal warehouse was not opened in this session. Next contract.
- Live providers: `ANTHROPIC_API_KEY` is unset in this environment, so the Anthropic provider is
  proven by a stubbed-client test (request shape, block mapping, pricing), not a live call.
- Postgres: `DATABASE_URL` is unset; `PostgresStore` and `migrations/postgres/` are written and
  the round-trip test is in place but skipped here.
