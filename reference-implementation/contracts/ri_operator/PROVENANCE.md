# PROVENANCE — where each command came from

Hashed 2026-11-14 with `sha256sum`, at the time of the copy. Paths outside this
repository are relative to the operator's home directory. This file lives under
`contracts/` and not in the pack, because the source paths contain nouns the pack is
forbidden to carry (PREREG.md, banned nouns).

| Command | Source | sha256 |
|---|---|---|
| ri-bottleneck | `~/.claude/commands/bottleneck.md` | `c8842f07c3541095f842df5e2770cf929fd44e514f75cc0266854fd1737cf655` |
| ri-judgment | `~/.claude/commands/judgment.md` | `006eb102ab13202ee46dbd789ddf0d610b25af1c09a8989ee5e6de13e2d583d6` |
| ri-gate | `~/hyperliquid/.claude/commands/gate.md` | `0aad4c2802e91b231b89023df9e858376ce385f95008d9ff885802a601cb3bfe` |
| ri-gate | `~/rich/scan/prompts/disprove.md` | `fe47abf0bccad6afb336641ab2dbb9fc4ab5bb9935b50d7a06c649270cf1eb6a` |
| ri-pack | `reference-implementation/HARNESS.md` (this branch) | `9d1fe79f3f700dc62e1bd61e662e333834664669e7f90f6c681fcf1fe51b9dc2` |
| ri-evidence | `forge/README.md` (this branch) | `9a51a644a986c645425199597687a68f6e0d86ffa2ebee34997c76fef872fc42` |
| ri-evidence | `~/power-path/agents/PROTOCOL.md` | `4139717d76574b2b6822c73f557fce3053a0e1b7a2aac199db8293fe179ef85b` |
| ri-scan | `~/ladder/rules/invariant-scan.md` | `c208d8b4ba5b2a48fe9d6b5d3cf2cb290d0d095b70b563589071a89e08333b46` |
| ri-scan | `~/hyperliquid/.claude/commands/morning.md` | `c3590257f4cc6ea0b40cd0c5ad00bc43863f4fcb09746a07b1ac06819d68a9c5` |
| ri-week | `~/hyperliquid/.claude/commands/week.md` | `5eec0aef9b7d61272eaeaea3147a865d240ca3f02ed0300b310cd259caa35911` |
| ri-week | `~/rich/scan/prompts/disprove.md` (the tripwire test) | `fe47abf0bccad6afb336641ab2dbb9fc4ab5bb9935b50d7a06c649270cf1eb6a` |

## What changed in the copy

- **ri-bottleneck, ri-judgment:** the protocol is kept. Domain examples were removed,
  a "why this exists" paragraph and a RECORD step were added.
- **ri-gate:** the five passes and eight checks are kept. Every instrument-specific
  command and example was removed. The single log line became two events (the
  author's request, the disprover's verdict). The verdict rule was made explicit;
  the source left the choice of verdict to the reader.
- **ri-pack:** new text. It wraps existing engine commands and adds no mechanism.
- **ri-evidence:** the evidence-item fields and the "error is not empty" rule are
  kept. The domain's mass policy and claim file are not carried; the command stops
  at the evidence.
- **ri-scan:** kept from the 626-line source: counted-never-read, scoring the previous
  scan, the production line, the piles, the proxy and comparison passes, the
  comfortable-candidate gate with its four uncomfortable candidates, the one-constraint
  verdict with test, price, exploit, subordinate and next constraint. Dropped: every
  program-specific rule, figure, file path and the amendment procedure. From the morning
  scan: reproducing the baseline, the three questions and the single move. Seven further
  passes of the source moved to ri-week, where the weekly source also has them.
- **ri-week:** the eight steps are kept. The instrument that built the sheet is replaced
  by `record.py list`; execution grades, watch rows and clocks became events. The rule
  that nothing is carried a third week is enforced by the event schema.

## The five interviews

The "why this exists" paragraph in each command and the table in
`packs/ri_operator/README.md` restate points made in five published interview
transcripts supplied by the operator on 2026-11-14 (Brown; Schulman, Millidge and
O'Neill; Musk; Patel; Naval). They are paraphrases, not quotations, and the
transcripts are not in this repository.
