# What counts as a settled outcome

Status: DRAFT, written by the executor on 2026-11-03 under PREREG A18 (R89). It binds as the
operator's document when the operator writes `ratified <date>` on the last line. From that
line on, its sha256 is a frozen-file gate and no session edits it; a change is a new document
with a new name and a new ratification.

1. A settled outcome is a fill on the HyperLiquid L1 that carries a transaction hash, as the
   venue's own public info API serves it (`userFillsByTime`), together with the funding
   payments the L1 charged or paid to the same address in the same window (`userFunding`).

2. The verified net of an address over a window `[T0, T1]` (milliseconds, inclusive, UTC) is

       realized_ex_funding = Σ closedPnl(fills with T0 ≤ time ≤ T1) − Σ fee(the same fills)
       net_with_funding    = realized_ex_funding + Σ funding.usdc(rows with T0 ≤ time ≤ T1)

   every term a Decimal taken from the payload's own string, never a float. `fee` already
   includes `builderFee`; it is subtracted once.

3. Both figures are always published together with the number of fills counted, the first
   and last transaction hash, and the coins and count of positions still open at `T1`. A
   position open at `T1` is counted and never valued.

4. Nothing else is an outcome. Not account value, not unrealized PnL, not a return on
   anything, not volume, not copies, not a figure the venue or any party computed, not a
   figure from `portfolio`, not a mark, not a mid.

5. A window opens after the observation it grades. Rows observed on day D are graded on
   fills from D+1 onward, never on D, and the window is declared before the first fill in it
   is read.

6. Coverage is disclosed, never estimated. If the public API served fewer fills than the
   address made in the window (its horizon is the 10 000 most recent fills), the row says
   `PARTIAL` and its figures are the figures of the fills served. If it served none, the row
   says `NONE`. Only `FULL` rows are ranked.

7. The machine never edits this document. The operator may.

ratified 2026-11-04 (the operator, in session at 06:3xZ: "ok ratify SETTLED.md now")
