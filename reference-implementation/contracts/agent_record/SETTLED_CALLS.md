# What counts as a resolved call, and what counts as a loss

Status: written by the executor on 2026-11-08 under PREREG A35 and RATIFIED the same day on the
operator's word ("Use the three transcripts verbatim to execute all of the following right now …
SETTLED_CALLS.md … ratified"). From the ratification line on, its sha256 is a frozen-file gate; no
session edits it; a change is a new document with a new name and a new ratification. It governs
the call ledger (R137–R144). SETTLED.md (HyperLiquid fills), SETTLED_SOLANA.md and
SETTLED_CENSUS.md are unchanged by it.

1. A call is one pre-registered statement about one external print that the leg making the call
   does not control, logged with its leg, its subject, its window, its side and the sha256 of the
   commit that registered it, BEFORE the window opens. A call registered after its window opened
   is not a call; it is discarded and counted as late.

2. A call resolves to exactly one bit against its print: RIGHT or WRONG. Nothing else about the
   call is scored: not its size, not its reasoning, not its write-up, not how close it was.
   A print that cannot be read (no tape row inside the tolerance, a market that never settled)
   leaves the call UNRESOLVED: not a loss, not a win, counted and disclosed.

3. The call types on the board, and their prints:
   a. BAR — one declared coin, one UTC hour [HH:00:00, HH+1:00:00). The side is UP or DOWN.
      The print is the tape of record (the VPS mids tape, R71/R76): open = the first tape row
      at or after HH:00:00Z within 600 s, close = the first row at or after HH+1:00:00Z within
      600 s. UP is RIGHT iff close > open; DOWN is RIGHT iff close < open; close equal to open
      makes either side WRONG (a call must call a move). Where the venue's own 1-hour candle is
      pinned beside the tape the candle is disclosed as the cross-check; the tape binds.
   b. MARKET — one HyperLiquid HIP-4 "binaryPrice" outcome market on a declared coin, with its
      `threshold` and `time` as the venue's outcome metadata states them, expiring inside the
      call's day. The side is YES or NO. The print is the tape of record's mid for that coin
      at the first row at or after `time` within 60 s: YES is RIGHT iff mid > threshold, NO is
      RIGHT iff mid ≤ threshold. The deployer's own settlement (the 1-minute perp candle, per
      the market's `resolutionSource`) is the print of record where it is pinned from the
      venue; until it is, the tape's mid is the print and `print_source` says so.
   c. LIVE — one round trip of a graded wallet under SETTLED.md (the record or a COPIER row):
      RIGHT iff its P&L (Σ closedPnl − Σ fee) is above zero. Its print is the chain.
   Any other call type is not on the board until a dated amendment names its print.

4. One bit per call, and duplicates count once: two calls by the same leg with the same type,
   subject, window and side are one call. A call whose print lands after 23:59:59.999Z of the
   day it was registered for is not on the daily board; it goes to the slow ledger and counts
   toward nothing.

5. The two numbers per leg per day are RESOLVED (the count of calls that resolved) and LOSS
   RATE (WRONG over RESOLVED, four decimals). A LIVE leg carries a third, GAP = its loss rate
   minus the loss rate of its paper twin on the same day. UNRESOLVED, LATE, DUPLICATE and SLOW
   counts are printed beside them and never enter the rate.

6. The loss is defined here and nowhere else. No leg, bot or student redefines what counts as
   WRONG; a leg that disputes a print files the dispute beside the bit, and the bit stands.

7. The machine never edits this document. The operator may.

ratified 2026-11-08 (the operator, in session at 06:4xZ: "Use the three transcripts verbatim to execute all of the following right now: … SETTLED_CALLS.md, your document, drafted tonight with the loss defined per call type and the print named, ratified …")
