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
