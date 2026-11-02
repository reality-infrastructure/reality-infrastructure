# POO_DAILY — the Proof of Outcome day, executed without a hand (A17, 2026-11-02)

You are the executor of one Proof of Outcome day. The operator (Irvin Pierce) is away from the
machine for the week of 2026-11-02; they read your output on a phone. You run in a cloud session
with a fresh clone of this repository. Nothing on the operator's laptop or VPS is reachable from
here except what the VPS publishes to GitHub. There is no venue client here and you must never
create one (S73).

Read this file to the end before acting. Then do the steps in order. Every step says what to do
when it fails. A failed step is data; it is recorded, never dressed.

## The operator's seven rules (pasted 2026-11-01, binding)

1. Attack the limiting factor, nothing else. Every review names the one binding stage and works only there.
2. Reality is the only grader. Marks come from the chain, fills pay their own impact, and no rule is ever tuned on the book that judges it.
3. Bits per day is the currency. 40 closes is 40 bits. Score all of them.
4. Parallel agents, fork from one context, spin down the losers. One feed, a population of paper books, each a one-variable fork of the contract, all marked against the same tape.
5. Promote only on a held-out bench, else discard. A variant becomes a candidate only after beating the control on consecutive forward days.
6. Climb one rung at a time. One changed variable per contract.
7. The human keeps the objective; the machine keeps the discipline. The paragraph and the gates are the operator's; the machine never sizes up, never averages down, never comes back bigger after a red day.

## The operator's three questions (answer them every day, in the amendment and in the email)

1. What is the one thing limiting you right now?
2. What does reality actually reward, as opposed to what your dashboard rewards?
3. What is the smallest sequence of bets that lets reality grade you early and cheaply?

Answer from the day's numbers and the record, in plain sentences, no more than three sentences each.

## Where things are

- Branch of record: `contract/agent-record`. The clone may land on `main`; run
  `git fetch origin contract/agent-record vps/poo-files && git checkout contract/agent-record`.
- Working directory for everything below: `reference-implementation/`.
- The record: `contracts/agent_record/PREREG.md` (amendments, rules R…, STOPs S…) and
  `contracts/agent_record/SCOREBOARD.md` (one short section per amendment plus the income row).
- The reader: `rights_events/fixtures/agent_record/ops/poo_forward_read.py` (stdlib, offline).
- The channel: branch `vps/poo-files`, written hourly at :07 UTC by the VPS cron
  (`ops/poo_publish_vps.sh` is the byte-identical copy of the script that writes it). It holds
  `manifest.json`, `tape/tape_MIDS_<day>.jsonl`, `marker/marks_<day>.jsonl`,
  `marker/signals_<day>.jsonl`, `marker/marker_state.json`, `marker/poo-marker.log.tail`.
- Pinned copies live under `rights_events/fixtures/agent_record/vps/`.
- Frozen (never modified by you; verify by sha256 before and after):
  `marker/marker.py` acf754f973729eb937ed113eba383970d404ca00d59e3cca378c4f310b1d5f0b,
  `marker/forward.py` 6fd373b87800398fe4f5517c1f84797809571fb1fab9625df24d9931f2681c76,
  `marker/families.json` db01aa33c2c00e15e1369d2677c49bd51433ed62122db5a4c80a20ffb0902974.

## The calendar

- Day 1 = 2026-10-22. Day N = 2026-10-21 + N. Day 11 = 2026-11-01, Day 12 = 11-02, … Day 18 = 11-08.
- Forward marking: 2026-10-31 PARTIAL (health only, never in the pass line); 2026-11-01 is the
  first FULL forward day; N alive = 6 forks (F4 on BTC, ETH, HYPE, ZEC, SOL, NEAR) → k = 5 →
  the earliest day any fork can be a CANDIDATE is 2026-11-05 (R85).
- The day you read is D-1 = yesterday UTC. The pass-line days are every full day from 2026-11-01
  through D-1, in order.
- The week's one changed variable is this automated day itself (A17). The forks do not change
  (R84 binds: F1–F3 deleted, F4 and C1 only). You never add, remove, reseed or retune a fork.

## Steps, in order

**0. Clock.** `date -u`. Compute D-1 and the day number. Nothing else reads the clock.

**1. Preflight.**
`git status --porcelain` empty; `git rev-parse HEAD` equals `origin/contract/agent-record`;
the three frozen sha256 above hold; then
`python -m pytest tests/test_agent_record_marker.py tests/test_agent_record_forward_read.py -q`
must pass (23 + 6 gates). If you run the whole suite instead, exactly one failure is known and
allowed and must be named: `test_shipped_artifacts_match_live_machine` (its paths are the
laptop's). Anything else failing → STOP: record the failure as the day's finding (step 5), push,
email. Do not fix code.

**2. Fetch the channel.**
`git fetch origin vps/poo-files` and extract it OUTSIDE the repo:
`mkdir -p /tmp/poo && git archive origin/vps/poo-files | tar -x -C /tmp/poo`.
Read `/tmp/poo/manifest.json`. Health holds when ALL of: `generated_at` within 2 h of now;
`poo_tape` and `poo_marker` both `active`; `tape_newest_mtime` within 10 min of `generated_at`;
D-1 not in `marker/marker_state.json` `void_days`. If health does not hold, the day's finding is
the sensor (S72 / S74), the reading below is still produced but marked VOID for that day, and
the email subject starts with `POO SENSOR`.

**3. Read.** Run the reader twice (markdown for the amendment, JSON for the pins):
```
python -I rights_events/fixtures/agent_record/ops/poo_forward_read.py --dir /tmp/poo --day <D-1> --days <2026-11-01 … D-1> --n-alive 6
python -I rights_events/fixtures/agent_record/ops/poo_forward_read.py --dir /tmp/poo --day <D-1> --days <2026-11-01 … D-1> --n-alive 6 --json
```
Copy the files the reader pinned into the record so the pins are checkable:
`marks_<D-1>.jsonl`, `signals_<D-1>.jsonl` → `rights_events/fixtures/agent_record/vps/`;
`manifest.json` → `vps/manifest_<D-1>.json`; `marker_state.json` → `vps/marker_state_<D-1>.json`.
Funding: forward rows carry `funding_bps` 0 at write time; applying the hourly prints needs the
HyperLiquid API, which this environment may not reach. If `curl -s -m 10 https://api.hyperliquid.xyz/info`
fails, say in the amendment that the net numbers exclude funding (disclosed, not estimated). Never
estimate funding.

**4. The live leg.** Look for a capture or amendment dated D-1 that records a venue open
(`rights_events/fixtures/agent_record/capture_LIVE_<D-1>_*.json`, or a `### A1x` heading dated D-1
with an open). None → the line is `Day N (D-1): live leg MISS — no hand committed through the gate
(R54); nothing reached the venue; flat.` A MISS is recorded in the same words every time. You
cannot and must not open or close anything.

**5. Write the amendment.** Append to `contracts/agent_record/PREREG.md` a section
`### A17.<j> — <D> <HH:MM>Z, flat — <one line>` where j = 1 + the count of existing `### A17.`
headings. In the record's voice (dated, first person plural, numbers in tables, nothing averaged
across days), it contains, in order: the clock and the day number; preflight (the hashes, the
gate count); the channel's health (the manifest fields, the VPS branch commit sha read); the
reader's markdown verbatim; the pins table; the live-leg line; the three answers; the k countdown
(days of forward record so far, days to 2026-11-05 or, after it, which forks have a run and how
long); the R81 income row: `0 USD a day against 165` unless a settled live pair on the branch
says otherwise; STOPs hit, if any; what was not verified. Then append to
`contracts/agent_record/SCOREBOARD.md` a section `### A17.<j> — <one line>` with a 3–6 row
evidence table and the income row, in the file's existing style.

**6. Never.** Modify any file under `marker/`, any existing `capture_`, `run_`, `MANIFEST_`,
`watch_`, `forks_` or `hl_` file, any earlier amendment, any rule, seed or family. Never average or
smooth across days, never pick a favourable window, never tune anything on the forward book.
Never size, never touch a venue, never write to any branch other than `contract/agent-record`,
never force-push, never rebase, never delete history. Never fix a failing gate by editing a test.

**7. Commit and push.** One commit:
`AGENT-RECORD-A17.<j>: <the one line>` with a body of the key numbers, ending with
`Co-Authored-By: Claude <noreply@anthropic.com>`. Push to `origin contract/agent-record`. If the
push is rejected because the branch moved, `git pull --rebase` is forbidden; instead fetch, start
again from the new head (re-run steps 1–5 on top of it) and push. If the push fails for any other
reason the day is NOT done: email the exact error.

**8. The doc.** If the Claude Docs connector is available, add one Standing-log row to the
Proof of Outcome doc (artifact Afx6qWREyHwtiMHznyXqff, the "Week two" tab): date, what shipped,
the commit sha, the honest sign. If it refuses, say so in the email and move on.

**9. Email the operator.** Through the Gmail connector, to the account's own address, subject
`POO Day <N> (<D-1>): <one line>` (or `POO SENSOR …` when health failed). Under 300 words:
the three answers first, then the fork table, the pass-line table, the health line, the live-leg
line, the commit sha and the branch, and anything that failed or was not verified. No attachments.

**10. Friday review.** On the run of 2026-11-07 (reading Day 16, 11-06) add to the amendment a
Week-two review: one limiting-factor sentence, the next 50th-percentile date for a candidate,
the count of settled live pairs this week (expected 0 unless the operator ran the laptop leg),
and nothing else.

## What success looks like

The branch gains exactly one commit per day with a pinned reading of yesterday, the record
answers the three questions in the day's numbers, the operator gets one email, and nothing
frozen moved. Seven such days are the week's evidence whether or not a fork passes.
