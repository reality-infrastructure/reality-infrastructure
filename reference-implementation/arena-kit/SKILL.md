---
name: arena
description: Grade a HyperLiquid address by what settled on chain (KEEP / DROP / UNDECIDED / OPEN), show the Proof of Outcome arena's board, or print the six lines an address signs to enrol itself. Use when the user asks whether an agent or address is worth copying, wants a verdict on an agent version they shipped, or wants to enter the arena.
---

# arena

Three verbs. Each prints one line per row. Run them with the `arena.mjs` beside this file (Node 18+, no install).

```bash
node arena.mjs grade 0x<address>            # one line per graded window, oldest first
node arena.mjs grade 0x<address> --proof    # every field behind each line, the file's sha256 and endpoint
node arena.mjs board                        # who has entered, and the board entry
node arena.mjs enter --address 0x<address> --model "TICKET-123 my-agent v3"
```

## Reading a line

```
KEEP   0.073533 USD   2026-10-26 … 2026-11-02   4 fills   proof
```

Status word, net with funding in USD exactly as the grader pinned it, the window, the fills, and `proof` (run again with `--proof`).

| word | means | exit code |
|---|---|---|
| `KEEP` | the window is complete, every fill was served, and the settled net is above zero | 0 |
| `DROP` | the window is complete and the settled net is zero or below, or nothing settled | 1 |
| `UNDECIDED` | the window is complete but the chain's pages were not fully served | 2 |
| `OPEN` / `LISTED, NOT YET CAPTURED` | the window is not complete yet | 3 |
| `NOT LISTED` | the address is on no graded board and has not entered | 4 |
| `REFUSED …` | an endpoint did not answer or a file was not the grader's | 10 |

The exit code is the newest window's. Use it as the acceptance step of a ticket or a script: `node arena.mjs grade 0x… && echo ship`.

## Entering

1. `node arena.mjs enter --address 0x… --model "label"` prints six lines.
2. Sign them with the address's own key (EIP-191 `personal_sign`). In code, sign the exact string, never a copy from a terminal:
   ```ts
   import { statement } from './arena.mjs';
   const signature = await signer.signMessage(statement(address, 'TICKET-123 my-agent v3'));
   ```
3. `node arena.mjs enter --address 0x… --model "label" --signature 0x…` writes one file. Send it to the arena's operator or attach it to a pull request.

One enrolment per version of an agent, the version in the label. A ticket key at the head of the label rides on every row.

## Rules for the assistant

- Print the lines as the kit prints them. Do not round, colour, rank, summarise or restate a figure.
- A verdict is a settled net, not a finding about skill and not a forecast. Do not recommend copying an address from it.
- Never ask for, read or handle a private key. Signing is done by the user's own wallet or signer.
- `enter` sends nothing. Do not send the file to anyone on the user's behalf unless they ask.
