# Analysis 1 — Delinquency-while-held (summary)

> **INTERNAL WORKING — NOT VERIFIED FOR EXTERNAL USE. Numbers pending attestation-stability per F1 discipline.**

Baseline: post-M-RI-16 remediated run (`audit/out/attested-remediated-2026-08-02/`, produced by `rerun_remediated.py` under `rules.py` sha256 `33bf6bfb…86a7`, the PREREGISTRATION §9 A2 re-pin; inputs read at HEAD `0139558` "M-RI-16-P2"). Note: during this pass, commit `59b8f39` "M-RI-16-P3" landed (not made by this session), committing the remediated outputs; input bytes verified unchanged.

## Input set — correction to the directive's premise

The directive named "the 342 county-confirmed-held PINs." No such set exists in any output on disk. The county-confirmed-held set is **claim_class = HELD, verdict = SUPPORTED** in `attested-remediated-2026-08-02/discrepancy_table.json` (field `verdicts[]`): **99 parcels** (98 via rule H1, 1 via H2). All figures below use N = 99.

## Fields actually present (enumerated before joining)

No fetched dataset contains a `tax_status` or `is_exempt` field, and **only Cook County datasets exist on disk** (no Will/Lake/McHenry data was ever fetched; per-county coverage cannot be reported because there is exactly one county of coverage). What exists:

- `55ju-2fs9` (Treasurer – Annual Tax Sale, retrieved 2026-08-02): `tax_sale_year` (**2011–2014 only** — dead endpoint per pilot MANIFEST ruling R3), `sold_at_sale`, `tax_amount_offered`, `penalty_amount_offered`, `total_tax_and_penalty_amount_offered`, `cost`, `total_amount_paid`.
- `ydgz-vkrp` (Treasurer – Scavenger Sale, retrieved 2026-08-02): `tax_sale_year` (2009–2015), `from_year`/`to_year`, `sold_at_sale`, `total_amount_paid`.
- `3723-97qp` (Assessor – Parcel Addresses, retrieved 2026-08-02): no tax or exemption field; the only exemption signal is the literal owner string `EXEMPT` in `owner_address_name`.

## Finding classes (operational definitions; precedence: tax rows > exempt > non-exempt > null)

| Finding | Count | of |
|---|---|---|
| DELINQUENT-WHILE-HELD | **40** | 99 |
| NON-EXEMPT-WHILE-HELD | **59** | 99 |
| EXEMPT-CURRENT | 0 | 99 |
| STATUS-NULL | 0 | 99 |

- **DELINQUENT-WHILE-HELD** here means: ≥1 Treasurer tax-sale record exists for the parcel. **The "while-held" temporal claim is NOT established from disk**: the tax-sale records are 2009–2015, and a land bank characteristically *acquires* parcels because they were tax-delinquent — the delinquency may predate the holding.

### A3 temporal recompute (2026-08-03; PREREGISTRATION §9 A3 — classes pre-declared before the join, year-granular)

`USER_acq_secure_date` re-extracted from the pinned source into `crm_acq_dates.json` (sha256 `480c2752…ebedd`; 72 of 740 features non-null). Split of the 40:

| Temporal class | Count | of |
|---|---|---|
| ACQ-DATE-NULL | **38** | 40 |
| PRE-ACQUISITION | **2** | 40 |
| SAME-YEAR-INDETERMINATE | 0 | 40 |
| POST-ACQUISITION-ANOMALY | 0 | 40 |

The amendment resolves the question the data can answer and names the one it cannot: **zero anomalies were found, on a 2-of-40 datable base** — the acquisition-date field is null for 38 of the 40 flagged parcels (and 97 of all 99 held parcels). The two datable parcels (secured 2025-08-01 and 2026-03-20, tax sales 2011–2014) both classify PRE-ACQUISITION — the expected land-bank pattern. The finding's final frame is therefore the conveyability form: **40 of 99 county-confirmed-held parcels carry 2011–2014 tax-sale records of $206,101.76 in offered tax-and-penalty amounts, and whether those interests were redeemed or extinguished at acquisition is not determinable from disk for 38 of the 40** — confirmation routes through Clerk records (see `scoped_not_run.md`, deliverable 3).
- **EXEMPT-CURRENT = 0 is structural, not substantive**: 98 of the 99 parcels are held-supported via H1, which requires the client's name in the max-year assessor owner/mail field — a parcel showing `EXEMPT` there could not have been H1-supported in the first place. The proxy cannot fire on this set by construction. A real exemption check requires the assessed-values/exemptions dataset (a (c)-class fetch, not performed).
- **NON-EXEMPT-WHILE-HELD** means only: the max-year assessor owner field shows a taxpayer name (the client's) rather than `EXEMPT`. It is a weak proxy, stated as such.

## Dollar exposure

- Annual tax sale, field `total_tax_and_penalty_amount_offered`, summed verbatim: **$206,101.76 — denominator: 40 of 99 held parcels carry amount data** (0 NULL amount rows among their 155 tax-sale rows; tax years 2011–2014).
- Scavenger sale, field `total_amount_paid` (different semantics — amount paid by the sale buyer, not the delinquency; NOT added to the figure above): **$1,810.00 over 4 of 99 parcels**.

Assessed values and recorded tax amounts are defensible from disk; market-value dollar claims are not computable from this data and are not estimated.

Every row in `delinquency_while_held.csv` cites dataset id, verbatim field values, and retrieval date (2026-08-02 for all four audit snapshots).
