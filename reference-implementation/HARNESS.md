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
