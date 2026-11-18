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
