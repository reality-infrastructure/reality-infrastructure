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
  sweep.py          python -m engine.sweep <pack>/<agent> --table T [--judge] [--workers N] [--budget-usd X]
  distill.py        python -m engine.distill <pack>/<agent> --student p/m [--matrix]   # rung four: exemplars from followed runs into a student variant, parity vs the teacher
  drift.py          @drift readings a pack declares (modules.drift); the loop adopts and grows nothing while any says shifted
                    # every row not yet graded, N runs in flight, one ledger; stops only when done, over budget or halted
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
`.harness/engine.sqlite3`. Tests use `sqlite://:memory:`. One process per store:
the ledger's Merkle log lives in that process's memory and follows the store
under the store's lock, so a sweep's threads share one Engine; two processes on
one store would race the ledger index.

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
- the closed loop (C7): a judge's verdict never contradicts a deterministic check and is recorded as `agent`-sourced; a human verdict replaces it and is never replaced by one; a judge never judges its own run or another loop role's; a planner schedules only agents the pack can run, under the cap; a refiner edits one onboarding/prompt text file and the edit is adopted only if the agent's golden score does not fall (`<pack>.refinement` event, both scores), or declines (`file: null`) when the evidence warrants no edit
- a non-frontier model outside a fixture pack needs `eval/matrix-*.json` showing parity
- unlisted table / file / tool / network target raises `AccessDenied`; the run fails closed as `access_denied`
- `events`, `ledger` reject UPDATE/DELETE; `agent_runs` freezes everything but the verdict columns
- undeclared event types and payload-schema violations are rejected before any write
- compaction summaries cite only events inside the window; raw events stay
- the judge is also tested by honeypots: succeeded runs served with one figure altered (`agent_run.read` through the loop's plant); misses above the threshold suspend it; `<pack>.honeypot` events
- a pack's drift readings (`@drift`) gate refinement and golden growth; `<pack>.drift` events
- the loop's law (config `autoloop`, on by default): an edit is adopted only if `eval/holdout.jsonl` (never tuned on) does not fall either; an agent whose pass rate over its last runs collapses is halted and cannot be planned until it recovers; the judge is suspended when the operator's overrides exceed the disagreement rate; golden sets grow only from runs the operator marked followed
- export and distillation refuse below 500 verdicted runs (human always; agent verdicts when `export.accept_agent_verdicts`) and for orchestrators and loop roles (workers and specialists are distilled)

## Dependencies

Python 3.11+, `ri_core` (this repo), `anthropic`, `psycopg[binary]` (only for Postgres),
`pyyaml`, `jsonschema`, `pytest`. No agent frameworks.

## JH-C11 wpF — crank analytics

What the weekly crank measures beyond pass rates and failure clusters, and how the loop acts on it.
`crank.build_report` calls `engine.analytics.extend_report` last and `crank.render` appends
`render_sections`; `autoloop.cycle` blames the week's wrong outputs before the crank, steers the
planner and the refiner with the result, and writes the cycle's analytic events at its end
(`analytics.record_cycle`). Config lives in `config/engine.yaml` (`autoloop.constraint`,
`autoloop.min_novel_share`, `autoloop.velocity`, `autoloop.speed`, `autoloop.directive_file`,
`sweep.measure_throughput`, `crank:`, `attribution:`, `adapters:`, `coverage:`), read through
`EngineConfig.analytics` with defaults. Tests: `tests/test_engine_c11_wpF.py`.

| gap | mechanism | where | config | event | test |
|---|---|---|---|---|---|
| G-M1 | the binding constraint: every lost run classified (access, error, tool budget, max_tokens, refusal, truncation, guardrail, verifier) plus adapter latency breaches, a verdict backlog nobody clears, budget and cost trend; ranked by runs then dollars lost; top and next, this week and the trailing window; the funnel per agent; the planner is handed it and `batch_resolves` requires `constraint_share` of the batch for its agent once it has cost `min_lost_runs`; the recommendation (and so the refiner) is pointed at it | `engine/constraint.py` `identify`, `planner_input`, `steer_recommendation`; `guardrails._batch_steering` | `autoloop.constraint` | `<pack>.constraint` (with `previous_top`) | `test_constraint_names_tool_budget_over_a_small_cluster_weights_the_plan_and_moves_after_the_fix` |
| G-D3 (report side) | where wall-clock goes (provider vs engine), concurrency, budget used, verdict backlog, the binding resource; a sweep's runs/hour, items/hour vs the manual baseline, worker utilisation | `engine/constraint.py` `resources`, `sweep_throughput`; `Sweep.record_throughput` (the CLI records it) | `sweep.measure_throughput` | `<pack>.throughput` | `test_sweep_reports_throughput_and_the_binding_resource` |
| G-NAB6 | yield: followed per USD, cost per followed run, items and scale_ratio on followed runs only, human verdicts per 100 runs and per followed outcome with a 4-week trend; a recommendation for volume without outcome; every recommendation carries the yield | `engine/analytics.py` `outcome_yield`, `_weigh_yield` | — | — | `test_crank_yield_counts_only_followed_outcomes`, `test_human_touch_rate_falls_when_the_judge_takes_over` |
| G-NAB5 | learning curve per adopted iteration vs cumulative runs; repetition index; while a window repeats, the planner gets a novelty floor that `batch_resolves` enforces | `analytics.learning_curve`, `repetition`, `novelty_for_planner`; `guardrails._batch_steering` | `autoloop.min_novel_share`, `crank.repetition_floor`, `crank.repetition_min_runs` | — | `test_crank_reports_learning_curve_from_refinement_events`, `test_repetition_index_flags_a_repeating_sweep`, `test_planner_batch_below_novel_share_is_refused` |
| G-D1 | velocity ledger: proposed/adopted, gain per edit, cost and attempts per point of gain, pass rate and cost per week, trend diminishing/accelerating/steady | `engine/velocity.py` `ledger` | `autoloop.velocity` | `<pack>.velocity` | `test_velocity_flags_diminishing_returns` |
| G-D2 | autonomy: agent vs human share of verdicts, planned runs, refinements and golden cases, week over week; the operator directive file (or `--directive`) passed verbatim to planner and refiner; its hash and whether the edit addressed it ride on the refinement event | `analytics.autonomy`; `autoloop.read_directive`, `plan(extra=)`, `refine(directive=)` | `autoloop.directive_file` | `<pack>.refinement` `directive_sha256`, `addresses_directive` | `test_crank_reports_agent_share_of_verdicts_and_edits`, `test_directive_reaches_planner_and_refiner_inputs` |
| G-M11 | cycle wall time and cost; first week of every failure cluster and the week an adoption removed it; median time-to-fix; cycles per week; misses flagged | `velocity.speed`; `analytics.record_cycle` | `autoloop.speed` | `<pack>.cycle` | `test_time_to_fix_and_cycle_events` |
| G-P17 | success by iteration, candidate and tool-call count; median steps; cost after iteration 1; cut/raise `max_iterations` or cut `search_width` once `yield_min_runs` | `analytics.iteration_yield` | `crank.yield_min_runs` | — | `test_iteration_yield_recommends_cutting_iterations_that_never_convert`, `test_iteration_yield_waits_for_enough_runs` |
| G-P7 | distinct output values per distinct input per field, repeated trigrams in free text, judge followed share vs operator spot checks; mode collapse and verdict skew feed a rung-2 recommendation | `analytics.output_diversity`, `diversity` | `crank.diversity` | `<pack>.diversity` | `test_identical_free_text_flags_mode_collapse_and_varied_does_not`, `test_verdict_skew_and_diversity_events` |
| G-P12 | `@featurize` input buckets (pack `modules.featurize`); live vs golden / held-out / exemplar coverage; distill exemplars round-robin across buckets; planner `synthetic: true` items recorded and never grown into golden | `engine/coverage.py`; `packs.load_pack`; `distill.exemplars`; `autoloop.act`, `grow_golden` | `coverage.min_bucket_share` | `<pack>.coverage`, `<pack>.synthetic_input` | `test_coverage_lists_uncovered_buckets_and_exemplars_span_them`, `test_synthetic_inputs_are_recorded_and_never_grown_into_golden` |
| G-P21 | grounding sources may declare `max_age_days` (+ `observed_field`; event queries default to `observed_at`); stale rows listed on the source and in a `stale_grounding` context note; the crank lists agents on stale facts | `engine/freshness.py` `mark_stale`; `memory.assemble_working_context`; manifest check | per-source `max_age_days`, `observed_field` | `<pack>.stale_grounding` (once per week per agent and source) | `test_stale_grounding_rows_are_flagged_and_the_crank_reports_them` |
| G-M10 | skip-level audit sample: k raw runs per worker/specialist (children included) by a seeded hash of (week, run_id) | `analytics.audit_sample` | `crank.audit_sample_per_agent` | `<pack>.audit_sample` | `test_audit_sample_is_deterministic_includes_child_runs_and_changes_with_the_week` |
| G-M8 | trace blame: judge / tool_error / memory_truncated / grounding_missing / prompt / model, by diffing the working context against a followed run (a row the followed run cited is named first); `python -m engine.blame`; blamed once per run each cycle; origins per agent in the crank | `engine/blame.py` `blame`, `blame_week` | — | `<pack>.blame` | `test_blame_names_the_row_dropped_by_the_memory_budget`, `test_blame_tells_prompt_model_tool_and_judge_apart` |
| G-NAB3 | a verdict on a run that cites child runs passes credit (followed) or blame (the named fields) down; own and inherited verdicts per agent; the kill rule counts inherited blame at `inherited_weight` | `engine/attribution.py`; `verdicts.record_verdict` hook; `autoloop.kill_rule` | `attribution` | `<pack>.attribution` | `test_override_on_an_orchestrator_field_blames_the_cited_child`, `test_followed_orchestrator_credits_its_children`, `test_crank_shows_inherited_verdicts_and_the_kill_rule_counts_them` |
| G-NCD7 | the gateway records every command outcome and ingest (or failure); the crank's vendor scorecard is built from those events; a slot's `trial` binding carries `trial_share` of commands and is promoted or refused on its record after `trial_min_events` | `engine/vendors.py`; `adapters/base.AdapterGateway` `_route`, `_decide_trial` | `adapters.trial_share`, `adapters.trial_min_events` | `<pack>.vendor_record`, `<pack>.binding_promoted`, `<pack>.binding_refused` | `test_new_vendor_binding_is_promoted_only_on_a_trial_record`, `test_command_errors_and_ingest_gaps_go_on_the_vendor_record` |

Limits, stated: the store lock's wait is not timed apart; `lock_wait_share` is the engine-side share of
wall time (tools, checks, store and its lock together). The novelty floor and the constraint share
bind only on evidence (a repeating window; a constraint that cost `min_lost_runs` runs of one agent),
so one failed run does not redirect a plan. Freshness covers grounding sources, not facts written
into skills.md. Trials route commands, not ingests (a vendor pushes its own feed).
