# What counts as a settled outcome on Solana

Status: drafted by the executor on 2026-11-08 under PREREG A32 (R133); the open questions of
section 6 answered on the three transcripts at the operator's word and the document RATIFIED
the same day (A34). From the ratification line on, its sha256 is a frozen-file gate and no
session edits it; a change is a new document with a new name and a new ratification. It is
the Solana counterpart of SETTLED.md (HyperLiquid), written for the venue's Solana copy board
("Top Traders": 1D / 7D / 30D PnL, win rate, trades, average hold, labels Smart Money / KOL/VC /
Fresh Wallet / Sniper). No Solana grader, tape or cohort runs until a dated PREREG amendment
opens one under this document.

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

3. The verified net of a wallet over a window `[T0, T1]` (block times, inclusive, UTC) is the
   sum of the realized nets of the round trips that closed inside the window, published
   together with the number of round trips counted, the first and last signature, and the tokens
   and balances still held at `T1`. A token still held at `T1` is counted and never valued.

4. Nothing else is an outcome. Not a displayed PnL percentage, not a win rate the venue
   computed, not a USD figure, not an unrealized mark against a pool price, not an airdrop,
   not a token received without a swap, not a transfer between the wallet's own accounts.

5. A window opens after the observation it grades. Wallets observed on the board on day D are
   graded on transactions from D+1 onward, never on D, and the window is declared before the
   first transaction in it is read.

6. The open questions, answered on the three transcripts (each answer is the simplest rule that
   a stranger can recompute from the pinned bytes; the panel, 2026-schulman-millidge-oneill.md
   @ 32:54–32:59: "relax on the realism axis a little bit and find some methods that actually
   work, and then try to get back to realism later after the method matures a little bit"):
   a. A token received by transfer or airdrop and later sold is NOT a round trip and its sale is
      not an outcome (rule 4: "not a token received without a swap"); the sale's signature is
      listed under the wallet as "sold without a swap-in", never netted. Brown, 2026-brown.md
      @ 1:16:41–1:16:58: the answer key in the folder is not the test; a token the wallet did
      not buy is not the wallet's trade.
   b. Partial sells and buys at several prices need neither FIFO nor average cost: a round trip
      is graded as a whole from zero balance to zero balance, as rule 2 says. One definition,
      no parameter (the operator's sixth rule: one changed variable per contract).
   c. A round trip still open at `T1`, with or without liquidity, is counted and never valued
      (rule 3, as SETTLED.md 3 for HyperLiquid). Musk, 2026-musk.md @ 53:12–53:19: "you can
      fool our ability to tell what it did with reality" — a pool price on a dead token is that
      fooling; the record prints the balance and no price.
   d. The public source of record is the Solana Foundation's public mainnet JSON-RPC
      (`https://api.mainnet-beta.solana.com`), its responses pinned verbatim; where that node's
      history is truncated for a wallet, the window is graded PARTIAL with the first served
      signature named, exactly as the HyperLiquid horizon is disclosed (A18, R114). No archive
      provider's figure is substituted. Musk @ 52:10: "Reality is the best verifier."
   e. The listed address only is graded. A chain-attested link between wallets (a signed
      transaction from one funding the other is NOT such a link; an on-chain registry entry is)
      may be added by a dated amendment; nothing is grouped by inference.

7. The machine never edits this document. The operator may.

ratified 2026-11-08 (the operator, in session at 06:1xZ: "Use the three transcripts verbatim to sign the following: … the Solana ratification …")
