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

## JH-C11 wpA — eval rigor

A score is evidence only with its n, its spread, its strata, an objective that has not silently moved, and an
eval that is itself checked. New modules: `engine/stats.py` (Wilson, pass@k, bound gates), `engine/rigor.py`
(per-model metrics, objective, controls, re-audit, suspects, coverage, adoption refusals, saturation; operator CLI
`python -m engine.rigor objective|clear-suspect`), `engine/curriculum.py` (`@tier`, promotion, gating, per-cycle
audit), `engine/goldenview.py` (the same metrics over runs already recorded). Tests: `tests/test_engine_c11_wpA.py`.

Golden file additions (all optional): header `controls: [{id, case, output}]`, `human_baseline: {score, source, n}`,
`samples`; case `tags: {area, realism, dimension, value_weight, ...}`, `tier` (int >= 1), `exercises: [tool ids]`.

| Mechanism | Gap ids | Code | Config | Event | Test |
|---|---|---|---|---|---|
| Wilson interval and n on every rate (eval score, draw rate, strata, crank pass rate, kill rule, judge disagreement and honeypot miss rate); kill rule / judge suspension decide on the bound when `gate_on_bounds` | G-B14 | `stats.rate/decide`; `autoloop.kill_rule`, `autoloop.judge_safety`, `crank._rigor_view` | `stats.confidence: 0.9`, `stats.gate_on_bounds: false` | intervals on `<pack>.refinement` (`before_interval`, `after_interval`) | `test_wilson_intervals_same_point_different_evidence_and_gate`, `test_kill_rule_and_judge_gate_on_the_bound_when_configured` |
| Repeated samples per case (distinct candidate indices via `Runner.run(sample=)`), pass@1, unbiased pass@k, robust case pass, zero-signal cases; adoption refuses a pass@k fall | G-P9, G-NAB7 | `eval.run_eval`, `rigor.model_metrics`, `rigor.adoption_refusals`, `loop.Runner.run` | `eval.samples: 3`, `eval.fixture_samples: 1`, `eval.min_case_rate: 0.6` | `samples`, `before/after_pass_at_k`, `refusals` on `<pack>.refinement` | `test_repeated_samples_report_pass_at_1_and_pass_at_k`, `test_flaky_case_fails_the_robust_eval_and_adopt_refuses_luck`, `test_adopt_refuses_a_pass_at_k_fall_and_a_stratum_fall` |
| A refinement needs a failure cluster seen in enough runs | G-P9 | `autoloop.refine` | `autoloop.refine_min_cluster_runs: 1` | none (refine `skipped`) | `test_small_cluster_does_not_trigger_refine` |
| Case tags and per-stratum scores; adoption refuses an edit that lowers any stratum with enough cases even when the total rises; crank names the weakest stratum and ranks failure clusters by `value_weight` | G-P1 | `rigor.model_metrics/weakest_stratum/adoption_refusals`, `goldenview.golden_view/value_weights`, `crank._rigor_view` | `eval.strata`, `eval.min_stratum_cases: 3` | `before_strata`/`after_strata` on `<pack>.refinement` | `test_strata_tiers_and_weakest_stratum_from_eval_and_crank`, `test_adopt_refuses_a_pass_at_k_fall_and_a_stratum_fall` |
| Tiers (difficulty / rungs): per-tier score, mastered tier, frontier tier, rung gaps; teacher-student gap per tier in distill | G-P10, G-B5, G-M16 | `rigor.tier_ladder`, `rigor.tier_gaps`, `distill.matrix` | `curriculum.promote_at: 0.9`, `curriculum.max_teacher_gap: 0.5` | `<pack>.curriculum` | `test_tier_ladder_frontier_and_rung_gap`, `test_teacher_student_gap_per_tier` |
| Easy-first promotion: a version starts at tier 1 and climbs when its latest runs at its tier pass; the sweep never hands an input above the promoted tier; the planner's batch must stay in the band (frontier - window .. promoted tier), refused by `batch_resolves`; pack `@tier(agent=)` tiers non-golden inputs (`modules.tiers`) | G-M16, G-P10 | `curriculum.promote/gate_inputs/band/band_problem/audit`, `sweep.Sweep.run`, `guardrails.batch_resolves`, `autoloop.plan/cycle` | `curriculum.min_runs: 5`, `window_runs: 20`, `plan_frontier_window: 1` | `<pack>.tier_promoted`, `<pack>.curriculum` | `test_tier_promotion_gates_the_sweep_and_the_planner` |
| Saturation: cases passed on each of their last K runs; above the share the crank and the cycle say harder cases are wanted and list failed non-golden inputs as candidates (operator-followed runs then grow golden) | G-B5 | `rigor.saturation`, `curriculum.audit`, `crank._rigor_view` | `eval.saturation_k: 3`, `eval.max_saturated_share: 0.8` | `<pack>.saturation` | `test_saturation_flags_a_set_the_agent_always_passes` |
| Real-pack golden gates in validate (strict = not fixture; empty sets exempt): negative controls declared, every allowed tool and child agent declared exercised, a hard-tier share | G-B5, G-P16, G-B11 | `validate.validate_pack(strict=)`, `rigor.declared_uncovered/hard_tier_problem` | `eval.require_controls`, `eval.require_tool_coverage`, `eval.hard_tier: 3`, `eval.min_hard_share: 0.2` | none (validation error) | `test_validate_refuses_real_pack_without_hard_tier_controls_or_coverage` |
| Coverage measured from traces: which allowed tools / child agents the model called on each case (`origin: agent`), uncovered, declared-but-unexercised | G-B11 | `rigor.tools_called/coverage` | — | — | `test_eval_reports_tool_coverage` |
| Negative controls: a control the comparison lets pass refuses the eval | G-P16 | `rigor.check_controls`, `eval.run_eval` | — | `<pack>.eval_integrity` | `test_negative_control_that_passes_refuses_the_eval` |
| Verifier re-audit of every golden expected value (validate reports, eval flags suspect) | G-P16, G-D8 | `rigor.expected_rejections`, `validate.validate_pack`, `eval.run_eval` | — | `<pack>.eval_integrity`, `<pack>.suspect_case` | `test_validate_reaudits_golden_expected_with_the_verifier` |
| Suspect cases: failed with one identical signature by 2+ models over `min_evals` runs (since the last clearance) or rejected by the verifier; excluded from every score until a human clears it (`clear_suspect`, source human) | G-D8 | `rigor.history_suspects/suspect_state/flag_suspect/clear_suspect` | `eval.suspect.min_evals: 3` | `<pack>.suspect_case` | `test_case_failed_by_all_models_is_quarantined` |
| Sweep `broken_task`: one failure cluster (or one error message) above the share of the first `window` completions pauses the sweep | G-D8 | `sweep.Sweep._broken` | `sweep.broken.window: 20`, `sweep.broken.max_cluster_share: 0.6` | sweep stop reason `broken_task` | `test_sweep_pauses_on_a_dominant_failure_cluster` |
| Human quality baseline on the golden set: score minus baseline on every eval row and on the crank's golden view | G-P24 | `rigor.human_delta`, `eval.run_eval`, `goldenview.golden_view`, `crank.render` | — | — | `test_human_baseline_delta_on_eval_and_crank` |
| Objective hash (problem.md, output schema, eval compare + threshold, verifier id) on every eval and refinement; refine refuses on a mismatch with the record until the operator records `<pack>.objective` (human only); adoption refuses across hashes | G-P19 | `rigor.objective_hash/objective_on_record/objective_mismatch/record_objective`, `autoloop.refine` | — | `<pack>.objective` | `test_objective_change_without_operator_event_refuses_refinement` |

### `run_eval` result shape

Top level: `agent`, `manifest_hash`, `objective_hash`, `golden_file`, `threshold`, `compare`, `samples` (draws per
case), `min_case_rate`, `confidence`, `min_stratum_cases`, `controls` `{declared, failed_as_expected, passed}`,
`rejected_by_checks` `[{case_id, violations}]`, `suspect` `{case_id: reason}`, `coverage` `{tools: {tool: [case
ids]}, uncovered, declared_unexercised}` (primary model), `human_baseline` (`{score, source, n, delta}` or null),
`frontier`, `frontier_score`, `models`, `primary`, `pass`, `summary`.

Each `models[]` row: `model`, `score` (robust case pass rate over counted cases, string to 4 places), `passed`,
`counted`, `excluded` (fixture-excluded and suspect cases), `parity`, `mean_cost_usd`, `mean_latency_ms`, `samples`,
`interval` (`{k, n, rate, lo, hi, confidence}` on the robust score), `pass_at_1`, `pass_at_k` (k = samples),
`sample_interval` (over all draws), `strata` (`{key: {value: {passed, counted, score, interval}}}` for each
configured tag key present plus `tier`), `curriculum` (`{mastered_tier, frontier_tier, gaps}` or null), `zero_signal`
(case ids with no passing draw), `human_delta`, `cases`.

Each `cases[]` entry: `id`, `run_id` and `status` (first draw), `passed` (robust: passes / samples >=
min_case_rate), `passes`, `samples`, `pass_rate`, `diffs` (of the first failing draw), `counted`, `suspect`, `tags`,
`tier`, `exercises`, `tools` (called by the model across draws), `draws` (`[{run_id, status, passed, diffs}]`).

Not built: the golden expected value is re-audited by the agent's verifier only; guardrails need a schema-complete
output and are not re-run over expected values. `stats.gate_on_bounds` ships off so the C7 law (kill rule and judge
suspension on the point rate) holds unchanged; adoption keeps the point rule (score does not fall) and adds the
refusals above, because a lower-bound adoption gate on golden sets of a few cases would refuse every edit.
## JH-C11 wpI — long-horizon record

Tests: `tests/test_engine_c11_wpI.py`.  Config defaults are in `config/engine.yaml` and read through
`EngineConfig.outcomes`, `.reputation`, `.forecast`, `.autoloop_long_horizon` (old configs load unchanged).

- **Outcomes: lagged resolution of forward claims** (G-P14, G-D13, G-NCD10) — `engine/outcome.py`. An agent's
  manifest declares `outcome: {resolver, after_days}`; a pack declares `@outcome(id=...)` resolvers in
  `modules.outcome` (same registry pattern as `@drift`). A succeeded run is due `after_days` after creation or at its
  output's `resolves_at`; `resolve_due` (run at the start of every autoloop cycle) asks the resolver, records
  `<pack>.outcome` {run_id, due_at, resolved_at, lag_days, hit, verdict, claim, actual, confidence} and an outcome
  verdict. **Verdict precedence: human > outcome > agent** (`engine/verdicts.py` `PRECEDENCE`): an outcome replaces a
  judge's verdict, never a human's (the event is still recorded, `verdict_recorded: false`); a judge never replaces an
  outcome; a human replaces either. Migration `0005_verdict_source_outcome.sql` widens `verdict_source`. Golden growth
  and export count a declared agent's runs only once resolved (growth: resolved as a hit); the kill rule counts a run the
  world proved wrong (`outcomes.kill_on_outcome`); the crank reports claims, resolved, backlog, outcome rate beside the
  followed rate, Brier and binned calibration. Config `outcomes: {enabled, resolve_each_cycle, kill_on_outcome,
  calibration_bins}`. Tests: `test_outcome_verdict_sits_between_a_human_and_a_judge`,
  `test_forward_claim_is_resolved_after_its_horizon_and_scored`, `test_crank_shows_outcome_rate_beside_the_followed_rate`,
  `test_kill_rule_counts_a_run_the_world_proved_wrong`, `test_unresolved_runs_do_not_grow_golden_and_resolve_when_due`.
- **Reputation, trust tiers and leverage** (G-NAB2, G-NCD2) — `engine/reputation.py`. Score over the agent's whole
  history, weight `0.5 ** (age / half_life_runs)`, runs on superseded manifests at `carry_on_edit ** edits`; metrics
  (pass rate, override rate, conflict mass, cost per certified item, outcome hit rate). Each cycle one
  `<pack>.reputation` event per agent: the tier rises one step per cycle, falls at once, drops to the bottom on a kill
  or a judge suspension. Leverage of the tier in force: review sampling in `engine.verdicts --pending`, sweep workers
  and budget (`Sweep`, report `reputation_tier`), per-agent batch caps (`batch_resolves`). A halted agent gets
  `probation_runs` golden-input runs per cycle (`<pack>.probation`), so the kill rule can lift. Crank and autoloop
  reports carry a reputation section. Config `reputation: {half_life_runs, carry_on_edit, min_runs, probation_runs,
  start_tier, tiers}`. Tests: `test_reputation_decays_and_partly_carries_across_manifest_change`,
  `test_leverage_rises_one_tier_on_record_and_drops_at_once_on_kill`, `test_low_reputation_raises_review_rate_and_cuts_budget`,
  `test_halted_agent_gets_probation_runs_and_the_kill_rule_lifts`.
- **Value-ranked planning** (G-NCD3) — `engine/value.py`. A pack declares `@value(id, agent)` hooks in `modules.value`
  returning candidate inputs with a value; the engine drops done inputs and halted agents, ranks by value per expected
  cost and hands `ranked` to the planner; `batch_resolves` refuses a batch that passes over a higher-ranked input without
  a reason in `skips`; every plan is a `<pack>.plan` event (ranking, batch with ranks, skips). Config
  `autoloop.plan: {max_ranked, max_skip_without_reason}`. Test: `test_planner_cannot_skip_higher_value_inputs_without_a_reason`.
- **Dated forecasts and the loop roles' scored taste** (G-M3, G-D5) — `engine/forecast.py`
  (`python -m engine.forecast add|resolve|report`). `<pack>.forecast` / `<pack>.forecast_resolved` (Brier). Operator
  targets and every adopted refinement's target (metric, value, due week, p_hit) resolve once after the due week; the
  hit rate per maker is flagged too soft / calibrated / too aggressive around 50 %. When `autoloop.taste.require_forecast`
  the refiner must state `forecast: {p_adopt, golden_delta, holdout_delta, target}` (`edit_applies`) and the planner
  `p_pass` per item (`batch_resolves`); both are scored at once. A role whose mean Brier over its last `window` exceeds
  `max_brier` after `min_scored` is suspended: the refiner adopts nothing; the planner is replaced by the value ranking.
  Config `forecast: {target_hit_rate, band, window, metric_window_runs}`, `autoloop.taste`. Tests:
  `test_dated_forecasts_resolve_once_with_a_calibration_flag`, `test_forecast_cli_adds_resolves_and_reports`,
  `test_refiner_forecasts_are_scored_and_a_poorly_calibrated_refiner_is_suspended`,
  `test_planner_p_pass_is_scored_and_a_suspended_planner_is_replaced_by_the_value_ranking`.
- **The curator** (G-D9) — loop role `curator` (manifest role enum, frontier-only, `LOOP_ROLE_KEYS`, `LOOP_ROLES`;
  reference agent `agents/curator`, fixture `curator-v1`), guardrail `case_certified`, `engine/curate.py`
  (`python -m engine.curate confirm`). Each cycle (when refining) the curator proposes cases; code admits a case only
  when the agent's verifier certifies the expected output and its fail fraction over `attempts` runs of the agent's model
  plus one per eval-matrix model lies in `[min_fail, max_fail]`; admitted cases go to `golden.jsonl` (never held-out)
  with provenance, `difficulty` and `tier`; cases of an agent without a verifier wait in `eval/proposed.jsonl` for the
  operator. `<pack>.case_proposed` events give the curator's reward history; refinement reports golden score per tier.
  Config `autoloop.curate`. Tests: `test_curator_is_a_frontier_only_loop_role`,
  `test_curator_cases_admitted_only_if_verified_and_discriminating`, `test_case_without_a_verifier_waits_for_the_operator`.
- **Scaffold from a proven agent** (G-M17) — `engine/scaffold.py` `new_agent`
  (`python -m engine.scaffold new-agent <pack>/<name> --from <pack>/<proven>`): copies onboarding, prompts, guardrails,
  tools, access and the golden header (not the cases), records `derived_from: {agent, manifest_hash}` (manifest
  schema), validates or rolls back; `engine.validate` reports each lineage and whether the source has changed since.
  Test: `test_new_agent_from_a_proven_agent_carries_derived_from`.
## JH-C11 wpG — sweep & scheduling

The work runs while the operator sleeps, sized before it spends, earned by version, at the cheap hour, on the
event that calls for it, and measured as it scales.  Tests: `tests/test_engine_c11_wpG.py` (FixedClock and a
per-slot LaneClock; nothing sleeps).

| Mechanism | Gap ids | Code | Config | Events | Test |
|---|---|---|---|---|---|
| Store lease: one process per store, enforced (`engine_leases`, migrations 0005 sqlite + postgres); taken by the `engine.schedule`, `engine.sweep`, `engine.scale`, `engine.triggers` and `engine.autoloop` CLIs; renewed on every completion | G-NAB1 | `engine/schedule.py` `Lease`, `store_lease`; `engine/store.py` `lease_acquire/lease_release/lease_get` | `schedule.lease_seconds`, `schedule.heartbeat_seconds` | `<pack>.heartbeat` | `test_store_lease_enforces_one_process_per_store` |
| Scheduler: pack `schedule.yaml` jobs (`autoloop`, `sweep`, `triggers`, `remediate`) on anchor + k * every; missed ticks found on start, at most `max_catch_up` run (older ones recorded as skipped), halted agents and closed off-peak windows skipped; `--tick` / `--serve` (sleeps until the next due tick, sleep injectable); the crank reports the week's ticks and misses | G-NAB1 | `engine/schedule.py` `Scheduler.tick/serve`, `due_ticks`, `load_schedule`, `week_summary`; `engine/crank.py` `_operations` | `schedule.max_catch_up` | `<pack>.schedule` | `test_scheduler_runs_due_jobs_catches_up_missed_ticks_and_skips_halted`, `test_serve_sleeps_until_the_next_due_tick_on_the_engine_clock`, `test_schedule_and_triggers_files_are_validated` |
| Event-triggered runs: pack `triggers.yaml` maps a declared event type to an agent and an input template; per-trigger cursor = highest dispatched ledger index; each dispatch links the run to its event (`source_ref`); kill rule and once-per-input apply | G-P22 | `engine/triggers.py` `dispatch`, `load_triggers` | `triggers.max_per_poll` | `<pack>.trigger_dispatch` | `test_a_declared_event_starts_exactly_one_run_and_a_halted_agent_is_not_started` |
| Event-triggered gated mini-cycle: a failure cluster of at least `min_count` with new evidence, or a human override with a reason, runs crank, drift gate and refine (golden + held-out) at once; one adoption per cluster; cooldown; called at the end of every law-built sweep, by the scheduler's `remediate` job and by `engine.verdicts --run` on an override | G-NCD8 | `engine/remediate.py` `remediation_trigger`; hooks in `engine/sweep.py` `_finish`, `engine/verdicts.py` `main` | `autoloop.trigger.{enabled,min_count,cooldown_minutes}` | `<pack>.trigger` | `test_failure_cluster_triggers_a_gated_refinement_without_waiting_for_the_week`, `test_an_operator_override_on_the_cli_starts_the_mini_cycle_at_once`, `test_drift_holds_a_triggered_refinement` |
| Pre-flight sizing: need = runs x p95 cost (agent + judge) / pass rate x (1 + margin), time = runs / (workers x runs per hour per worker), against the budget; refuse with the arithmetic or cap; `--target-followed N` works backward to the runs needed; the crank reports p50/p95/max of cost, latency and tokens and runs per hour per worker | G-M6 | `engine/sizing.py` `preflight`, `percentiles_by_agent`; `engine/crank.py` `_operations` | `sizing.{margin,on_over}` | `<pack>.sizing` | `test_preflight_refuses_with_the_arithmetic_caps_and_works_backward` |
| Mandatory budget outside fixture packs for a sweep, a scaling ladder, a scheduled sweep job and an autoloop cycle (the cycle's act step starts nothing once it is spent) | G-M6 | `engine/sizing.py` `require_budget`; `engine/autoloop.py` `cycle`, `act` | `autoloop.budget_usd`, `sweep.budget_usd`, `scale.budget_usd` | none | `test_a_real_pack_needs_a_budget_for_a_sweep_and_a_cycle`, `test_autoloop_cycle_stops_spending_at_its_budget_and_reports_cycle_time` |
| Pilot gate and projection vs actual: a seeded sample runs first; projected cost, pass rate with Wilson interval, wall time and the settings it ran at; stop (`pilot`) when the projection exceeds the budget or the pass rate is under the kill rule; at the end projected vs actual, and whether the last adopted refinement's golden gain survived at scale | G-P15 G-D6 | `engine/sizing.py` `pilot_indices`, `project_pilot`, `final_projection`; `engine/sweep.py` `Sweep.run` | `sweep.pilot.{n,seed,refuse_if_projected_over_budget}` | `<pack>.sweep_pilot`, `<pack>.projection` | `test_pilot_projection_recorded_and_compared_and_overbudget_refused` |
| Burn-in, ramp and volume tiers per manifest_hash: under `burn_in_runs` (or failing) one worker and at most the burn-in count; then workers double per healthy step, halve on a failing one, and stop doubling when throughput gains less than `sizing.min_gain` (saturation); tiers cap total runs per version | G-M5 (and G-M6 marginal throughput) | `engine/rollout.py` `plan`, `Ramp`; `engine/sweep.py` `_apply_rollout`, `_ramp_step` | `rollout.*`, `sizing.min_gain` | `<pack>.rollout` | `test_a_new_failing_version_never_exceeds_one_worker_and_stops_at_burn_in`, `test_a_healthy_version_ramps_one_two_four_and_is_capped_by_its_tier`, `test_the_ramp_stops_doubling_when_more_workers_buy_no_throughput` |
| Mid-sweep switch to an adopted version: the agent is re-hashed every `kill_check_every` completions; remaining inputs run on the new version, entries carry their hash; the crank reports pass rate per version; the autoloop reports `cycle_seconds` | G-D12 | `engine/sweep.py` `_check_version`; `engine/rollout.py` `by_version`; `engine/autoloop.py` `cycle` | `sweep.reload_on_adoption` | `<pack>.version_switch` | `test_sweep_switches_to_the_adopted_version_mid_run`, `test_autoloop_cycle_stops_spending_at_its_budget_and_reports_cycle_time` |
| Off-peak tariff windows: `prices.yaml` `off_peak: {windows_utc, input, output, cache_read}` (DeepSeek rows filled); a call is billed at the rate in force on the engine clock; `sweep --off-peak` starts nothing outside a window (`window_closed`, next opening reported); the scheduler skips such ticks | G-M7 | `engine/offpeak.py`; `engine/config.py` `_tariff`, `off_peak_windows`; `engine/providers.py` `_Priced.price(clock=)`; `engine/sweep.py` `_open` | `sweep.off_peak` | none | `test_off_peak_windows_parse_and_price`, `test_off_peak_sweep_starts_nothing_outside_the_window_and_bills_the_off_peak_rate_inside` |
| Scaling ladder: the golden set (fixed mix) swept at each worker count and search_width/max_iterations setting (a setting runs as its own hash); pass rate, wall time, tokens, cost, speed-up and efficiency; stops at the budget; every sweep report carries start/end, wall_s, tokens, peak in flight and the worker slot of each unit | G-B1 | `engine/scale.py` `ladder`, `main`; `engine/sweep.py` `_measures`, `_drive` | `scale.{ladder,budget_usd}` | `<pack>.scaling` | `test_scaling_ladder_records_speedup_efficiency_and_stops_at_the_budget`, `test_sweep_report_records_wall_clock_tokens_and_runs_remediation` |
| Worker calibration: bursts at 1, 2, 4, ... until an added worker's marginal speed-up falls below the threshold; recommends workers and whether spare budget goes to search_width; the sweep takes it with `adaptive_workers` | G-D3 (calibration part) | `engine/scale.py` `calibrate`, `recommended_workers`; `engine/sweep.py` `build_sweep` | `sweep.min_marginal_speedup`, `sweep.adaptive_workers` | `<pack>.worker_calibration` | `test_worker_calibration_recommends_where_an_added_worker_stops_buying_time` |

`engine.sweep` (CLI) and the scheduler build every sweep through `build_sweep`, which applies all of the above
from config; a `Sweep` constructed directly runs with them off unless they are passed.
## JH-C11 wpH — run loop & tools

The mechanics of one run that the five interviews named and the engine lacked. Every knob has a default in
`config/engine.yaml` read through `engine/config.py` (`run_loop`, `shared_memory`, `risk`, `faults`, `sandbox`),
so older config files still load. Tests: `tests/test_engine_c11_wph.py`.

| gap ids | mechanism | config | event / column | test |
|---|---|---|---|---|
| G-M9, G-NCD6, G-NAB4(c) | `engine/staging.py` `EffectStage`: a candidate's `write`/`external` tool calls are validated and access-checked at once (`ToolSpec.prepare`; the model gets a `staged` receipt) and held; the certified candidate's writes commit in one store transaction, then its commands go through the gateway; a rejected (or not selected) candidate's effects are discarded and listed on its trace. Closes the double event of CONTRACT.md LIVE TURNS | `loop.rejected_side_effects: record\|drop` | `<pack>.rejected_side_effect`; trace `effects` | `test_event_appended_by_a_rejected_candidate_never_reaches_the_ledger`, `test_rejected_side_effects_drop_policy_keeps_them_on_the_trace_only`, `test_rejected_candidate_leaves_no_event_or_command` |
| G-NAB4, G-NCD5 | `engine/risk.py` `RiskGuard` in `AdapterGateway.command`: per-run and per-ISO-week command caps, per-slot `exposure_field`/`max_exposure`, stake ≤ `max_fraction_per_action` of the slot's remaining `capacity`, `irreversible` slots wait for a human `approval` (`engine.risk approve`), one loss ≥ the ruin threshold halts the agent (kill rule, sweep, planner, gateway) until a human `lift` | `risk.*`; adapters.yaml slot `irreversible`, `exposure_field`, `max_exposure`, `capacity`, `max_fraction_per_action`, `ruin_threshold` | `<pack>.risk_block`, `command_sent`, `approval`, `loss`, `ruin_halt`, `ruin_lift` | `test_external_cap_blocks_the_next_command`, `test_irreversible_command_waits_for_human_approval`, `test_command_above_stake_fraction_is_blocked`, `test_one_ruinous_loss_halts_the_agent_despite_a_good_average` |
| G-D11 | `engine/fanout.py` `fan_out`: `agent.<pack>.<child>` with `inputs: [..]` runs the parts (× alternatives) concurrently, the certified alternative with the most accept mass kept per part; only certified children cite | `loop.fanout` (engine.yaml) and manifest `loop.fanout` | column `fanout_group` | `test_orchestrator_fans_out_children_in_parallel_and_cites_only_certified`, `test_fanout_runs_alternatives_per_part_and_keeps_one` |
| G-B3 | `siblings.message` tool + `Bus` (inbox delivered at turn boundaries, cap and drop record, per-run budget); `engine__clarify` offered to children while the parent has budget, status `needs_clarification` returns the question, `clarifies` answers it as a revision; `engine/consensus.py` disagreement among passing candidates on the golden compare fields + one reconcile turn; crank `coordination` (messages per child run) | `loop.messaging`, `max_inbox_per_turn`, `max_messages_per_run`, `max_clarifications_per_run`, `reconcile` | `<pack>.message`, `<pack>.disagreement`; column `clarification`; status `needs_clarification` | `test_siblings_exchange_messages_and_the_inbox_cap_drops_the_excess`, `test_message_budget_and_messaging_off_refuse_the_tool`, `test_child_needing_clarification_returns_a_question_not_a_failure`, `test_passing_candidates_that_disagree_are_recorded_and_reconciled` |
| G-B4 | `engine/runctx.py`: manifest `loop.fork_context` gives children the parent's context (+ sha256); `notes.write` notes return in the next iteration's feedback; `scratch.write`/`scratch.read` share certified findings across a sweep (scope per sweep) or a fan-out, read into `memory.scratch` | `loop.max_notes_chars`, `memory.shared_scratch.max_tokens` | `<pack>.scratch`; columns `forked_from`, `context_sha256` | `test_forked_child_context_hash_equals_the_parents`, `test_notes_from_iteration_one_appear_in_iteration_two_context`, `test_sweep_workers_share_findings_through_the_scratch` |
| G-P13 | `Runner.run(session_id=, supersedes_run_id=)`, `engine.run --session/--supersedes`; the session's earlier turns in the context; `runctx.links` both ways; `engine.export --format session`; golden cases with `session: [..]` replayed turn by turn | `memory.session_turns` | columns `session_id`, `supersedes_run_id` | `test_session_runs_export_as_one_ordered_trace_and_supersede_links_both_ways`, `test_a_golden_case_may_be_a_session_replayed_turn_by_turn`, `test_cli_links_a_run_to_a_session_and_the_run_it_revises` |
| G-B17 | `engine/sandbox.py` + `engine/sandbox_child.py`: tools declared `sandbox=True` or targeting a network host run in `python -I -B` with a per-run temp workspace (deleted at run end, quota-checked), an empty environment, and an irremovable audit hook refusing connects/lookups to ungranted hosts, process spawning, native loading and writes outside the workspace. NOT isolated: reads of files the OS user can read, CPU/memory (timeout only), native extensions below the socket layer | `tools.sandbox`, `workspace_quota_mb`, `sandbox_timeout_seconds` | trace tool call `sandbox: {id, exit}` | `test_a_sandboxed_tool_cannot_reach_an_unlisted_host_even_when_the_access_check_is_bypassed`, `test_the_sandbox_is_a_scrubbed_process_with_a_quota_bound_workspace` |
| G-B21 | `engine.replay <run_id> --from I:C [--model]`: candidates before the point copied from the stored trace and re-checked, the point restarts from its stored first message, the rest runs live; effects never re-sent | none | column `replayed_from` (`<run_id>@I:C`); trace `origin: stored` | `test_replay_from_iteration_2_reproduces_the_original_output_byte_identical`, `test_replay_cli_exits_zero_when_identical` |
| G-B20 | `engine/faults.py` `FaultInjector` (seeded per run and call) on tool reads (error / stale / altered) and adapter commands (error); `python -m engine.faults` soak | `faults.rate`, `faults.kinds`, `faults.seed` | `<pack>.fault`, `<pack>.fault_soak` | `test_injected_altered_row_is_caught_by_cited_values_match`, `test_soak_records_that_every_faulted_run_failed_closed`, `test_adapter_command_fault_and_seeded_draws` |

Migrations `0004_zz_c11_wph_run_links.sql` (sqlite rebuilds `agent_runs` to widen the status CHECK; it sorts
after `0004_verdict_source` and before every `0005_*`, so later column additions alter the rebuilt table;
postgres alters in place). The seven link columns are bound to the run's ledger entry when set and frozen after
insert. A staged effect cannot be cited by the candidate that staged it: it does not exist until certified.
## JH-C11 wpE — judge & verification integrity

New module `engine/integrity.py` (mechanism only); hooks in autoloop, sweep, verdicts, guardrails, builtin_tools,
crank, export, distill, loop, providers, traces, manifest, run, eval.  Tests: `tests/test_engine_c11_wpE.py`.

| gap | mechanism | config | event | test |
|---|---|---|---|---|
| G-NAB8 | an override or `wrong` on a succeeded run carries `correction {path: value}` (field named in the reason, value differs from what the judge was served, honeypots included); stored on the verdict; corrections become preference pairs; a honeypot is hit only when the correction restores the value | `autoloop.judge.require_correction` | `<pack>.verdict` gains `correction` | `test_override_without_correction_fails_guardrail`, `test_correction_becomes_a_preference_pair`, `test_honeypot_hit_requires_restoring_the_value` |
| G-P11 | `verdicts --expected JSON` on an override; `grow_regressions` appends those runs as golden cases tagged `regression` (provenance "corrected by operator"); a judge's verdict can never carry `expected`; the crank lists failure clusters no regression case pins | `autoloop.grow_from_corrections` | `<pack>.golden_grown` | `test_operator_correction_becomes_a_regression_case_and_a_judge_correction_never_does` |
| G-M18 | a human override on a succeeded run names an output field or is `--unspecific`; unspecific overrides are excluded from the crank's override ranking | `verdicts.require_specific_override` | `<pack>.verdict` gains `unspecific` | `test_human_override_naming_no_field_is_refused_and_an_unspecific_one_steers_nothing` |
| G-M12 | operator overrides of a judge and its missed honeypots (re-served with the same plant) become the judge's `eval/golden.jsonl`, operator confirmations its `eval/holdout.jsonl`; `eval_judge` scores it each cycle; `refine_judge` adopts a judge edit only if it catches more misses and the held-out score holds | `autoloop.judge.learn_from_misses` | `<pack>.judge_case`, `<pack>.refinement` (agent = the judge) | `test_an_operator_override_of_an_agent_followed_adds_one_judge_case`, `test_a_judge_edit_that_drops_its_score_is_rejected` |
| G-P8 | a pack with `panel_min` judges judges by panel; each verdict an RI observation (`Judgement.observe_verdict`) fused with conflict kept; a verdict only on agreement, else the run waits (first in the queue); a suspended member drops out | `autoloop.judge.panel_min`, `require_agreement` | `<pack>.verdict` gains `panel`, `conflict`; `<pack>.judge_disagreement` | `test_two_judges_that_disagree_record_no_agent_verdict_and_the_run_goes_first_in_the_queue`, `test_an_agreeing_panel_records_the_verdict_and_a_suspended_member_drops_out` |
| G-B8 | a judge never grades its own model's run (`frontier.yaml judge_model` lets a judge run an independent model); collusion (share of operator-rejected runs the judge passed) suspends it; judged roles get AccessDenied on grader runs, honeypot/trap/judge events and judge files; a planner batch leaning on agent-only passes is refused | `autoloop.judge.require_distinct_model`, `max_collusion_rate`, `min_collusion_compared`, `autoloop.plan_max_agent_only_share` | `<pack>.collusion` | `test_a_judge_on_the_model_that_made_the_run_is_refused`, `test_a_judge_that_passed_what_the_operator_rejected_is_suspended_for_collusion`, `test_a_worker_cannot_read_the_grader`, `test_a_planner_batch_leaning_on_agent_only_passes_is_refused` |
| G-B7 | graded honeypots (single / paired / citation) with per-tier miss rates; answer-key traps under `trap_dir` for agents whose access reaches it; `no_forbidden_reads` guardrail; `report_anomaly` output recorded; per-cycle cheat rate, a rising rate above the gate halts refinement (the judge's too); honeypot miss gate lowered to 0.05 | `autoloop.honeypot_tiers`, `traps_per_cycle`, `trap_dir`, `max_cheat_rate`, `judge.max_missed`, `integrity.forbidden_reads` | `<pack>.trap`, `<pack>.anomaly`, `<pack>.cheat_rate` | `test_a_worker_that_reads_the_answer_key_fails_and_the_trap_says_concealed`, `test_graded_honeypots_map_the_limit_of_what_the_judge_catches`, `test_a_rising_cheat_rate_halts_refinement` |
| G-P6 | `verdicts --pending` ordered by monitor flag, panel disagreement, conflict mass, age; crank section per agent: run and judge latency, hours to the first human verdict, queue size and age; an SLA breach is logged | `review.pending_order`, `review.sla_hours` | `<pack>.review_backlog` (reason `sla`) | `test_pending_lists_the_highest_conflict_first`, `test_crank_reports_stage_timings_verification_cost_and_operator_time` |
| G-B18 | verification cost / production cost per agent; every Nth agent verdict sampled for human review; the sweep stops (`review_backlog`) and the autoloop plans nothing while the unreviewed sample exceeds the cap | `review.sample_every`, `review.max_backlog` | `<pack>.review_backlog` (reason `sample`) | `test_a_sweep_stops_with_review_backlog_when_the_sample_is_not_reviewed` |
| G-NCD1 | human verdicts carry `review_seconds` (the CLI measures it); operator cost per review against agent cost per certified run and judge agreement give delegate / operator / insufficient per agent, which sets that agent's review sampling interval | `economics.*` | `<pack>.delegation` | `test_crank_recommends_delegating_reviews_only_below_operator_rate_and_above_agreement` |
| G-B6 | providers capture reasoning (`Completion.reasoning`: Anthropic thinking blocks, `reasoning_content`) per candidate, hashed; role `monitor` reads it with `reasoning.read` (monitor only) and flags; a flag halts the agent until a human verdict; `reasoning_guard` keeps reasoning out of the judge's read, refiner evidence, golden growth, export and distill; reasoning-motivated refinements are capped per window; monitorability trended | `monitor.*` | `<pack>.monitor`, `<pack>.intervention`, `<pack>.monitorability` | `test_provider_reasoning_is_captured`, `test_scheming_reasoning_is_flagged_never_reaches_the_judge_and_halts_its_agent`, `test_a_refinement_citing_a_flag_past_the_cap_is_refused` |
| G-B22 | `integrity.safeguards(engine, pack, path)` (kill rule with monitor halts, judge suspension, review backlog) called by `engine.run` (refuses a halted agent), `engine.sweep` (a suspended judge records nothing; a judged sweep plants honeypots), `engine.eval`, `engine.autoloop` | `safeguards.paths` | `<pack>.safeguards` | `test_with_a_suspended_judge_a_judged_sweep_records_no_agent_verdict`, `test_safeguards_run_on_every_listed_path_and_the_run_cli_refuses_a_halted_agent` |

Operator-visible consequences: a judge's output schema must declare a `correction` object (load fails while
`require_correction` is on); with `require_distinct_model` on, a judge running the same model as the agents it grades
records no verdict until `frontier.yaml judge_model` names another model; `--no-refine` also skips the judge's learning.
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
## JH-C11 wpC — experiments

What a component, a framing, a point in time, a shared channel and a long horizon do to an agent's score, measured
rather than assumed.  One plumbing module, `engine/experiment.py`: an `Experiment` rides on `Runner.experiment`
(hooks in `loop.Runner.run` / `_iterate`) and can swap an agent for a variant, frame its context, hold it to a case's
`as_of`, and isolate one batch's event channel.  Variant, framed and soak runs are *experiment runs*
(`is_experiment_run`: manifest hash `x-<sha256>` or a `soak:` session); the kill rule (`experiment.latest_runs`), the
judge's queue (`autoloop.unjudged`), reputation, tier promotion and suspect detection leave them out.  Knobs:
`eval.ablations`, `eval.ablation_holdout`, `eval.isolate_events`, `eval.backtest`, `eval.probes`, `eval.grid` and a
top-level `soak` block in `config/engine.yaml`, read through `EngineConfig.experiments` with defaults.  Tests:
`tests/test_engine_c11_wpC.py`.

| Mechanism | Gap ids | Code | Config | Event | Test |
|---|---|---|---|---|---|
| Ablation: golden (and held-out) scored whole, then with one component removed: each grounding source, long-term memory, each `## ` section of skills.md / workflow.md, the whole onboarding, the child agents (the one-agent topology on the same inputs: agent tools withdrawn from the model and from its access), and everything at once (the model alone); delta per component; `python -m engine.ablate` writes `eval/ablation-<date>.{md,json}` | G-B2, G-D14 (ablation part) | `engine/ablate.py` `ablate`, `components`, `write_report`, `main` | `eval.ablations`, `eval.ablation_holdout` | `<pack>.ablation` {component, kind, class, score_full, score_ablated, delta, intervals, held-out scores} | `test_ablation_reports_component_contributions`, `test_memory_that_adds_nothing_is_credited_nothing`, `test_orchestrator_with_children_ablated_scores_lower_and_the_event_carries_both_scores`, `test_components_split_onboarding_sections_and_withdraw_children`, `test_ablation_runs_never_trip_the_kill_rule` |
| Attribution: credit shares of the full score (the model alone, each component, the interaction left over); data vs method from the ablation deltas and from adopted rung-1 / rung-2 refinement gains; who directed the agent's outputs (operator, the loop's planner, a declared event, an orchestrator) with succeeded and followed counts | G-B2 (B84), G-D14 (D152) | `ablate.ablate` (`credit`), `refinement_gains`, `output_origins` | — | — | `test_ablation_attributes_outputs_and_data_versus_method_gains` |
| Factorial grid: every level of every factor in the agent's `eval/grid.yaml` (model, prompt file, grounding set, skills / workflow file versions) crossed; each cell scored on golden and held-out; one-at-a-time and grid-averaged effects, the full change, and the residual (full change minus the sum of main effects); `eval/grid-<date>.{md,json}` | G-P23 | `engine/grid.py` `run_grid`, `effects`, `load_factors`, `write_grid`, `main` | `eval.grid.{factors,max_cells,holdout}` | none (an artifact, like the parity matrix) | `test_two_by_two_grid_reports_main_effects_and_a_planted_interaction`, `test_grid_refuses_too_many_cells_and_unknown_factors` |
| Framing-invariance probes: every golden case under two framings (counterpart human vs agent; without vs with a test cue; without vs with the operator's preferred wrong answer, taken from the case's negative control or one expected figure altered) placed as structured `framing` in the context; divergence on the compare fields per kind with its Wilson interval; a sycophancy divergence landing on the preferred value is marked; a kind above `max_divergence` blocks adoption (`autoloop.refine` calls `experiment.adoption_gate` on the candidate) | G-B19 | `engine/probes.py` `run_probes`, `preferred_wrong`, `main`; `experiment.adoption_gate`; hook in `autoloop.refine` | `eval.probes.{kinds,frames,max_divergence,on_adoption}`; a golden header's `probes.frames` overrides | `<pack>.probe` | `test_a_responder_keyed_on_the_test_cue_diverges_and_is_flagged`, `test_sycophancy_probe_states_a_wrong_preferred_answer_and_sees_the_output_bend`, `test_divergent_probes_block_adoption_through_the_gate` |
| Point-in-time backtests: a golden / held-out case may carry `as_of`; every run of that case (children included) reads only events observed and runs created at or before it, and rows of tables that declare `as_of_field` (pack.yaml) dated at or before it; an undated table is listed (`report`) or refused (`refuse`); every tool call on the trace carries the cutoff; the context carries `as_of`; the `no_future_citation` guardrail is added to the run; the backtest score is reported apart on each model row | G-D10 | `experiment.query_events`, `check_run`, `visible_runs`, `visible_table_rows`, `future_citations`, `backtest_summary`; hooks in `builtin_tools`, `memory.assemble_working_context`, `tools.ToolRegistry.call`, `eval.load_golden` / `run_eval`; `guardrails.no_future_citation`; `config/pack.schema.json` `as_of_field` | `eval.backtest.unfiltered: report` or `refuse` | none (trace field `as_of`) | `test_as_of_case_cannot_read_or_cite_the_future`, `test_a_backtest_reads_only_dated_rows_of_a_table_that_declares_its_date` |
| Evaluation isolation: an eval (and each trap and honeypot batch of a cycle) is one batch; a run cannot see events whose `source_ref` is a run of another case of the batch, nor those runs; the engine's grounding and memory reads are filtered silently; a read the model asked for that would have crossed is recorded and fails the case | G-B23 | `experiment.Experiment` (`begin_case`, `end_case`, `started`, `hidden`), `query_events`, `check_run`, `visible_runs`, `isolated_batch`; hooks in `eval.run_eval`, `autoloop.cycle` | `eval.isolate_events` | `<pack>.side_channel` | `test_isolated_eval_runs_cannot_read_each_others_events_and_a_try_is_a_side_channel`, `test_trap_and_honeypot_batches_isolate_each_top_level_run` |
| Long-horizon soak: N runs in one `soak:` session over the golden inputs with memory live and compaction run whenever due; pass rate (Wilson), mean conflict mass and cost by run-age bucket, first-to-last decline, degraded flag; the production horizon (longest session) against the longest soak: adoption refused while the evaluated horizon is shorter than `min_horizon_ratio` x production | G-B12 | `engine/soak.py` `soak`, `production_horizon`, `evaluated_horizon`, `horizon_refusal`, `main`; `experiment.adoption_gate` | `soak.{cycles,buckets,max_decline,min_horizon_ratio,on_adoption}` | `<pack>.soak` | `test_a_fixture_agent_whose_memory_grows_until_it_fails_shows_the_decline_by_age`, `test_adoption_is_refused_while_the_evaluated_horizon_is_shorter_than_production` |

The four CLIs (`engine.ablate`, `engine.grid`, `engine.probes`, `engine.soak`) run the path-`eval` safeguards first:
`test_experiment_clis_run_against_a_store_and_write_their_reports`.  `run_eval` gains `experiment=`; its result gains
`side_channels` and `experiment` at the top and `backtest` on each model row; each case entry gains `as_of`.

Limits, stated: an ablation removes a component from the agent as loaded (the variant never touches a file, so no
pack copy is needed); the attribution of an output to the operator counts every top-level run neither planned,
triggered nor delegated, plain eval runs included.  The probes' framing is structured data: how a real model reads it
depends on the words a pack supplies through `eval.probes.frames` or the golden header.  The soak's horizon gate
compares runs in a chain; days are reported beside them, not gated.  Isolation scopes one batch; plain eval runs still
share the event log with production runs outside the batch, as before.
