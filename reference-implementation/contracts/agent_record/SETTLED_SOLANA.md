# What counts as a settled outcome on Solana

Status: DRAFT, written by the executor on 2026-11-08 under PREREG A32 (R133). It binds as the
operator's document when the operator writes `ratified <date>` on the last line. Until then no
Solana address is graded, no Solana tape runs and no Solana cohort is captured. From the
ratification line on, its sha256 is a frozen-file gate and no session edits it; a change is a new
document with a new name and a new ratification. It is the Solana counterpart of SETTLED.md
(HyperLiquid), written for the venue's Solana copy board ("Top Traders": 1D / 7D / 30D PnL, win
rate, trades, average hold, labels Smart Money / KOL/VC / Fresh Wallet / Sniper).

1. A settled outcome is a confirmed Solana transaction, identified by its signature, in which
   the graded wallet is a signer and which moves SPL tokens or SOL between the wallet's own
   accounts and a liquidity venue (an AMM pool or a launchpad bonding curve), as the public
   JSON-RPC serves it (`getSignaturesForAddress`, `getTransaction` with full metadata), the
   responses pinned verbatim beside the run as HyperLiquid's pages are.

2. The unit of account is the wallet's quote asset, SOL, valued in SOL and never converted to
   USD by the grader. A **round trip** in a token is the run of the wallet's swaps in that token
   from a zero balance to a zero balance (or to the window's end). Its realized net in SOL is

       proceeds_sol(sells) − cost_sol(buys) − fees_sol

   where fees are the transaction fees, priority fees and venue fees the transactions paid in
   SOL, each taken from the pinned transaction metadata (pre/post balances), never from a
   venue's or an indexer's figure.

3. The verified net of a wallet over a window `[T0, T1]` (slots or block times, inclusive, UTC)
   is the sum of the realized nets of the round trips that closed inside the window, published
   together with the number of round trips counted, the first and last signature, and the tokens
   and balances still held at `T1`. A token still held at `T1` is counted and never valued.

4. Nothing else is an outcome. Not a displayed PnL percentage, not a win rate the venue
   computed, not a USD figure, not an unrealized mark against a pool price, not an airdrop,
   not a token received without a swap, not a transfer between the wallet's own accounts.

5. A window opens after the observation it grades. Wallets observed on the board on day D are
   graded on transactions from D+1 onward, never on D, and the window is declared before the
   first transaction in it is read.

6. Open questions the operator answers or strikes before ratifying (each is a place where
   Solana's settlement is less clean than HyperLiquid's):
   a. Tokens received by transfer or airdrop and later sold: is the sale's proceeds an outcome
      with zero cost, or is the token excluded from round trips?
   b. Partial sells across several transactions and buys at several prices: FIFO within the
      round-trip definition above, or average cost? (The draft's definition needs neither: a
      round trip is graded as a whole from zero to zero.)
   c. A round trip still open at `T1` whose token has no liquidity (a rug): counted and never
      valued, as written, or disclosed with its last pool price?
   d. Which RPC endpoint is the public source of record, and what is served when an archive
      node's history is truncated (the horizon problem, as HyperLiquid's 10 000 fills)?
   e. Wallet linkage: the venue lists one address; a trader may operate several. The record
      grades the listed address only (as the HyperLiquid arena does) unless a chain-attested
      link exists.

7. The machine never edits this document. The operator may.

DRAFT — not ratified.
