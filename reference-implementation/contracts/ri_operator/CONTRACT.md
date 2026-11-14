# CONTRACT: RI-OPERATOR — eight operator commands as one pack on the harness

```
status:   PLAN GATE (no code written; nothing pushed)
branch:   contract/ri-operator, cut from contract/irv-harness at 1be79e5
baseline: 777 passed, 1 failed, 1 skipped (2026-11-14, `python -m pytest -q` from
          reference-implementation/ in the worktree C:\Users\newce\ri-operator).
          The one failure is tests/test_audit_remediation.py::
          test_shipped_artifacts_match_live_machine, the path-dependent test already
          queued as contracts/queue/artifact-path-determinism.md. Not this contract's.
rulings:  R1-R3 below, made from the five interview transcripts at the operator's
          instruction (2026-11-14). The operator may overrule any of them at this gate.
```

## Context (read first, do not skip)

Eight agent skills written outside this repo passed a screen drawn from five
interviews (verification bottleneck, independent grader, limiting factor, objective
pinned before the result, learning by iteration, long horizons, productized). The
operator's order: package them as one system inside Reality Infrastructure, each with
its own command.

Two of the eight already live here: the agent pack harness (`engine/`, HARNESS.md) and
the evidence-only protocol (`forge/`, `ri_core/`). The other six are prompts in other
repos. What makes the eight a system is one property: every command's output (a
verdict, a constraint, a forecast, a watchlist row) is an event on the harness's
Merkle ledger, so a buyer can replay what their agents decided and on what evidence.

## The rulings

### R1 — Revenue: open source, paid deployment. No closed commands.

| Transcript | What it says | What it rules |
|---|---|---|
| Brown | The scaffold gets "disproportionate credit"; the capability is elsewhere. Evals that cannot see the real behaviour were the failure. | The command text is not the asset. A checker the buyer cannot inspect is a checker nobody can trust. |
| Schulman, Millidge, O'Neill | Anything a model shows in trajectories "can be distilled very easily"; what stays with a company is what it learns from its own deployment. | Closed prompts leak on first use. The durable thing is the buyer's own record, which only a deployment produces. |
| Musk | Customer service sold with "no integration needed", using the apps the buyer already has. "Don't make the AI lie." | Sell the install into the buyer's existing repo and tools. A truth instrument is not sold on hidden terms. |
| Patel | Progress follows whatever is verifiable; an agent that can check its own score works in parallel. | The buyer must be able to verify the verifier. That requires source. |
| Naval | Long-term games with long-term people; reputation is the leverage; code has zero marginal cost of replication. | The covenant is the reputation. Keep it and let the code spread at no cost. |

Ruling: NEUTRALITY.md stands unamended. The pack ships Apache-2.0. Revenue is the
covenant's sixth permitted line: paid engagements to deploy or integrate, with no
client influence over log format or fusion semantics.

Dissent on the record (Naval): "You won't get rich renting out your time." A paid
deployment is rented time. The ruling answers it only in part: the engagement is a
fixed, repeatable install rather than hourly work. Whether that is enough is the
operator's call and is not settled by the transcripts.

### R2 — Base: branch from contract/irv-harness. Baseline before any change.

| Transcript | What it says | What it rules |
|---|---|---|
| Brown | "Fork yourself", work, merge back; sub-agents start from forked context. | Fork the branch that already has the context. |
| Schulman, Millidge, O'Neill | Labs "stay at the frontier" of the lineage and diff from the last version; a cumulative task holds every line already won. | Build on the harness as it stands. Do not rebuild it on main. |
| Musk | Use conventional equipment first, then modify it; make the mistakes small. | Use the existing engine untouched; add a pack beside it. |
| Patel | A verifiable proxy lets work be checked before it merges. | Run the suite first and pin the number. Done: 777 / 1 / 1. |
| Naval | Compounding: get traction and do not let go; every reset starts trust from zero. | Do not reset onto main and lose ten harness contracts. |

Ruling: as branched. The engine, `ri_core/`, SPEC.md and every frozen module are OUT.

### R3 — Scope: five commands now, two next, foresight last. One real run each.

| Transcript | What it says | What it rules |
|---|---|---|
| Brown | Models now work over horizons longer than anyone has time to evaluate; "we never want to underestimate" again. | A command whose proof needs weeks of record (week, foresight) cannot be accepted in a day. It goes later. |
| Schulman, Millidge, O'Neill | Rungs too far apart do not climb; year by year does. Realism is a separate axis from difficulty. | Stage it. And accept on a realistic run, not a fixture alone. |
| Musk | "Make a little fab and see what happens"; work the limiting factor; start with the simplest task and march up the curve. | Ship what needs no engine port first. The port is the long pole, so it is its own contract. |
| Patel | Modular work that each agent can check locally parallelises; novels do not. | Eight commands, eight independent gates. No command's acceptance depends on another's. |
| Naval | Iterations, not hours. Proof of work is the calling card. Learn to sell, learn to build. | The first sale needs a logged record. Each command's acceptance includes one real run on the ledger. |

Ruling:
- **This contract:** `/ri-bottleneck`, `/ri-judgment`, `/ri-gate`, `/ri-pack`, `/ri-evidence`.
- **Next contract:** `/ri-scan`, `/ri-week`.
- **Its own contract:** `/ri-foresight` (ports the engine from `hyperliquid/atlas/foresight.py`).

## Non-Goals (hard boundaries)

- Do NOT modify `engine/`, `ri_core/`, `rights_events/`, SPEC.md, NEUTRALITY.md, LICENSE or `forge/`.
- Do NOT add a dependency.
- Do NOT copy any trading figure, wallet, venue name, client name or operator name into the pack.
- Do NOT claim a command works on the strength of its prompt. A command with no logged run is not delivered.
- Do NOT touch `contract/agent-record` or the checkout at `C:\Users\newce\Reality-Infrastructure`.

## Deliverables

```
packs/ri_operator/                 scaffolded by `python -m engine.scaffold new-domain ri_operator`
  agents/disprover/                the fresh-agent role for /ri-gate (manifest, deny-by-default access,
                                   output schema, guardrails, held-out set)
  events.py                        declared event types: constraint.named, judgment.run, gate.verdict
.claude/commands/
  ri-bottleneck.md                 from ~/.claude/commands/bottleneck.md; output contract appended as an event
  ri-judgment.md                   from ~/.claude/commands/judgment.md; same
  ri-gate.md                       from hyperliquid gate.md + rich disprove.md, domain nouns removed
  ri-pack.md                       wraps engine.scaffold / validate / run / verdicts / replay
  ri-evidence.md                   wraps forge/scaffold.py and the evidence-item rules of power-path PROTOCOL.md
tests/test_ri_operator_pack.py     pack validates; event types round-trip; gate verdict replays byte-identically
packs/ri_operator/PROVENANCE.md    each command's source path and sha256 at the time of copy
```

## Acceptance (deterministic)

- [ ] `python -m engine.validate ri_operator` exits 0 (paste).
- [ ] `python -m pytest -q` shows 777 + new passed, the same 1 failed, 1 skipped (paste).
- [ ] `git diff contract/irv-harness -- engine ri_core rights_events forge SPEC.md` is empty (paste).
- [ ] `grep -riE` for the banned nouns listed in PREREG.md over the pack and the five commands returns nothing (paste).
- [ ] Each of the five commands has one run on a real repository recorded on the ledger, and `python -m engine.replay <run_id>` passes for each (paste five).
- [ ] The `/ri-gate` run was made by an agent that did not see the builder's session (state how).

## Kill criteria

- A command cannot write its output as a declared event without an engine change: STOP. That is a finding about the harness, not something to code around.
- A real run cannot be produced for a command: that command is reported NOT DELIVERED. It is not replaced by a fixture.
- The baseline moves for any reason other than new tests: STOP.

## Plan gate

Open to the operator before any code:
1. Confirm or overrule R1, R2, R3.
2. Naval's dissent under R1.
3. Which real repository the five acceptance runs are made on.
4. Push: this branch is local only until the operator says otherwise.

## Plan gate — answered 2026-11-14

Answered from the five transcripts at the operator's instruction. Each is the
operator's to overrule.

### G1 — R1, R2, R3 confirmed. The Naval dissent is answered with a condition.

- Naval answers his own objection: "You will need to rent your time to get started. This is only acceptable when you are learning and saving."
- Musk: each stage's revenue pays for the next (the rocket funds the constellation).
- Schulman panel: what a company learns from its own deployment is the thing that cannot be distilled away. A deployment is where that record is made.
- Brown: the scaffold is not where the credit belongs, so it is not what to charge rent on.
- Patel: iterations compound; the first deployments are the iterations.

Ruling: paid deployment is the starting rung, priced as a fixed install and not by the
hour. It is acceptable only while each deployment adds to a reusable record. The
operator revisits R1 after the first paid deployment.

### G2 — The acceptance runs are made on `C:\Users\newce\tier-one`.

- Musk names customer service as the first market for agents: large, average-difficulty, no integration barrier. tier-one is that business.
- Schulman panel: accept on the realism axis, not on a puzzle. tier-one has a pipeline, a price sheet and a store, not a fixture.
- Brown: a grader must not share a root with what it grades. tier-one is not a source of any of the five commands; hyperliquid, rich, power-path and this repo are, and are excluded.
- Patel: pick where a verifiable number exists. tier-one has a unit of flow (tickets) and a test suite.
- Naval: proof of work has to be shown where a buyer would recognise it. A support team is a buyer.

Disclosed limits: tier-one has no client yet, so its traffic is not live traffic; it
has 21 uncommitted paths; and its agent was one of the examples behind the harness
item of the original screen. The runs read tier-one and write only to this repo's
ledger. Nothing in tier-one is changed.

### G3 — Do not push now. Push when acceptance passes.

- Brown: evaluate before release, and do not underestimate what was not evaluated.
- Patel: an agent checks its score before it merges.
- Naval: arrive with proof of work, not with a promise.
- Musk: make the mistakes at small scale before the large one.
- Schulman panel: a result that only looks good on the easy distribution is the one to distrust; wait for the realistic run.

Ruling: the branch stays local until the acceptance checklist is answered with pasted
proof. Push is then part of DONE, as CLAUDE.md requires. The pre-registration's order
is already fixed by commit 85eed06.
