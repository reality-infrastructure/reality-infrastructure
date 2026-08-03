# CONTRACT-ARTIFACT INVENTORY — every contract on disk, all repos

```
contract: "Extract the operator's contract-writing method" (2026-08-03, this session)
phase:    1 of 4
scan:     13 git repos under C:\Users\newce\ (all repos on disk); 4 hold contract
          artifacts (reality-infrastructure, the-registry-signal, capability-factory,
          royalty-audit) + 2 hold copies/snapshots (signal-dashboard,
          the-registry-signal-BACKUP-2026-04-09). The other 7 (nimbus, nimbus-ai,
          my_nimbus_ai_project, solana-trading-bot, langgraph, Performance-RNN-PyTorch,
          registry-static) contain none.
method:   read-only; statuses are as stated in the artifacts themselves
```

## Totals

- **Execute-class contracts (a task given to a session to perform): 43** —
  19 the-registry-signal + 21 reality-infrastructure + 1 royalty-audit +
  2 library scaffolds (signal-dashboard originals).
- **Decision/ledger contracts (CF entries): 26** (CF-001–CF-025 + CF-025 CLOSEOUT).
- **Admission proposals: 2** (capability-factory/_admission/).
- **Governing instruments (CLAUDE.md variants, done-rule, baselines, pre-registrations,
  templates, canon): ~20** (listed per repo below).
- **Date range covered: 2026-03-31 → 2026-08-03** (Scoring Engine v1 → the
  artifact-path-determinism queue entry).
- Completed: 33 execute contracts. Stopped: 2 plan-gate halts (both resumed after
  ratification). Abandoned/superseded: 5. Parked pending trigger: 2.
  Executed-but-unarchived: 2 (M-RI-00, M-RI-09). Completed-with-pre-registered-FAIL: 1
  (CF-022 — the failure honored, not tuned away).

## reality-infrastructure (M-RI / C / RI-FORGE) — 21 execute contracts

Paths relative to `reference-implementation/` except where noted.

| ID | Path | Date | Subject | Status |
|----|------|------|---------|--------|
| M-RI-00 | none — ROADMAP.md:10 "(done in chat)" | 2026-07-19 | Repo + structure + constitution docs | completed, NOT ARCHIVED |
| M-RI-01 | contracts/completed/M-RI-01-serialization.md | 2026-07-19 | Canonical deterministic serialization | completed |
| M-RI-02 | contracts/completed/M-RI-02-merkle-log.md | 2026-07-19 | Merkle evidence log + proofs | completed |
| M-RI-03 | contracts/completed/M-RI-03-clock-identity.md | 2026-07-19 | Lamport clock + identity anchor | completed |
| M-RI-04 | contracts/completed/M-RI-04-provenance.md | 2026-07-19 | PROV-DM graph + how-provenance | completed |
| M-RI-05 | contracts/completed/M-RI-05-rules.md | 2026-07-19 | Versioned declarative rule store | completed |
| M-RI-06 | contracts/completed/M-RI-06-reconcile.md | 2026-07-20 | Denœux cautious combination | completed |
| M-RI-07 | contracts/completed/M-RI-07-project.md | 2026-07-21 | Projection engine (fold + justification) | completed |
| M-RI-08 | contracts/completed/M-RI-08-replay.md | 2026-07-21 | Replay + counterfactual | completed |
| M-RI-09 | none — ROADMAP.md:19 "(005d365; contract not archived)" | 2026-07-19 | Conformance suite + ablation | completed, NOT ARCHIVED |
| M-RI-10 | contracts/completed/M-RI-10-title-dossier.md | 2026-07-22 | Fictional title-dossier walk-through | completed |
| M-RI-11 | contracts/completed/M-RI-11-real-parcel-dossier.md | 2026-07-27 | Real Dolton parcel dossier (first real data) | completed |
| M-RI-12 | contracts/completed/M-RI-12-case-study.md | 2026-07-28 | Anonymized prospect-facing case study | completed |
| M-RI-13 | contracts/completed/M-RI-13-ep-typing.md | 2026-07-28 | EP typing wired into evidence layer | completed (PASS, un-tuned) |
| C1 | contracts/completed/C1-event-layer.md | 2026-08-01 | Rights-event layer, Song X end-to-end | completed |
| C2 | contracts/completed/C2-second-domain.md | 2026-08-01 | Second domain (parcels), zero-change wall | completed (F3: one criterion NOT MET — REAL DATA UNAVAILABLE) |
| C3 | contracts/completed/C3-four-views.md | 2026-08-01 | Public static site, four views | completed |
| C4 | contracts/completed/C4-methodology-note.md | 2026-08-01 | Methodology note + release | completed |
| M-RI-14 | contracts/completed/M-RI-14-crm-reality-audit.md | 2026-08-02 | 740-parcel CRM reality audit | completed (admitted via CF-025) |
| M-RI-15 | contracts/completed/M-RI-15-attest-rerun-select.md | 2026-08-02 | Attest, re-run, select (day-class) | completed (DONE-only archive) |
| M-RI-16 | contracts/completed/M-RI-16-f1-remediation.md | 2026-08-03 | F1 remediation, re-baseline (day-class) | completed (DONE-only archive) |
| RI-FORGE | CONTRACT-RI-FORGE.md (repo root) | 2026-08-03 | Reusable build library (forge/) | completed (4/4 gates, forge/SCOREBOARD.md) |
| (queued) | contracts/queue/artifact-path-determinism.md | 2026-08-03 | Path-casing determinism defect | QUEUED |

Related instruments: audit/PREREGISTRATION.md (M-RI-14, FROZEN + §9 amendments A1-A3) ·
pilot/ep_typing_preregistration.md + pilot/mass_assignments.md (M-RI-11/13) · CLAUDE.md ·
ROADMAP.md (the milestone ledger) · forge/templates/*.template.md + forge/fixtures/
demo_fixture/ (template instances, fixture only — not an executed contract) · the
method-extraction contract executing now (2026-08-03, transcript-only, no file on disk).

## the-registry-signal (letter contracts) — 19 execute contracts

| ID | Path | Date | Subject | Status |
|----|------|------|---------|--------|
| Scoring Engine v1 | contracts/completed/2026-03-31-scoring-engine-v1.md | 2026-03-31 | Field audit + composite scoring | completed |
| Daily Brief | contracts/completed/2026-04-01-daily-brief.md | 2026-04-01 | Top-20 morning brief | completed |
| C | contracts/completed/2026-04-07-contract-c-backtest-and-avoid-zips.md | 2026-04-07 | Backtest + avoid-zips | completed |
| E | contracts/completed/2026-04-08-contract-e-dashboard-supabase.md | 2026-04-08 | Dashboard on Supabase | completed |
| F | contracts/completed/2026-04-10-contract-f-cron-automation.md | 2026-04-10 | Cron automation | completed |
| H | contracts/completed/2026-04-14-contract-h-pre-migration-refactor.md | 2026-04-14 | Pre-migration refactor | completed |
| I | contracts/completed/2026-04-15-contract-i-daily-movers-v0.md | 2026-04-15 | Daily movers v0 | completed |
| J | contracts/completed/2026-04-21-contract-j-dashboard-whats-new.md | 2026-04-21 | Dashboard what's-new | completed |
| K | contracts/completed/2026-04-30-contract-k-dashboard-truthfulness.md | 2026-04-30 | Dashboard truthfulness | completed |
| L | contracts/completed/2026-05-01-contract-l-behavioral-capture.md | 2026-05-01 | Behavioral capture | completed |
| M | contracts/completed/2026-05-05-contract-m-csv-export.md | 2026-05-05 | Weekly CSV export | completed |
| O | contracts/CURRENT.md | 2026-05-26 | Five design fixes + real data | completed (never archived out of the slot) |
| C (draft) | contracts/queue/contract-c-backtest.md | pre-04-07 | Backtest draft | SUPERSEDED (rewritten at execution) |
| D (draft) | contracts/queue/contract-d-cron-automation.md | pre-04-10 | Cron draft | SUPERSEDED (became F) |
| E (draft) | contracts/queue/contract-e-dashboard.md | pre-04-08 | Dashboard draft | SUPERSEDED (rewritten at execution) |
| G | contracts/queue/contract-g-repo-cleanup.md | 2026-04-10 | Split repo into signal-os + dashboard | ABANDONED (never executed as specified) |
| FOIA | docs/contracts/pending/foia-integration-dolton.md | 2026-06-08 | Wire FOIA vacancy/violations | PARKED (fires on FOIA receipt) |
| signal-design | contracts/signal-design.md | 2026-04-07 | UI restyle (library) | library/reusable |
| signal-scaffold | contracts/signal-scaffold.md | 2026-04-07 | Next.js scaffold (library) | library/reusable |

Letter gaps: A/B were never lettered (the two date-named contracts); D's letter was
consumed by a superseded draft (executed as F); **N has no artifact anywhere** — unexplained
gap. Governing instruments: CLAUDE.md (rewritten 2026-06-03, INVARIANTS block) ·
CLAUDE.dain-legacy.md (superseded) · rules/done-rule.md (5-gate DoD) ·
docs/loop/back-test-pre-registration.md (LOCKED, 2026-07-15, + Amendment 1) ·
docs/loop/baseline.md (rolling ledger D-001–D-098, through 2026-07-23).
signal-dashboard carries byte-identical copies of the two library contracts;
the BACKUP repo is a 2026-04-09 snapshot of the same method, not deep-read.

## capability-factory (CF) — 26 ledger entries + 2 admission proposals

The admission layer. Execute contracts live elsewhere; this repo decides what may run.

- **CF-001 → CF-025** in decision_log.md (append-only; "Never rewrite history. To reverse
  a decision, append a new entry referencing the old."), 2026-07-24 → 2026-08-02, no
  numbering gaps. Types: SHAPE / RULE / DEFER / OVERRIDE / BUILD; status OPEN/CLOSED.
  Notable: CF-004 OPEN by design (deferred) · CF-022 **FAIL per pre-registered condition,
  closed honestly** · CF-024 an explicit OVERRIDE of a prior rule · CF-025 BUILD entry that
  opened M-RI-14, with appended CLOSEOUT the same day.
- **_admission/ame8-ruling-proposal.md** (2026-07-26): PROPOSAL → ratified at 0c74f41
  (CF-018). **_admission/crm-reality-audit-proposal.md** (2026-08-02): RATIFIED at plan
  gate → CF-025 → M-RI-14.
- Governing: README.md (the Admission Rule) · baseline.md ("Updated at every closeout.
  Never guessed.") · daily_log.md · purpose.md · EXTRACTION-PROMPT.md (defines the CF
  entry format) · canon/ (7 evidence-gated assets, n=1/n=2/n=3+ maturity vocabulary) ·
  _position/ (2: proposes-does-not-authorize menu; the unsent A4 draft under GATE) ·
  _extraction/ (1).

## royalty-audit (M-RA) — 1 execute contract

| ID | Path | Date | Subject | Status |
|----|------|------|---------|--------|
| M-RA-01 | contracts/completed/M-RA-01-two-source-detection-g-herbo-validation.md | 2026-07-31 → 2026-08-02 | Scaffold + two-source registration-gap detection + G Herbo validation | completed (premise drift reported per disk-beats-memory; residuals carried forward) |

Instruments: CLAUDE.md (IF/ELSE-NEVER form; halt-don't-mock; disk-beats-memory) ·
CONTRACT_TEMPLATE.md (the canonical TASK-form skeleton, ported from RI) ·
PRE-REGISTRATION.md (G Herbo validation; real-result-wins rule; falsifier split) ·
docs/mlc-access.md (sanctioned-access rulings R1-R3) · snapshots/MANIFEST.md.
Mid-contract HALT honored at bab336d (build halts for operator transcription) — a
designed stop, not a failure. contracts/queue/ empty.

## Cross-repo mechanism (how the pieces connect)

the-registry-signal (Mar-May) is the method's origin: CURRENT.md slot, completed/
archive, CHECKPOINT: STOP, done-rule. capability-factory (from Jul 24) added the
admission layer: proposal → operator ratification at plan gate → CF BUILD entry →
execute contract in the target repo → closeout appended to the CF entry.
reality-infrastructure (from Jul 19) is where the execute method matured (TASK form,
pre-registration files, amendment discipline, DONE-only day-class archives).
royalty-audit (Jul 31) is the first port of the mature method to a fresh repo — via
CONTRACT_TEMPLATE.md, proving the form travels.
