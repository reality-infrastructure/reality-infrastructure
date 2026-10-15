# PRE-REGISTRATION: TRADING-FRAME (net_pnl_bucket conflict-mass fold, PATH B)

Frozen BEFORE `trading_frame/fold.py` or `trading_frame/run.py` exists. The commit that
adds this file strictly precedes the commit that adds any fold/run code; that ordering is
the proof (disk-beats-memory; pre-registration = the metric committed before the result).
No number below may be edited after a consuming-code commit lands; a wrong prediction is
recorded as wrong, never quietly corrected.

## 1. Question and frame (closed)

- Question id: `net_pnl_bucket`.
- Frame Ω = `{GAIN, FLAT, LOSS}` (sorted canonical: `FLAT,GAIN,LOSS`). A fixed, declared
  3-answer frame — not built from whichever hypotheses happen to appear — so the
  unresolved set is always the full Ω and is comparable across captures.
- Bucket rule (matches the PATH A adapter): `net > 0 → GAIN`, `net < 0 → LOSS`,
  `net == 0 → FLAT`, over Decimal arithmetic, ε = 0.

## 2. Mass model (closed, Decimal-only)

Two simple support functions over Ω, fused by `ri_core.reconcile.cautious_fuse`
(pointwise minimum of conjunctive weights; no new arithmetic in fusion):

- **Venue (displayed) claim** — EP `self_asserted`, prior `CLAIM_MASS[SELF_ASSERTED] =
  0.30` (imported from frozen `rights_events.policy`):
  `m({displayed_bucket}) = 0.30`, `m(Ω) = 0.70`.
- **Chain-realized claim** — EP `cryptographically_signed`, prior
  `CLAIM_MASS[CRYPTOGRAPHICALLY_SIGNED] = 0.55`:
  `m({chain_bucket}) = 0.55`, `m(Ω) = 0.45`, where `chain_bucket` buckets the Decimal sum
  over the capture's fills of `realized_pnl_usdc − fee_usdc`.

Rationale pinned: the chain-realized weight exceeds the venue weight because realized PnL
is a chain-measured outcome of signed transactions, not an interested party's assertion.
The PATH A `dispute` event is NOT a fold input (its `focal_mass` is 0 by the frozen
dispute-fuses-vacuously rule); PATH B derives the chain bucket from the signed fills
directly.

## 3. Known-answer — MISMATCH case (PINNED)

Holds for the SYNTHETIC capture (displayed `GAIN` 0.30 vs chain `LOSS` 0.55) and the REAL
2026-10-15 HyperLiquid capture (displayed `LOSS` 0.30 vs chain `GAIN` 0.55) — the two are
mirror images and yield identical masses by relabeling:

| subset              | mass   |
|---------------------|--------|
| ∅ (conflict)        | 0.165  |
| {chain_bucket}      | 0.385  |
| {displayed_bucket}  | 0.135  |
| any 2-element set   | 0      |
| the other singleton | 0      |
| Ω = {FLAT,GAIN,LOSS}| 0.315  |

- `conflict_mass` (mass on ∅) = **0.165**
- `unresolved_mass` (mass on Ω) = **0.315**
- chain-realized bucket carries **0.385**; displayed bucket carries **0.135**.
- Sum of all masses = 1 exactly.

Chain net per capture (for the record): SYNTHETIC `−306.50` (LOSS); REAL 2026-10-15
`+27.676980` (GAIN).

## 4. Known-answer — AGREEMENT case (PINNED)

When the displayed bucket equals the chain bucket (e.g. displayed `GAIN` 0.30 vs chain
`GAIN` 0.55):

| subset              | mass   |
|---------------------|--------|
| ∅ (conflict)        | 0      |
| {agreed_bucket}     | 0.55   |
| Ω                   | 0.45   |
| everything else     | 0      |

- `conflict_mass` = **0** — the fold reports contradiction only when the evidence
  actually contradicts itself.

## 5. Reproducibility prediction (PINNED)

- Folding the same events twice is byte-equal (pure function).
- The belief object logged by the runner re-folds byte-for-byte from the reloaded,
  signature-re-verified event log (conflict mass is a reproducible function of the signed
  inputs, not a stored constant).
- A single altered byte in a saved fill makes reload raise.

## 6. What would falsify this contract

- Any gate masses differing from §3/§4 after the code lands.
- A need to edit any frozen module to produce the fold (would be a kill-finding, not a
  fix).
- The agreement case producing nonzero conflict (would prove the fold rigged).

## 7. AMENDMENTS (dated, append-only)

### A1 — 2026-10-15 — known-answer for the gdex-sourced captures (PINNED before gates)

Inputs pinned in `contracts/trader_record/PREREG.md` §7 A1 (same commit as this
amendment; the consuming gates land strictly later):

- `capture_REAL_2026-10-15_gdex.json` sha256
  `a84893e857a80405b6afa2689c9df4226cbba9c48caf6912f06bf96c8774601c` — displayed GAIN
  (0.30) vs chain LOSS (0.55); chain net `-1092671.088114`.
- `capture_REAL_2026-10-15_gdex_multi.json` sha256
  `e3b47fa51e32dd021d23a985764b6e0f42b2377e001c1c6aca54953da01766b1` — displayed GAIN
  (0.30) vs chain LOSS (0.55) over a 5-address actor; chain net `-401006.054671`.

Both are the §3 MISMATCH case and MUST yield exactly: `conflict_mass` **0.165**, mass on
`LOSS` (chain) **0.385**, mass on `GAIN` (displayed) **0.135**, `unresolved_mass`
**0.315**, `FLAT` and every 2-element subset **0**, sum **1**. The venue weight stays
0.30 even though the venue is now gdex's own endpoint rather than the underlying HL API
— the EP type (`self_asserted`) is what sets the prior, not the host. The §5
reproducibility predictions hold unchanged (re-fold byte-identical from the reloaded
log; one-bit tamper fails reload). A different mass is a STOP, not a retune.
