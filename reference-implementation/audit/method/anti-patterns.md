# ANTI-PATTERNS — forms the operator has visibly moved away from

```
contract: "Extract the operator's contract-writing method" (2026-08-03)
phase:    4 (companion to contract-spec.md)
rule:     an anti-pattern is listed only with evidence of movement: the form appears
          in early/failed/abandoned artifacts and is absent from (or explicitly
          overruled in) completed recent ones. Prefixes as in contract-spec.md.
```

## 1. Forms visibly abandoned

**Narrative contracts without fences.** The earliest form (`## What / ## Why /
## Context Files / ## Test`, rs/…2026-03-31-scoring-engine-v1.md) has no OUT
section, no STOP conditions, no checkbox acceptance. It disappears after mid-April;
every contract from rs/Contract H (2026-04-14) onward carries per-phase gates
and an Out of Scope fence, and every RI-era contract carries all four invariant
sections. The operator has not written a fence-less contract since 2026-04-07.

**Queued speculative drafts.** rs/contracts/queue/ contracts C, D, E were all
rewritten from scratch at execution time; none ran as drafted. The lesson is
codified as doctrine: "ONE contract in flight. Do NOT modify files outside contract
scope. Do NOT start a new contract in this session. No queue." (rs/CLAUDE.md:37-38,
rewritten 2026-06-03). Where a queue reappears (ri/contracts/queue/, 2026-08-03,
one entry) it holds a complete, executable contract awaiting numbering — not a
sketch awaiting a rewrite.

**Completion without archival.** M-RI-00 "(done in chat)" and M-RI-09 "(005d365;
contract not archived)" (ri/ROADMAP.md:10, :19) are the only executed-but-unarchived
contracts in the corpus, both from the first RI days. The COMPLETION rule
(ri/CLAUDE.md: "CURRENT.md moved to /contracts/completed/ with the DONE report
appended") ended the practice; nothing since M-RI-10 is missing its archive. The
2026-08-03 near-miss shows why it matters: an operator instruction relied on the
M-RI-16 DONE report's "left untracked" line after the fact had changed
(forge/INVENTORY.md §9 A3) — prose reports go stale; the archive-plus-git-state is
what a later session can trust.

**Deploy-proof as the terminal gate.** The registry 5-gate done-rule (VPS deploy,
curl, hard-refresh screenshot — rs/rules/done-rule.md) is the DoD of the era that
ended 2026-05-26. Every contract since M-RI-01 terminates instead in
paste-the-suite-output, byte-identity, and pasted `git diff` walls. The screenshot
gate never appears again. (Context-dependent: the registry repo still declares it;
the operator simply stopped writing contracts of that shape.)

**Unpinned premises.** Early contracts state context as prose; from M-RI-11 on,
premises are pinned — sha256 of inputs, dataset ids, commit hashes — and a pin
mismatch is a STOP condition (S1, ri/audit/PREREGISTRATION.md:136). M-RA-01 shows
the mature behavior when a premise drifts anyway: "PREMISE DRIFT REPORTED per
disk-beats-memory; contract pinned RI at 72e1cc8, but RI HEAD is now 9e73e56 …"
(ra/ M-RA-01 DONE report) — reported, classified benign, not silently absorbed.

**Predicting result counts.** Nothing in the corpus before M-RI-14 forbids it, but
from M-RI-14 on the rule is explicit and doubly stated: "Verdict COUNTS are UNKNOWN
and declared so" (ri/audit/PREREGISTRATION.md:60-62); "verdict counts as measured —
never predicted" (cf/decision_log.md:688-690). Where prediction IS wanted, it is
itself pre-registered and scored: M-RI-15 "missed by 2", M-RI-16 "missed by 0"
(ri/…M-RI-16-f1-remediation.md §6). Unregistered prediction does not appear in any
completed contract after 2026-08-01.

## 2. Present in failed/abandoned artifacts, absent from completed ones

The corpus has exactly one abandoned contract (rs/contracts/queue/contract-g-repo-
cleanup.md) and three superseded drafts. What G has that no completed contract has:

- **Meta-work as the objective.** G is the only contract whose entire deliverable is
  repository restructuring ("Split repo into signal-os + signal-dashboard") — no
  data, no user-visible output, no test that could fail. Every completed contract
  ships something a test or a reader can check.
- **Human-only territory inside the execution path.** G's Out of Scope reserves
  ".env files (human-only territory) … production secrets … the Vultr VPS without
  checkpoint approval" — the work could not complete without leaving the agent's
  authority. Completed contracts either keep operator actions fully outside scope
  (M-RI-14: "No email sent by this session"; the A4 GATE) or stop and wait for a
  ruling (M-RA-01's transcription halt); none interleaves agent work with
  operator-only steps inside one execution.
- **No acceptance criteria.** The G draft (like the other queue drafts) has phases
  but no checkbox acceptance. Everything completed since mid-April has it.

Causality is not claimable from n=1 (G may simply have been overtaken by events);
what is claimable: the operator never again wrote a pure-restructuring contract,
and the two properties above never appear in a completed one.

## 3. Doctrine that exists BECAUSE a failure was observed (negative space)

These rules read as anti-patterns the operator caught in the act and legislated
against; each cites its own trigger:

- "generation is how a knowledge base fills with confident fiction (see the RP-001
  audit, CF-012)" — cf/canon/extraction-protocol.md:28-30. RP-001's status had to be
  corrected after an epistemic audit (CF-012); the STOP-on-synthesis rule followed.
- "THE REAL-TIME TRIPWIRE: the moment I find myself adjusting ANY input … AFTER
  having seen the back-test result … STOP. That adjustment IS the failure happening
  in real time." — rs/docs/loop/back-test-pre-registration.md:63-66. Written in the
  first person: a self-observed temptation, pre-committed against.
- "Scoring a null as zero would dump 831 parcels to the bottom … a silent
  corruption. FORBIDDEN." — rs/docs/loop/back-test-pre-registration.md:97-99. The
  831 is a measured, named near-miss.
- The §9 amendment discipline (dated, append-only, re-pin in the same commit) exists
  because a real rule gap (the `/`-normalization miss, F1) was found AFTER a
  baseline shipped; the fix arrived versioned with every transition cause-traced
  (ri/audit/PREREGISTRATION.md:170-191) rather than as a quiet edit.
- The single-writer rule (one writing session per repo per window, operator ruling
  2026-08-03) followed a mid-pass commit by a parallel session (59b8f39, noted in
  72ab7d2's message: "committed mid-pass … with bytes unchanged").

## 4. Marked unestablished (fewer than three instances — not yet the pattern)

- DONE-only archives with the contract text left at a commit pointer (M-RI-15/16) —
  2 instances; contrast with 17 full-text archives.
- Markdown-heading contract form (Context/Non-Goals/…/Kill Criteria) — 2 instances
  (RI-FORGE, this method-extraction contract).
- OPERATING MODE risk-framing section — 1 instance (M-RI-13).
- In-contract NUMBERING correction block — 1 instance (M-RI-13).
- "Found while doing something else" provenance block on a queued contract — 1
  instance (ri/contracts/queue/artifact-path-determinism.md, 2026-08-03).
