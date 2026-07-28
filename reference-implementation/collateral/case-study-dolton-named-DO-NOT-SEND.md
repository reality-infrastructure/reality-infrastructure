# LOCKED — requires SSLBDA written consent before any external use

> **DO NOT SEND. DO NOT EXCERPT. DO NOT RENDER TO PDF/HTML.**
> This file does not leave this repository. The client named below has not consented to
> external use of this material. The sendable version is
> `case-study-parcel-verification-v1.md` (and its PDF). Usage rules: `collateral/README.md`.

---

# Case Study: One Parcel, One Wrong Record

**The Registry Signal** — parcel verification for land banks and public land holders

---

## The situation

Land banks act on their inventory records. Acquisition, maintenance, disposition,
reporting to funders — all of it assumes the record is right. When a record is wrong, the
cost surfaces later: a deal that stalls, work ordered on the wrong parcel, a dispute over
who actually holds title. The cost of bad property records industry-wide is a matter of
published research: fraud and forgery claims now average $206,976 per refinance
transaction — nearly seven times all other claim types — and account for over 40% of
refinance-related title-insurer losses (ALTA-commissioned Milliman study, November 2025).

SSLBDA shared its parcel inventory with us — a 740-record export — as part of a pilot.
We selected one residential parcel in its service area — PIN 29-02-408-053-0000,
14347 Woodlawn Ave, Dolton, IL 60419 — and asked one question: **does the public record
agree with the inventory?**

## What we did

We pulled four sources for that one parcel: SSLBDA's own inventory record (feature 258
of the export), plus three public county sources — Assessor Parcel Sales (recorded deed
data), the Assessor Parcel Addresses assessment roll, and Treasurer tax-sale records.
Before pulling any data, we fixed in writing how much weight each kind of source would
carry. The data decides *what* the evidence says — never *how much it counts*.

Every value in the analysis traces to a named field in a frozen copy of its source
record. One source — the tax-sale data — returned nothing for this parcel, so it
contributes nothing: we state that plainly rather than treat silence as an all-clear
(which it is not).

## What we found

The inventory says the parcel was **sold on 2017-01-01**.

The county's recorded deed chain — six sale records spanning 2000 to 2017 — tells a
different story. The only conveyance recorded in 2017 is deed document 1717247010,
recorded 2017-06-16 — months after the date the inventory gives — and the seller of
record is RICHARD THORTON, a private individual, not SSLBDA (grantee CSMA BLT LLC,
sale price $65,000). In fact, SSLBDA appears in no queried public record for this parcel
at all — no deed, no assessment-roll year — across data running from 1999 through 2026.

Instead of hiding that disagreement, the analysis quantifies it: **40% of the belief
about this parcel's disposition is unresolved conflict**, traced to exactly two records —
inventory feature 258 and recorded deed 1717247010. Along the way, the same analysis
collapsed 17 different spellings of owner names scattered across the county data into
the 10 real parties behind them.

## Why this is different

A normal data pipeline handles disagreement by averaging, or by picking a winner —
"newest record wins," "the county wins." Either way the disagreement disappears, which
means nobody is told to go fix it.

This system holds the conflict, measures it, and names the two records that produced it.
Then it answers the question an executive actually asks: *what if the inventory entry
were corrected?* Rerun the analysis without that one record and the conflict falls from
40% to zero — confidence that SSLBDA never conveyed the parcel then rests on the
recorded deed at 0.8, with the remaining 0.2 left honestly uncommitted rather than
invented.

And the entire analysis replays byte-for-byte from its evidence log. Anyone you delegate
can rerun it and get the identical document, verified by checksum.

## What it means for you

Every parcel in your inventory can carry a dossier like this: what the public record
says, where it disagrees with your records, how serious the disagreement is, and which
specific record to fix. That turns "our data is probably fine" into a checkable,
prioritized worklist.

**We can run this against any parcel you name — the first one is how this case study
happened.**

---

> ### How it works, in plain language
>
> **Evidence log.** Every number in the dossier traces back to a named field in a frozen
> copy of a source record. No untraceable claims.
>
> **Pre-registered confidence.** How much weight each kind of source carries is fixed in
> writing *before* any data is pulled — so the answer cannot be tuned after the fact.
>
> **Conflict, kept on the page.** When records disagree, the disagreement is measured
> and reported — never averaged away, never silently resolved.
>
> **Replayable.** Rerunning the analysis reproduces the dossier byte-for-byte, verified
> by checksum.

---

*Informational analysis of public records for demonstration purposes.
NOT a title opinion, title insurance commitment, or legal advice. All figures come from a
reproducible, test-enforced analysis transcript; records as retrieved on the dates
listed in `pilot/MANIFEST.md` (2026-07-27).*

---

## Appendix: claims audit (named version only)

Every number and factual claim above, mapped to its banked artifact. Golden transcript =
`tests/golden/pilot/dolton_dossier.out` (M-RI-11, frozen). This table lives only in the
named version: an audit table in the anonymized version would necessarily carry the PIN,
document numbers, and record ids, defeating the anonymization (see `collateral/README.md`).

| Claim / number | Artifact |
|---|---|
| ALTA figures: $206,976 avg refinance fraud/forgery claim; ~7x other claim types; >40% of refinance-related title-insurer losses; Milliman study, Nov 2025 | `research/stage-1-prior-art/stage-1-adversarial-verdict.md`, "Beachhead ranking" item 5 (repo-external research bank, Reality-Infrastructure root) |
| 740-record inventory export; exactly 1 feature matched the PIN (feature 258) | `pilot/MANIFEST.md`, "CRM extract" section |
| Parcel identity: PIN 29-02-408-053-0000, 14347 Woodlawn Ave, Dolton, IL 60419 | Golden transcript header; `pilot/MANIFEST.md` |
| Four sources; one identity per source; tax source returned 0 rows and contributes no observation; "does NOT imply tax-clear" | Golden transcript Section 1; `pilot/MANIFEST.md` (ruling R3: queried Treasurer dataset is a dead endpoint) |
| Weights fixed before any data pulled (deed 0.8, assessor 0.6, tax 0.6, CRM 0.5) | `pilot/mass_assignments.md` (frozen at M-RI-11 Plan Gate); golden transcript Section 5 |
| Inventory says "Sold", date 2017-01-01 | Golden transcript Section 1, obs_o3 (crm_extract.json feature 258, fields USER_disp_status / USER_date_disposed) |
| Six sale records, 2000–2017 | Golden transcript Section 2, deed chain (ccao_parcel_sales, dataset wvhk-k5uv, 6 rows) |
| Deed 1717247010, 2017-06-16, RICHARD THORTON → CSMA BLT LLC, $65,000 | Golden transcript Section 2, deed chain, final row |
| SSLBDA in no queried public record, 1999–2026 (narrative, not an observation) | Golden transcript Section 9 (ruling R4); assessment roll = 28 rows, years 1999–2026 (Section 1) |
| 40% unresolved conflict on disposition, traced to two records | Golden transcript Section 5: m(∅) = 0.4000 [CONFLICT], "40.00% of belief mass" |
| 17 spellings → 10 parties | Golden transcript Section 2: 17-row attested alias table, "Alias-resolved entities (10)"; `pilot/MANIFEST.md` alias table |
| Counterfactual: conflict 40% → 0%; belief rests on the recorded deed at 0.8, remainder 0.2 uncommitted | Golden transcript Section 7: m(∅) 0.4000 → 0.0000; m({not_conveyed}) = 0.8000 |
| Byte-for-byte replay, verified by checksum | Golden transcript Section 8: Merkle root 68b45d8b…39fa, "byte-identical replay: OK"; enforced by `tests/test_pilot.py` (415-test suite) |
| Disclaimer wording | Golden transcript header disclaimer (M-RI-11 contract, Plan Gate item (g)) |
