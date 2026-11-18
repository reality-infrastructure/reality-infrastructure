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
