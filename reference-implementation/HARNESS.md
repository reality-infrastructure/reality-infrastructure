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
