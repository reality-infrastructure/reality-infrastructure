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

**Question 1 is answered by R72's fixed order, never by judgment (A18 R94).** Print the first
factor that holds and the reading that made it hold, then one sentence: (1) the sensor — the
tape of record has a null span or a hole longer than 15 min in the last 24 h, or its last row
is older than 60 s at the read; (2) the hand / the gateway — no pair settled inside the
five-hour gate in the last 7 days; (3) the search — no fork beat both controls on the last
forward day; (4) sim-to-real — a candidate exists and its live residual is outside tolerance;
(5) the group — a candidate holds and its group at the current rung is not full; (6) capital.
The sentence may add words; it may not change the factor.

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
- Frozen (never modified by you; verify by sha256 before and after; paths from `reference-implementation/`):
  `rights_events/fixtures/agent_record/marker/marker.py` acf754f973729eb937ed113eba383970d404ca00d59e3cca378c4f310b1d5f0b,
  `rights_events/fixtures/agent_record/marker/forward.py` 6fd373b87800398fe4f5517c1f84797809571fb1fab9625df24d9931f2681c76,
  `rights_events/fixtures/agent_record/marker/families.json` db01aa33c2c00e15e1369d2677c49bd51433ed62122db5a4c80a20ffb0902974.
- Tools in the cloud session: `pytest` is not preinstalled; `python -m pip install -q pytest` first
  (PyPI is reachable; the HyperLiquid API is not). The phone notification tool (PushNotification)
  reaches the operator even when Gmail does not.

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
Print `python --version` first and quote it in the amendment (A23 finding F2: float sums in the ledger JSON differ in their last digit between interpreters; the routine's version must be on the record).
`git status --porcelain` empty; `git rev-parse HEAD` equals `origin/contract/agent-record`;
the three frozen sha256 above hold; then
`python -m pytest tests/test_agent_record_marker.py tests/test_agent_record_forward_read.py tests/test_agent_record_torn_void.py -q`
must pass (23 + 6 + 11 gates). If you run the whole suite instead, exactly one failure is known and
allowed and must be named: `test_shipped_artifacts_match_live_machine` (its paths are the
laptop's). Anything else failing → STOP: record the failure as the day's finding (step 5), push,
email. Do not fix code.

**2. Fetch the channel.**
`git fetch origin vps/poo-files` and extract it OUTSIDE the repo, running `git archive` FROM THE
REPOSITORY ROOT (from a subdirectory it archives only that subtree and `/tmp/poo` comes out empty;
the first run lost two minutes to this):
`mkdir -p /tmp/poo && (cd "$(git rev-parse --show-toplevel)" && git archive origin/vps/poo-files | tar -x -C /tmp/poo)`.
Verify every file's sha256 against the manifest's list before reading anything.
Read `/tmp/poo/manifest.json`. Health holds when ALL of: `generated_at` within 2 h of now;
`poo_tape` and `poo_marker` both `active`; `tape_newest_mtime` within 10 min of `generated_at`;
D-1 not in `marker/marker_state.json` `void_days`. If health does not hold, the day's finding is
the sensor (S72 / S74), the reading below is still produced but marked VOID for that day, and
the email subject starts with `POO SENSOR`. A26 (R116): the day is ALSO void when its marks file
carries the marker's own `{"type":"void"}` row — the reader prints this (`this day void … by row`);
the state's `void_days` is derived and has lost entries to a full disk, the row decides.

**3. Read.** Run the reader twice (markdown for the amendment, JSON for the pins):
```
python -I rights_events/fixtures/agent_record/ops/poo_forward_read.py --dir /tmp/poo --day <D-1> --days <2026-11-01 … D-1> --n-alive 6
python -I rights_events/fixtures/agent_record/ops/poo_forward_read.py --dir /tmp/poo --day <D-1> --days <2026-11-01 … D-1> --n-alive 6 --json
```
A26 (R115): the reader reads a glued torn line as the whole row behind the fragment (the fragment's
row is lost and never reconstructed), drops a torn LAST line as in-flight, and prints the alignment
counts per file; if it prints `REFUSED S98 <file> line <n>` and exits 1, that refusal IS the day's
reading: quote it, pin the file as served, compute nothing, never repair a line, never drop a day
from `--days` by hand. A26 (R116): days the marker voided are removed from the pass line by the
reader itself and disclosed (`Pass-line days … void by the marker's own mark`); quote that line.
Copy the files the reader pinned into the record so the pins are checkable:
`marks_<D-1>.jsonl`, `signals_<D-1>.jsonl` → `rights_events/fixtures/agent_record/vps/`;
`manifest.json` → `vps/manifest_<D-1>.json`; `marker_state.json` → `vps/marker_state_<D-1>.json`.
Funding: forward rows carry `funding_bps` 0 at write time; applying the hourly prints needs the
HyperLiquid API, which this environment may not reach. If `curl -s -m 10 https://api.hyperliquid.xyz/info`
fails, say in the amendment that the net numbers exclude funding (disclosed, not estimated). Never
estimate funding.

**3b. The arena (A18, from the run of 2026-11-05 onward, reading Day 14 = 11-04).** For every
cohort whose window has started (today: cohort `2026-11-03`, window 2026-11-04 … 11-10), the
channel's `arena/<cohort>/` holds the VPS fills tape's pages. Build the day's capture OFFLINE
from them and grade it through the unmodified runner:
```
python rights_events/fixtures/agent_record/arena/arena_capture_from_tape.py --channel-dir /tmp/poo \
  --cohort-capture rights_events/fixtures/agent_record/arena/<cohort>/capture_ARENA_<cohort>_<cohort>.json \
  --as-of-date <D-1> --now-ms $(date -u +%s)000 [--paper-marks vps/marks_<day>.jsonl ...]
python -m rights_events.agent_arena --capture rights_events/fixtures/agent_record/arena/<cohort>/capture_ARENA_<cohort>_<D-1>.json \
  --out rights_events/fixtures/agent_record/arena/<cohort>/run_ARENA_<cohort>_<D-1>.ri \
  --arena-out rights_events/fixtures/agent_record/arena/<cohort>/arena_<cohort>_<D-1>
```
The run must print `AGENT-RECORD ARENA RUN: OK`; `--verify --run` must pass. If the runner
refuses the capture whole (PREREG A19: S87 the cohort differs from the pinned payload's
derivation, S88 the window or a flag is not the rule's, S89 the payload's bytes are off
their pin), that refusal IS the day's arena finding: quote its reason, grade nothing, push. The amendment
carries the counts (FULL / PARTIAL / NONE / REFUSED), the ranked rows (address, fills, net
with funding), the RECORD row, and the page file shas from the manifest. If `arena/` is
missing from the channel or its newest `pages_index.jsonl` line is older than 2 h, the arena
day is VOID (S85): say so, grade nothing, and go on. Never fetch the API from the cloud.

**3c. The leader screen (A20, from the run of 2026-11-12 onward: the first run after cohort
2's window closes on 11-10).** For every cohort whose window is COMPLETE at D-1, run the
screen over the day's pinned arena (pure, offline):
```
python -m rights_events.arena_screen --capture rights_events/fixtures/agent_record/arena/<cohort>/capture_ARENA_<cohort>_<D-1>.json \
  --arena rights_events/fixtures/agent_record/arena/<cohort>/arena_<cohort>_<D-1>.json \
  --out-prefix rights_events/fixtures/agent_record/arena/<cohort>/screen_<cohort>_<D-1>
```
Commit both files and their shas. The amendment prints the counts (selected / refused / not
screened) and, for every FULL row, its failing letters. A SELECTED address buys nothing
tonight: the paper copy fork needs a later amendment the operator signs (R104). On a day
the window is not complete, do not run the screen (it screens nobody).

**3d. The population ledger (A21, every run).** After the day's marks file is pinned under
`vps/` (step 3), write the ledger as of D-1 (pure, offline; reads the newest pinned reading
of every full forward day, the frozen marker and `ledger/promotions.json`):
```
python -m rights_events.agent_ledger --as-of <D-1> --out-prefix rights_events/fixtures/agent_record/ledger/ledger_<D-1>
```
A26: from the ledger as of 2026-11-08 on, a day whose newest pinned reading carries a void mark is
listed under `Void days (R116…)` and counted for nothing (R116); a laptop re-pin
`marks_<day>_as_read_<date>.jsonl` dated 2026-11-08 or later is read by the ledgers as of that date
and later only (R117). The ledger as of 2026-11-07 renders as A17.10 pinned it.
Commit both files. The amendment prints each fork's status (ALIVE / CANDIDATE / PROMOTED /
RETIRED), rung, days alive, run against k, and any retirement with its reason. A CANDIDATE
is not promoted by the routine: promotion is one rung of size by an amendment the operator
signs (R88, R106). A RETIRED fork's slot is refilled only by a PREREG amendment (R107).

**3e. The copier's grade (A28, every run, after 3b–3d).** The feed is a pure function of the newest
pinned arena and screen files per cohort and SETTLED.md's sha (R118); it never reads the channel or the API:
```
python -m rights_events.arena_feed --as-of <D-1>
```
It writes `arena/feed/feed_<D-1>.json`, `.md` and `feed_latest.json` (byte-equal, S100) and prints per cohort
KEEP / DROP / UNDECIDED / OPEN (R119) with the run across listings (R120). Commit the three files. The amendment
prints the per-cohort counts and any change of status or run since the previous feed. If it prints
`FEED REFUSED` (S99), quote the reason, write nothing, go on. Never set a badge threshold here (the operator's).

**3f. The AI board entry (A29, every run, after 3e).** The record's account and the paper population in the
venue's "AI Traders" columns, from pinned pages and pinned marks only (R123–R127); the board's as-of is TODAY (the
production day D, not D-1), so the dated file never collides:
```
python -m rights_events.arena_ai_board --as-of <D>
```
It writes `arena/ai_board/ai_board_<D>.json`, `.md` and `ai_board_latest.json` (byte-equal, S101). Commit the three
files. The amendment prints the rows (rank within class, trades, win rate, biggest win/loss, fees, total) and any
record row not graded (pages not on the branch). ROI is never computed. If it prints `AI BOARD REFUSED` (S102, a page
off its pin), quote the reason, write nothing, go on.

**3g. The call ledger (A35, every run, after 3f).** Resolve yesterday's calls against the channel's tape, write the
board, then register today's calls before their windows (the tape dir is the channel extract's `tape/`; the
commit sha is the branch head you start from; the time is `date -u +%s`000):
```
python -m rights_events.call_ledger resolve --day <D-1> --tape-dir /tmp/poo/tape
python -m rights_events.call_ledger board --day <D-1>
python -m rights_events.call_ledger register --day <D> --registered-ms $(date -u +%s)000 --commit-sha $(git rev-parse HEAD) --tape-dir /tmp/poo/tape
```
Commit `calls/ledger/calls_<D>.jsonl`, `calls/ledger/resolved_<D-1>.json`, `calls/board/board_<D-1>.json|.md`,
`calls/board/board_latest.json`. The amendment prints the board's two numbers per leg (RESOLVED, LOSS RATE; GAP for a
live leg) and the registration counts. Never edit a leg file; never re-register a call; if `CALL LEDGER REFUSED`
(S104, a tape file off its earlier pin), quote it and write nothing. MARKET calls come only from the newest pinned
capture under `calls/captures/` (R144); the routine does not fetch markets.

**3h. The book of the verdict (A37 + A38, every run, after 3g).** The arena's KEEP set as the leader list of one paper
fork, F6, identical to F4 in every other byte (R145), and F7 = F6 with the leader's own close as the exit (R151). Run it
over the channel extract: the completed cohort's KEEP list (R146; cohort 1 = `2026-10-25` until cohort 2 completes on
11-10 and is graded on 11-11, then `2026-11-03`), the replay of F6 and F7 over the next cohort's pinned pages for the
window so far (R147, in-sample, decides nothing), the relisting table (R149), the book's ledgers for F6 and F7 (R148,
R151), and the copier row (R153–R155, R158: the record's settled pairs after 2026-11-09 14:00Z, the kill test, the
STARLINK line; nothing is shared by the routine, ever):
```
python -m rights_events.arena_book run --as-of <D-1> --cohort <completed cohort> --next-cohort <cohort being graded> \
  --feed rights_events/fixtures/agent_record/arena/feed/feed_<D-1>.json \
  --channel-arena-dir /tmp/poo/arena/<cohort being graded> --tape-dir /tmp/poo/tape \
  --t0 <the next cohort's window start> --t1 <D-1> \
  --endpoint https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/contract/agent-record/reference-implementation/rights_events/fixtures/agent_record/book/book_latest.json
python -m rights_events.arena_book verify --manifest rights_events/fixtures/agent_record/book/MANIFEST_BOOK_<D-1>.json
```
Commit `book/keep_<cohort>.json`, `book/signals_F6_*`, `book/marks_F6_*`, `book/marks_F7_*`, `book/relist_<D-1>.json`,
`book/ledger_F6_<D-1>.json|.md`, `book/ledger_F7_<D-1>.json|.md`, `book/copier_<D-1>.json`, `book/book_<D-1>.json|.md`,
`book/book_latest.json`, `book/MANIFEST_BOOK_<D-1>.json`. The amendment prints the daily table (F6 and F7 beside F4 and
C1 on the same admitted days), the relisting table, the copier row's line (settled pairs, status ALIVE / CANDIDATE /
KILLED, the kill test due or not) and the STARLINK line verbatim. The marker runs with `keep.json` since 02:40Z 11-09
(A37.2) and with F7 since A38's restart; a day with 0 forward rows is written as such. If `BOOK REFUSED`, quote it and
write nothing. The first chain-graded pair under an arena verdict has a 50th-percentile date of **2026-11-11** (R152):
on and after it, a day without one is written `R152: the date is missed; <n> days late` in the same words every time.

**3j. L2 favorite, the compounding account (A40, every run, after 3h).** The hourly legs this laptop session registered
for D-1 (`calls/l2_favorite/ledger/calls_<D-1>.jsonl`, from the captures under `calls/l2_favorite/captures/`) are resolved
against the channel's tape exactly as 3g resolves the main ledger's market calls (SETTLED_CALLS.md 3b; S104 on different
tape bytes), then the account is marked as of D-1 (R164: 11.00 USDC, quarter-Kelly on the Laplace p-hat, reinvested; the
benches CM and C0; the date for 165 USD a day from the measured mean daily log growth after 5 marked days; the kill line
R168). You register nothing (you cannot capture); if no register exists for D-1 the resolve step is skipped and the account
is still marked from the main ledger's favorite calls:
```
python -m rights_events.l2_favorite resolve --day <D-1> --tape-dir /tmp/poo/tape     # only if calls_<D-1>.jsonl exists
python -m rights_events.l2_favorite account --as-of <D-1>
python -m rights_events.l2_favorite check-latest
```
Paste the account table (the four rows and the date line) into the amendment. Commit `calls/l2_favorite/ledger/resolved_<D-1>.json`,
`calls/l2_favorite/account_<D-1>.json|.md` and `account_latest.json` with the day's files.

**4. The live leg (A38 R155 from Day 19, 2026-11-09).** Under the standing go of A34 the entry is the first F6 signal
inside [14:00, 15:00)Z (a KEEP leader's qualifying open), one unit by R156, exit at 30 bps or the gate 5 h after the
open; the hand submits both legs (R157). `ops/copier_watch.py` watches the window and writes `copier/watch_<D>.jsonl`;
read it: an `ORDER_FOR_THE_HAND` row with a venue open on the chain = a pair to grade; an `ORDER_FOR_THE_HAND` row with no
open on the chain = `Day N (D-1): live leg MISS — the signal fired at <time>, no hand committed through the gate (R54,
R157); nothing reached the venue; flat.`; a `window_end` row and no order row = `Day N (D-1): live leg MISS by rule (R155):
no KEEP leader opened inside the window; nothing reached the venue; flat.` Then, as before: look for a capture or
amendment dated D-1 that records a venue open
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

**GitHub access (2026-11-02 02:11Z):** the Claude GitHub App is installed for this one
repository on the reality-infrastructure organization (installation 177678167, on the operator's
words "I'm authorizing you to do so"), so the push is expected to succeed and the day is DONE
only when it does. **Fallback, READ-AND-REPORT mode** (the operator's earlier decision "we'll let
everything run without github for right now", kept for any day the push is refused): commit
locally exactly as above (so the sha exists), then put
the COMPLETE text of your amendment and your SCOREBOARD section, verbatim, in your final message
(the run log on claude.ai keeps it; the laptop replays it onto the branch later), label the day
`READ, UNPUSHED (replay pending)` in the subject line, and go on to steps 8 and 9. The channel
files stay on `vps/poo-files` and the reader is deterministic, so the replay reproduces your
numbers and pins byte for byte. If one day the push succeeds, the day is DONE as written.

**8. The doc.** If the Claude Docs connector is available, add one Standing-log row to the
Proof of Outcome doc (artifact Afx6qWREyHwtiMHznyXqff, the "Week two" tab): date, what shipped,
the commit sha, the honest sign. If it refuses, say so in the email and move on.

**9. Email the operator.** Through the Gmail connector, to the account's own address, subject
`POO Day <N> (<D-1>): <one line>` (or `POO SENSOR …` when health failed). Under 300 words:
the three answers first, then the fork table, the pass-line table, the health line, the live-leg
line, the commit sha and the branch, and anything that failed or was not verified. No attachments.
If Gmail refuses (the first run got "Precondition check failed" on send and on draft), send the
same text, trimmed to fit, as a PushNotification to the operator's phone, and say in the
amendment that the email failed. One channel must carry the day; silence is not an option.

**10. Friday review.** On the run of 2026-11-07 (reading Day 16, 11-06) add to the amendment a
Week-two review: one limiting-factor sentence, the next 50th-percentile date for a candidate,
the count of settled live pairs this week (expected 0 unless the operator ran the laptop leg),
and nothing else.

## What success looks like

The branch gains exactly one commit per day with a pinned reading of yesterday, the record
answers the three questions in the day's numbers, the operator gets one email, and nothing
frozen moved. Seven such days are the week's evidence whether or not a fork passes.
