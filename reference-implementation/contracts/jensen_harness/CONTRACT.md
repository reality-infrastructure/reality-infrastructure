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

---

# CONTRACT JH-C7 — The closed loop: the pack's agents decide the verdict, the data and the training

Operator instruction 2026-10-17, verbatim: "Change the proposer to AI deciding the verdict
the data and the training using reality infrastructure." Built on `contract/irv-harness`
in the same session as HL-02 (hood). Concern stated before building and not withdrawn:
all three interviews the operator read as a trader (Brown, Schulman/Millidge/O'Neill,
Musk) warn that an AI grading its own outputs learns to game the grader. Two structural
guards therefore hold on every turn of the loop: an agent verdict can never contradict a
deterministic check and is recorded under its own source, and a human verdict outranks it.

## OBJECTIVE
`python -m engine.autoloop <pack> --week W` runs one cycle in which the pack's own
`planner` chooses the next runs, the runs execute, the pack's `judge` adjudicates every
run of the week that has no verdict, the crank reports, the pack's `refiner` turns a
rung-1/2 recommendation into one exact text edit that is adopted only if the agent's
golden score does not fall, and every specialist whose gate is open is exported; every
step is a traced run or a ledger-bound event.

## SCOPE
IN: `engine/autoloop.py` (new), `engine/verdicts.py` (source), `engine/store.py` +
`migrations/*/0004_verdict_source.sql` (verdict_source, verdict_ref), `engine/manifest.py`
(roles judge/planner/refiner; frontier-only; no verifier; required output keys),
`engine/guardrails.py` (`verdict_grounded`, `batch_resolves`, `edit_applies`;
`GuardrailContext.engine`), `engine/builtin_tools.py` + `config/tools.yaml`
(`agent_run.read`, `runs.list`), `engine/crank.py` (verdicts attributed by source),
`engine/export.py` + `config/engine.yaml` (`export.accept_agent_verdicts`, `autoloop.*`),
`config/manifest.schema.json`, `config/engine-events.json` (`<pack>.refinement`),
`packs/_reference/agents/{judge,planner,refiner}` + fixture responders,
`tests/test_engine_c7.py`, `tests/test_engine_c5.py` (one expectation), `HARNESS.md`,
`IMPROVEMENT-ORDER.md`, this section.
OUT: `ri_core/`, any model pin, any guardrail or verifier of a pack, any training.

## PLAN GATE (answered)
(a) Who adjudicates is a column, not a new table: `verdict_source` (human|agent) and
`verdict_ref` (the judge's run_id) beside the existing verdict columns; the freeze
triggers admit the two new columns and nothing else. (b) The three loop roles are
manifest roles with the orchestrator's economics (frontier only, no swap) and no verifier;
the loop reads fixed keys from their certified outputs, so the manifest validator requires
those keys in the output schema. (c) The model proposes, code decides, at every step: the
judge's verdict is checked by `verdict_grounded` against the judged run's own status; the
planner's batch by `batch_resolves` against the pack; the refiner's edit by `edit_applies`
against the files it was handed, and then by the golden set before and after. (d) The
export gate counts agent verdicts only when `export.accept_agent_verdicts` is true
(operator's decision: true); a human verdict on the same run replaces the agent's.

## ACCEPTANCE — proof (2026-10-17)
1. `python -m engine.validate _reference` → `OK … agent judge (judge) … agent planner
   (planner) … agent refiner (refiner) … guardrails: 10 … event types: 8`.
2. `tests/test_engine_c7.py` (11 tests): roles load; a non-frontier judge is refused
   (`role judge must run the frontier`); a judge schema without `verdict` is refused; an
   agent verdict carries `verdict_source=agent` and the judge's run as `verdict_ref`, its
   event is `source=agent:judge`, the judge run replays byte-identical; a human verdict
   replaces it and an agent verdict never replaces the human's; a judge may not judge itself
   nor another loop role's run; `judge-lenient` saying `followed` on a failed run →
   `failed_guardrail` ("contradicts code"); `planner-bad` → `failed_guardrail` ("no agent
   'nobody'"); `refiner-bad` → `failed_guardrail` ("occur exactly once"); the gate counts
   agent verdicts iff config says so; one cycle on the fixture pack plans the one input the
   week lacked, runs it, judges all three runs (`followed`, `wrong`), attributes verdicts in
   the crank (`wrong (agent)`), refines the allocator's skills.md with a `_reference.refinement`
   event (adopted, PASS before and after), reports the gate closed, and renders every section;
   the CLI writes `autoloop-<week>.md/.json` and the crank.
3. Full suite: `759 passed, 1 skipped` after one hypothesis flake in `tests/test_identity.py`
   (pre-existing, `ri_core` untouched; passes alone: `26 passed`).

## DONE
1. Plan Gate: above. 2. `pytest -q`: 758 passed + the flake, re-run green (above).
3. git status clean at commit. 4. Commit on `contract/irv-harness`, pushed — hash in the
commit trailer. 5. Checklist: above.

## LIVE TURNS AND THE FIXES THEY FORCED (2026-10-17, all pushed)
- hood HL-03 (three cycles) and ri_closeout (one cycle) ran the loop on Haiku. Both judged every run of the
  week (hood 50 verdicts: 48 followed, 2 wrong; closeout 49: 43 followed, 5 overridden, 1 wrong), both
  adopted one refinement after the golden set passed before and after (hood: profiler prompt, rung 2;
  closeout: closeout skills, rung 1), both export gates closed.
- 2055d6b: the refine step skipped when the top failure cluster was the judge's own runs; it now takes the
  first cluster of a refinable agent (loop roles are never refined by the loop).
- 5c366ae: prior-output memory loaded every succeeded run with its trace and exhausted memory on hood's
  second cycle; it loads the latest N (`list_runs(newest_first=True, limit=n)`).
- c34f5a9: a refiner may decline (`file: null`); the closeout cycle had adopted a well-meant edit the
  recommendation did not call for because declining was impossible.
- Found by the judges, not by code: a candidate that fails a guardrail after calling `events.append` leaves its
  event in the ledger (two identical events for one input). Both packs' refiners aimed their edits at it; an
  engine-level answer (side effects of a rejected candidate) is a later contract.

## STOP CONDITIONS HIT
- None in the engine.
