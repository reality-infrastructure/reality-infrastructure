# SPEC — JENSEN HARNESS ENGINE (domain-agnostic)

Source: Jensen Huang (NVIDIA) × Harrison Chase (LangChain) interview, 2026,
as distilled in the Aug 26 thread ("agentic-harness-spec.md" + "jensen-build-spec.md").
Vendor products (Nemotron, NIM, OpenShell, DGX) excluded — mechanisms kept.

(Operator-supplied spec, recorded verbatim on 2026-10-16 as the source of contract JH-C0..C6.)

This document has four parts:
- PART 1 — Traceability: every principle from the interview → the engine component that implements it
- PART 2 — The engine: every component, its interface, its schema, its invariants
- PART 3 — Build sequence: seven contracts (C0–C6), one fresh Claude Code session each
- PART 4 — Domain pack: how any domain plugs in (Registry Signal is pack #1, not part of the engine)

Rule for Claude Code: the engine NEVER contains domain words. No "parcel",
"lead", "offer", "deal". Domains supply nouns; the engine supplies mechanism.

---

## PART 1 — TRACEABILITY (nothing from the interview is dropped)

| # | What Jensen said / the principle | Engine component | Where |
|---|---|---|---|
| 1 | Model is the ingredient; the harness makes it a product | Agent behavior lives only in versioned config files | §2.1 Manifest |
| 2 | Agentic system = grounded + tools + memory + safeguards + iterate-until-done | Manifest has exactly these five blocks | §2.1 |
| 3 | Different models need different prompts/tools | Per-model prompt variants inside the manifest | §2.1, §2.4 |
| 4 | "I always start all of my work with the frontier" | Default model for every agent = frontier via provider abstraction | §2.4 |
| 5 | "For a lot of things you never have to replace [the frontier]" | Orchestrator is pinned frontier; swap is disallowed for `role: orchestrator` | §2.13 |
| 6 | Cheap + fast intelligence → wider search → better answers | Cost/latency instrumented per run; `max_iterations` and `search_width` are tunables | §2.3, §2.11 |
| 7 | Super sub-agents: one job, insanely hard optimization problem | Exactly one `role: specialist` slot per domain pack (hard cap, config-enforced) | §2.14 |
| 8 | "Connect them to specialized tools… proprietary knowledge" | Tool registry with domain-supplied deterministic tools | §2.5 |
| 9 | "A whole team dedicated to refining that" | Refinement crank: scheduled weekly review report + refinement contract template | §2.19 |
| 10 | "We hire consultants, license external tools, outsource work" | Adapter layer: licensed components plug in behind a fixed interface | §2.15 |
| 11 | Coding/writing are general skills; domain intelligence is yours | Bespoke effort only in specialist + verifier; general work stays on orchestrator | §2.13, §2.14 |
| 12 | A company is a collection of proprietary workflows → harnesses | `workflow.md` per agent: the manual process being harnessed | §2.2 |
| 13 | Working memory, long-term memory, compaction | Three-tier memory: run context / event log + prior outputs / rolling compaction | §2.9 |
| 14 | Flywheel: use → data → smarter → more use | Event log + traces + verdicts + improvement ladder; crank is explicit, not automatic | §2.10–2.12, §2.19 |
| 15 | Optimize cost order: context → harness → model → post-training | Improvement ladder with gates; post-training gated on ≥500 verdicted traces | §2.17 |
| 16 | Post-train the model inside the harness | Trace export to training format — specialist only, never orchestrator | §2.18 |
| 17 | Consultant onboarding: mission, how it was done, access | Onboarding pack: `skills.md` + `workflow.md` + `access.yaml` | §2.2 |
| 18 | Security + access control or "impossible to deploy"; sandbox | Deny-by-default runtime, fail-closed, per-agent allowlists | §2.6 |
| 19 | Evals, benchmarks, guardrails — "that's the work" | Guardrails as code + eval harness on real golden sets + SME verdicts | §2.7, §2.12 |
| 20 | Own the crown jewels; don't outsource state | All configs, traces, events, evals in your repo + your Postgres; adapters must export everything | §2.10, §2.15 |
| 21 | Don't anthropomorphize — it's software; understand it | Every output traceable; failures debugged from traces, never blind re-prompt | §2.11 |
| 22 | "It's a tool… we know exactly how it's working" | Citation resolver: every output figure cites source rows or is rejected | §2.8 |
| 23 | LLM is good at proposing, not at self-certifying | Proposer/Verifier split: model proposes, deterministic code certifies | §2.8 |
| 24 | "The tools are arcane… blueprints put the pieces together" | `harness new-domain` scaffolder + reference pack = the blueprint | §2.20 |
| 25 | "Companies will be built on harnesses representing workflows of the past" | Phase order per domain: harness an existing manual workflow first | §2.20, PART 4 |
| 26 | Ambition: do what couldn't be done before | `scale_ratio` metric: items evaluated per run ÷ items a human evaluates manually | §2.11 |
| 27 | Model economics: specialize when good-enough is crossed | Eval matrix across models; downgrade only on eval parity, cost report kept | §2.16 |

---

## PART 2 — THE ENGINE

### Architecture (four layers)

```
            ┌──────────────────────────────────────────────┐
 HUMAN  ←→  │ L1  ORCHESTRATOR  (frontier, never replaced)  │  narrates, drafts, briefs
            └───────────────┬──────────────────────────────┘
                            │ calls as tool (one level deep)
            ┌───────────────▼──────────────────────────────┐
            │ L2  SPECIALIST  (the one bespoke super sub-   │  proposes → VERIFIER certifies
            │     agent per domain)                         │
            └───────────────┬──────────────────────────────┘
            ┌───────────────▼──────────────────────────────┐
            │ L3  ADAPTERS  (licensed components)           │  vendor pipes, your data
            └───────────────┬──────────────────────────────┘
 ═══════════════════════════▼═══════════════════════════════════════
 L4 SUBSTRATE: event log · agent_runs traces · verdicts · access runtime ·
               provider layer · memory/compaction · evals · improvement ladder
```

Repo layout (engine):

```
engine/
  run.py            # single entrypoint: python -m engine.run <pack>/<agent> [args]
  manifest.py       # load + validate manifests (§2.1)
  loop.py           # iterate-until-done runner (§2.3)
  providers.py      # provider abstraction (§2.4)
  tools.py          # tool registry (§2.5)
  access.py         # deny-by-default runtime (§2.6)
  guardrails.py     # output checks (§2.7)
  verify.py         # proposer/verifier contract + citation resolver (§2.8)
  memory.py         # three-tier memory + compaction (§2.9)
  events.py         # event log API (§2.10)
  traces.py         # agent_runs writer (§2.11)
  verdicts.py       # verdict CLI (§2.12)
  eval.py           # eval harness + model matrix (§2.12, §2.16)
  adapters/base.py  # adapter interface (§2.15)
  export.py         # post-training export, gated (§2.18)
  crank.py          # weekly refinement report (§2.19)
  scaffold.py       # harness new-domain (§2.20)
migrations/         # engine tables only
packs/
  _reference/       # blueprint pack, fixture data only, labeled as fixtures
  <domain>/         # real packs live here or in their own repos
IMPROVEMENT-ORDER.md
```

Dependencies: Python stdlib, `anthropic`, `psycopg` (or `supabase`), `pyyaml`,
`jsonschema`, `pytest`. NO agent frameworks (LangChain, LangGraph, CrewAI, etc.).

---

### 2.1 Manifest — the agent definition

One file per agent: `packs/<pack>/agents/<agent>/manifest.yaml`. The five
harness components and nothing else carry behavior.

```yaml
name: string                # unique within pack
role: orchestrator | specialist | worker
version: semver             # bump on any change; recorded on every trace
model:
  provider: anthropic | openai_compat | local
  name: string              # default: current frontier
  variants:                 # per-model prompt/tool overrides (principle 3)
    <model-name>: { system_prompt_file: path, tool_overrides: [...] }
grounding:                  # what it may read for context
  sources: [ { kind: table|file|event_query|agent_output, ref: string } ]
tools: [ tool_id, ... ]     # allowlist; must exist in tool registry
memory:
  working: { max_tokens: int }
  long_term: { event_queries: [...], prior_outputs: int } | null
  compaction: { after_days: int, summary_agent: string } | null
loop:
  max_iterations: int       # default 3
  search_width: int         # parallel candidate proposals per iteration, default 1
  stop_when: all_guardrails_pass | verifier_certified | iterations_exhausted
safeguards:
  output_schema: path       # JSON Schema
  guardrails: [ guardrail_id, ... ]
  verifier: verifier_id | null   # required when role=specialist
```

Invariants:
- MUST reject a manifest with unknown keys, unknown tools, or unknown guardrails (fail at load)
- MUST hash the manifest + skills + access files; hash stored on every trace
- NEVER allow a prompt string inside Python; prompts live in files referenced by the manifest

### 2.2 Onboarding pack — the "HR system for AI"

Per agent, beside the manifest:
- `skills.md` — mission; definition of good output; examples of good/bad output
- `workflow.md` — how the job was done manually before ("this is how it's previously been done"); who did it; how long it took; what they checked. This is the workflow-of-the-past being harnessed
- `access.yaml` — see §2.6

`skills.md` + `workflow.md` are injected as grounding on every run.

### 2.3 Loop — iterate until done

```
for i in 1..max_iterations:
    candidates = propose(context, n=search_width)
    for c in candidates:
        g = guardrails(c); v = verifier(c) if specialist
        if pass: return accept(c)
    context += failure_reasons(candidates)   # model sees why it failed
mark_failed(); discard output
```

- Every iteration, every candidate, every tool call is recorded in the trace
- Failure reasons fed back are guardrail/verifier messages, never free-form re-prompting

### 2.4 Provider layer

```python
class Provider(Protocol):
    def complete(self, system, messages, tools, **kw) -> Completion: ...
    def price(self, in_tokens, out_tokens) -> Decimal: ...
```

- Implementations: `anthropic`, `openai_compat` (covers DeepSeek, local vLLM, etc.)
- Model swap = edit manifest `model.name` only. Verified by test running the same agent on two model strings
- Prices live in `config/prices.yaml`, never hardcoded

### 2.5 Tool registry

```python
@tool(id="ns.name", effect="read" | "write" | "external", deterministic=True|False)
def fn(args: Schema) -> Result: ...
```

- Engine ships generic tools only: `events.query`, `events.append`, `agent_output.read`, `files.read`
- Domain tools are registered by the pack (§PART 4)
- `effect=write` tools only callable if access.yaml grants write on the target
- `effect=external` tools only via adapters (§2.15)

### 2.6 Access runtime — deny by default

`access.yaml`:
```yaml
tables:   { read: [...], write: [...] }
files:    { read: [glob...], write: [glob...] }
network:  [ host, ... ]        # provider host is implicit
tools:    inherited from manifest allowlist
```

- Enforced in `access.py` at every tool call, not by prompt
- Unlisted target → raise `AccessDenied`, trace marks `access_denied=true`, run fails closed
- Engine tables `agent_runs`, `events` are writable only through engine APIs, never via raw SQL tools

### 2.7 Guardrails — engineering, not vibes

Built-in guardrails (engine):
- `schema_valid` — output validates against `output_schema`
- `no_invented_keys` — output keys ⊆ schema keys
- `citations_resolve` — every cited source ref exists (§2.8)
- `no_fabrication` — any field marked `requires_source` must carry a citation or be null
- `bounded_size` — output under configured size

Domain guardrails registered by the pack. Guardrail failure = run failed, output discarded, failure persisted.

### 2.8 Proposer / Verifier split + citation resolver

The load-bearing rule: **the model proposes and explains; deterministic code certifies. Never the reverse.**

```python
class Verifier(Protocol):
    id: str
    def verify(self, proposal: dict, context: VerifyContext) -> VerifyResult:
        # returns certified: bool, violations: [str], recomputed: dict
```

- Required for every `role: specialist` agent
- Verifier recomputes every numeric claim it can; mismatches are violations
- Citation format, engine-wide: `{"ref": "<kind>:<table_or_path>:<id>", "field": "..."}`
- `citations.resolve(ref)` must return the source row/file or the guardrail fails
- No output field marked `traceable: true` in the schema may lack a citation

### 2.9 Memory — three tiers

| Tier | What | Lifetime |
|---|---|---|
| Working | the run's context window: grounding + tool results + iteration feedback | one run |
| Long-term | event-log queries + last N outputs of this agent + their verdicts | permanent (event log) |
| Compaction | rolling summaries of events older than `after_days`, written by a designated summary agent, stored as `events` rows of type `compaction.summary` with citations to the summarized range | permanent |

- Compaction summaries are themselves guarded (`citations_resolve`) and never replace raw events — raw rows are retained

### 2.10 Event log — the crown jewel

```sql
create table events (
  event_id     uuid primary key default gen_random_uuid(),
  entity_type  text not null,       -- domain noun, supplied by pack
  entity_id    text not null,
  event_type   text not null,       -- namespaced: '<pack>.<verb>'
  payload      jsonb not null,
  source       text not null,       -- 'human' | 'agent:<name>' | 'adapter:<id>' | 'pipeline:<id>'
  source_ref   text,                -- run_id, vendor record id, url
  observed_at  timestamptz not null,
  recorded_at  timestamptz not null default now()
);
-- append-only: no UPDATE/DELETE grants; corrections are new events of type '<pack>.correction'
```

Invariants:
- Every real action = one event. NEVER fabricate events
- Event types are declared in the pack's `events.yaml` with a payload JSON Schema; undeclared types rejected
- Adapters write here within the latency SLA declared in their scorecard (§2.15)

### 2.11 Traces — `agent_runs`

```sql
create table agent_runs (
  run_id          uuid primary key,
  pack            text, agent text, role text,
  manifest_hash   text, agent_version text,
  provider        text, model text,
  input_hash      text,
  iterations      jsonb,   -- per iteration: candidates, tool_calls, guardrail + verifier results
  output          jsonb,   -- null if failed
  status          text,    -- succeeded | failed_guardrail | failed_verifier | access_denied | error
  cost_usd        numeric, latency_ms int,
  items_evaluated int,     -- for scale_ratio (principle 26)
  parent_run_id   uuid,    -- orchestrator → specialist linkage
  human_verdict   text,    -- null until adjudicated
  verdict_reason  text,
  verdict_at      timestamptz,
  created_at      timestamptz default now()
);
```

- Failed runs are logged identically to successes
- `scale_ratio` = items_evaluated ÷ `manual_baseline_items` declared in workflow.md

### 2.12 Verdicts + evals

Verdict CLI: `python -m engine.verdicts <pack>/<agent> --pending`
- Shows output + citations; operator records `followed | overridden | wrong | n/a` + reason
- Verdict also appended to `events` as `<pack>.verdict`

Eval harness: `python -m engine.eval <pack>/<agent> [--models a,b,c]`
- Golden set: `packs/<pack>/agents/<agent>/eval/golden.jsonl`, each case = input + expected + `provenance` (where the real historical answer came from)
- Golden cases MUST come from real history; `provenance` required; fixture packs label cases `fixture: true` and are excluded from real-domain thresholds
- Prints one line: `PASS (k/n ≥ threshold)` or `FAIL (...)`; threshold declared in the golden file header

### 2.13 L1 — Orchestrator

- `role: orchestrator`, frontier model, swap disallowed by manifest validator
- The single human-facing surface: reads events, specialist outputs, adapter transcripts; writes briefs, drafts, summaries
- Does NO proprietary math. Any number it states must be a citation to a specialist output or event row (`citations_resolve` enforced)
- Calls the specialist as a tool (`agent.<pack>.<specialist>`), one level deep max; child run linked via `parent_run_id`

### 2.14 L2 — Specialist (the one bespoke super sub-agent)

- `role: specialist`, max ONE per pack (validator enforces `max_specialists: 1`; override requires an ADR file in the pack)
- Pack must declare `problem.md`: the insanely-hard optimization problem in one paragraph — decision variables, constraints, objective, why no vendor sells it
- Output = proposals with explanation + citations; Verifier certifies feasibility and recomputes figures
- Starts on frontier; the ONLY component eligible for model downgrade (§2.16) and post-training (§2.18)

### 2.15 L3 — Adapters (licensed components)

```python
class Adapter(Protocol):
    id: str
    def ingest(self, vendor_payload) -> list[Event]       # vendor → your event log
    def command(self, cmd: Command) -> CommandResult      # your system → vendor
    def suppression_check(self, entity_id) -> bool        # enforced before every command
    def export_all(self, since) -> Iterator[dict]         # data ownership guarantee
```

Non-negotiable adapter terms (encoded as tests):
- Every vendor record lands as `events` rows within declared latency
- Suppression list enforced before every outbound command
- Disclosure/opt-out flags carried on every command where the domain requires them
- `export_all` must return everything the vendor holds about your entities
- Swap = change `adapters.yaml` binding; zero code change in orchestrator/specialist

`VENDOR-SCORECARD.md` template per adapter slot: event latency, suppression enforcement, disclosure, export rights, swap cost, price. Build-vs-buy is reopened only with a filled scorecard as evidence.

### 2.16 Model economics

`python -m engine.eval <pack>/<agent> --models frontier,X,Y` produces a matrix: score, cost/run, latency. A downgrade is permitted only when score ≥ frontier score on the same golden set; the matrix is committed as `eval/matrix-<date>.md`.

### 2.17 Improvement ladder (cost order)

`IMPROVEMENT-ORDER.md`, enforced as process:
1. Grounding / context (cheapest)
2. Harness: prompts, tools, guardrails, loop params
3. Model swap (requires §2.16 parity)
4. Post-training (requires §2.18 gate)

Every refinement PR states which rung it is on and why lower rungs were exhausted.

### 2.18 Post-training export (gated)

`python -m engine.export <pack>/<specialist> --format sft|preference`
- Refuses to run unless `count(agent_runs where agent=specialist and human_verdict is not null) ≥ 500`
- Refuses for `role: orchestrator`
- Output = dataset file only; training/hosting is out of the engine's scope

### 2.19 Refinement crank

`python -m engine.crank <pack> --week <iso-week>` writes `crank/<week>.md`:
- runs, pass/fail rates, cost, latency, scale_ratio per agent
- verdict distribution; top override reasons
- guardrail/verifier failure clusters
- one recommended rung-1 or rung-2 change with the evidence rows

The crank is a report, not an autopilot. A human turns it into the next refinement contract.

### 2.20 Blueprint + scaffolder

`python -m engine.scaffold new-domain <pack>` creates the full pack skeleton (PART 4) with TODO markers. `packs/_reference/` is a complete working pack on labeled fixture data that passes every engine test — the blueprint someone else could deploy.

---

## PART 3 — BUILD SEQUENCE (one fresh Claude Code session per contract)

Each contract amends the previous; none is authorized until the previous is DONE.
All use the same anatomy. Shared CONSTRAINTS (apply to every contract):

- MUST keep engine code free of domain nouns
- MUST keep all agent behavior in pack files — zero prompts in Python
- MUST enforce access in code, fail closed
- MUST log every run, including failures
- NEVER add dependencies beyond the list in PART 2
- NEVER fabricate golden cases, events, or historical outcomes
- NEVER let the model self-certify numbers
- NEVER write outside the contract's IN scope

Shared STOP CONDITIONS: an assumption can't be verified from the repo → stop, report. Acceptance requires OUT-scoped work → stop, report. A migration conflicts with existing schema → stop, report.

---

### C0 — Core runner (manifest, loop, provider, access, guardrails, traces, eval)

OBJECTIVE: `python -m engine.run _reference/worker` executes a manifest-defined agent end-to-end on fixture data, guarded, access-enforced, traced to `agent_runs`, and `python -m engine.eval _reference/worker` prints PASS.

CONTEXT: New repo (name proposed at PLAN GATE, e.g. `harness-engine`). Postgres via env `DATABASE_URL`. Provider key via env.

SCOPE IN: §2.1–2.7, §2.11, §2.12 (eval only), `_reference` pack with one `worker` agent, `agent_runs` migration, IMPROVEMENT-ORDER.md.
SCOPE OUT: events table, memory tiers, verifier, orchestrator/specialist roles, adapters, verdict CLI, export, crank, scaffolder.

PLAN GATE: (a) manifest JSON Schema; (b) `agent_runs` DDL; (c) access enforcement call path; (d) the fixture domain for `_reference` (must be trivially deterministic, e.g. arithmetic or text classification with known answers), labeled `fixture: true`. HALT on any unverified assumption.

ACCEPTANCE:
1. Run exits 0, prints run_id; row has non-null iterations, cost, latency, manifest_hash
2. Eval prints `PASS`
3. pytest: unlisted table read → `AccessDenied`, run status `access_denied`
4. pytest: malformed output → `failed_guardrail`, output null
5. pytest: manifest with unknown key/tool → load error
6. Model swap: same agent on two model strings, no code change, both run_ids in PR
7. `pytest` green

DEPLOY: none. DONE: acceptance output in PR · feature branch, clean · migration verified with select · manifest/skills readable by a non-author · IMPROVEMENT-ORDER.md present.

---

### C1 — Event log, memory tiers, verdicts

OBJECTIVE: Agents read long-term memory from `events`, compaction writes cited summaries, and operators adjudicate runs via the verdict CLI.

SCOPE IN: §2.9, §2.10, §2.12 (verdict CLI), `events.yaml` declaration + validation, `events.query`/`events.append` tools, `_reference` gains declared event types.
SCOPE OUT: verifier, roles, adapters, export, crank.

ACCEPTANCE:
1. pytest: undeclared event_type rejected; payload schema enforced
2. pytest: UPDATE/DELETE on `events` fails (grants)
3. Compaction run writes a `compaction.summary` event whose citations all resolve; raw events still present
4. Verdict CLI records a verdict on a C0 run; matching `<pack>.verdict` event exists
5. `_reference/worker` run with `long_term` enabled shows event-query tool calls in its trace

---

### C2 — Proposer/Verifier, specialist slot, orchestrator composition

OBJECTIVE: `_reference/orchestrator` calls `_reference/specialist` as a tool; the specialist's proposal is certified by a deterministic verifier; the orchestrator's brief cites only certified figures.

SCOPE IN: §2.8, §2.13, §2.14, citation resolver, `max_specialists: 1` validator, `problem.md` requirement, `parent_run_id` linkage. `_reference` specialist = a small fixture knapsack/allocation problem with a deterministic feasibility checker.
SCOPE OUT: adapters, model matrix, export, crank.

PLAN GATE adds: draw the LLM-proposes / code-certifies boundary for the reference specialist as a list of fields owned by each side.

ACCEPTANCE:
1. pytest: seeded infeasible proposal → `failed_verifier`
2. pytest: seeded misstated figure → verifier recompute mismatch → violation
3. pytest: second specialist in a pack without ADR → load error
4. pytest: orchestrator manifest with non-frontier model swap → load error
5. Orchestrator run → child specialist run linked by `parent_run_id`; every number in the brief resolves via citations

---

### C3 — Adapter layer

OBJECTIVE: A licensed component plugs in behind the Adapter interface; its records land in `events`, suppression is enforced, and swapping vendors is a config change.

SCOPE IN: §2.15, `adapters.yaml`, `VENDOR-SCORECARD.md` template, two fixture adapters (`_reference/mock_a`, `_reference/mock_b`) implementing the same slot.
SCOPE OUT: any real vendor integration, any real outbound action (email, call, SMS, payment).

ACCEPTANCE:
1. pytest: mock ingest → events within declared latency
2. pytest: suppressed entity → command blocked, block logged as event
3. pytest: `export_all` returns every ingested record
4. Swap `mock_a` → `mock_b` in `adapters.yaml`; orchestrator run unchanged in code; both run_ids in PR

---

### C4 — Model economics

OBJECTIVE: `engine.eval --models` produces a committed cost/score/latency matrix and the validator blocks downgrades lacking parity.

SCOPE IN: §2.16, matrix writer, downgrade validator (manifest model ≠ frontier requires a matrix file showing parity).
ACCEPTANCE: matrix file generated for `_reference/specialist` across ≥2 models; pytest: downgrade without parity file → load error.

---

### C5 — Refinement crank + post-training export

OBJECTIVE: Weekly crank report generated from real traces; export refuses below gate and for orchestrators.

SCOPE IN: §2.18, §2.19.
SCOPE OUT: any training, fine-tuning, or model hosting.
ACCEPTANCE: crank report for a fixture week lists all required sections; pytest: export with <500 verdicts → refusal; pytest: export on orchestrator → refusal; pytest: export with fixture ≥500 verdicts → valid dataset file.

---

### C6 — Blueprint scaffolder + first real domain pack

OBJECTIVE: `engine.scaffold new-domain <pack>` produces a skeleton that loads; the first real pack is scaffolded in its own repo, consuming the engine as a dependency, with ONE worker agent harnessing an existing manual workflow.

SCOPE IN: §2.20; scaffolder; first real pack's worker agent only (its specialist is a separate later contract, after the worker has run in production).
PLAN GATE adds: locate the real historical data for the golden set and report the actual count before code. Fewer than 10 real cases → STOP.
ACCEPTANCE: scaffolded pack passes `engine.validate`; real worker eval PASS on real golden set; zero engine code changes required by the pack.

---

## PART 4 — DOMAIN PACK INTERFACE

A domain plugs in by supplying these files and nothing else:

```
packs/<pack>/
  pack.yaml            # name, entity types, max_specialists, manual baselines
  events.yaml          # declared event types + payload schemas
  problem.md           # the one insanely-hard problem (for the specialist)
  tools/               # domain tools, registered via @tool
  verifiers/           # deterministic verifier for the specialist
  guardrails/          # domain-specific output checks
  adapters.yaml        # slot → adapter bindings
  agents/
    <orchestrator>/    manifest.yaml skills.md workflow.md access.yaml
    <specialist>/      manifest.yaml skills.md workflow.md access.yaml eval/golden.jsonl
    <worker>/ ...      # optional harnessed workflows-of-the-past
```

Order of adoption for any domain (principle 25 → 7):
1. Harness one existing manual workflow as a `worker` (prove the pattern on the past)
2. Promote the human-facing summary job to the `orchestrator`
3. Write `problem.md`; build the `specialist` + verifier only once real outcomes exist for a golden set
4. License everything general behind adapters; fill the scorecard before building any adapter in-house
5. Turn the crank weekly; climb the improvement ladder in order

Example mapping (illustrative only — not engine code):

| Slot | Registry Signal pack | Any other domain asks |
|---|---|---|
| Worker | patrol-sheet QA | What manual check do I already do weekly? |
| Orchestrator | morning brief | Who is the human, and what do they read? |
| Specialist | allocation engine (which items, at what price, in what order) | What decision is a constrained optimization over data only I have? |
| Adapters | calling/inbound vendors | What is general, commodity, and rentable? |
| Event log | outreach, responses, dispositions, closes | What actions produce outcomes I can learn from? |

---

## CAVEAT (for Irvin, not Claude Code)

The interview is two harness vendors selling harnesses, and your own rule is
"don't chase harnesses." The engine is only justified if C6 ships a worker that
saves real review time on an existing workflow. Benchmark: if C0–C2 aren't
running a real pack within two weeks, stop and put the hours back into
Registry Signal's pipeline directly.
