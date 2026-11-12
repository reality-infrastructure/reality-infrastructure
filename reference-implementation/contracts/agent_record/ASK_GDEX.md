# The ask to the venue

Status: DRAFT, written by the executor on 2026-11-12 under PREREG A44 (R199). It is the
operator's to read, change, send or throw away. No session sends it. Every figure below is on
this branch in a pinned file named beside it; nothing here is a claim about any trader's skill
or about anyone's profit.

---

**To:** GDEX
**From:** the operator of the record at `0x9f976123e7c48952be487664b8130aad144b7f23`
**About:** your empty "AI Traders" tab, and a grader that can fill it

## What exists today

1. **Your "AI Traders" tab has columns and no rows.** On 2026-11-08 the Top Perp Traders
   board listed 48 237 human traders. The AI tab beside it (RANK, MODEL, TOTAL P&L, ROI %,
   WIN RATE, BIGGEST WIN, BIGGEST LOSS, TRADES, FEES) listed none.

2. **A grader has read your board's addresses since 2026-11-03, daily since 2026-11-05.** It
   reads only what the chain settled after an address was listed: HyperLiquid fills with a
   transaction hash and the funding the L1 charged, every page pinned byte for byte. The rule
   is one page long and frozen (`SETTLED.md`, sha256 `c6b590de…`). Two cohorts of your board
   are graded over a complete window:

   | listed | window | board addresses | fully served by the public API | net > 0 after listing (KEEP) | net ≤ 0 or nothing settled (DROP) | not decidable |
   |---|---|---|---|---|---|---|
   | 2026-10-25 | 10-26 … 11-02 | 80 | 8 | 7 | 51 | 23 |
   | 2026-11-03 | 11-04 … 11-10 | 69 | 28 | 25 | 44 | 1 |

   (`arena/feed/feed_latest.json`. The three status counts are over the board's addresses
   and my own account, graded beside them: 81 and 70 rows. Mine is one of the 7 in the first
   window and one of the 44 in the second.)

3. **What a follower could have received is a different number from what the board shows.**
   In the first cohort the eight fully served rows realized 550 743 USD in the window and held
   **no position that was both opened and closed inside it**: the money came from positions
   carried in or still open. In the second cohort, read on 2026-11-09, 99.82 % of 73.2 million
   USD realized by 28 rows sat in such positions. Someone who starts copying on the day of the
   listing does not hold those positions. This is not a criticism of those traders. It is a
   statement about which number a copier needs. (`arena/source/`, PREREG A39.1.)

4. **There is now a door.** Any address can enrol itself: it signs six fixed lines with its
   own key, the check is arithmetic anyone can run offline, and from the next capture it is
   graded by the same rule in your tab's own columns, with one addition: its result on trips
   it opened and closed inside the window. Fills between two graded addresses are disclosed
   (373 of 216 912 trade ids in the first cohort were such meetings, in the ordinary course).
   Today the door holds zero entrants. (`arena/door/door_latest.json`, PREREG A44.)

## What I am asking

1. **Show the door's rows in the "AI Traders" tab, or link the tab to the endpoint.** The
   file is already laid out in your columns. You keep the tab; the chain keeps the numbers.

2. **Let an agent launched from your Agent Risk Terminal enrol with one click.** A managed
   wallet's owner cannot sign the six lines today, because the venue's session signs for the
   wallet. One signature from the terminal over the statement in `door_latest.json` is all the
   door needs.

3. **One question.** Do the referral tiers on your referrals page (30 % and 10 % of fees)
   apply to the volume of agents that enrol through my code? I am not assuming the answer.

## What I am not asking and not claiming

No badge, no payment, no exclusivity, no access to anything private. No claim that any graded
address is good or bad at trading. No return or ranking that the frozen rule does not define.
My own account's graded result is small and is on the same page as everyone else's: four
fills, net 0.073533 USD in the first window, nothing settled in the second.

## Where to look

- The door: `…/rights_events/fixtures/agent_record/arena/door/door_latest.json`
- The copier's grade of your board: `…/arena/feed/feed_latest.json`
- The record in your AI columns: `…/arena/ai_board/ai_board_latest.json`
- The rule: `reference-implementation/contracts/agent_record/SETTLED.md`

(`…` = `https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/contract/agent-record/reference-implementation`)

A fifteen-minute call is enough to decide whether this is useful to you.
