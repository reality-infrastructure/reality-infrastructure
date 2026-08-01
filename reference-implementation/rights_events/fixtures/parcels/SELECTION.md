# Parcel selection — Contract 2 plan gate (2026-08-01)

Nine Dolton-area (Cook County) parcels. Contested means: at least two of
{latest-deed grantee, assessor taxpayer-of-record, tax-sale/forfeiture
interest} name different entities, under the M-RI-11 rule that distinct
strings are distinct frame entities absent record evidence linking them.
Every contest below is a statement that RECORDS DISAGREE and requires
verification against the underlying instruments — it characterizes the
records, never the people named in them (privacy ruling R1).

Eight parcels appear in the Treasurer's 2022 Annual Tax Sale results as
"Forfeited - Sold to Cook County" (sale date 2024-12-11) — a live
competing tax interest per ruling R3. PIN 29024080530000 is the M-RI-11
pilot parcel and is not in that file.

| PIN | Classification | Records basis |
|---|---|---|
| 29024080530000 | contested | M-RI-11 pilot: deed chain ends CSMA BLT, LLC (2017); assessor roll says FIRST KEY HOMES / FIRSTKEY HOMES; SSLBDA CRM self-reports a 2017 disposition the deed record contradicts |
| 29033140260000 | contested | deed chain BP CAPITAL -> FATHERS AND BLESSINGS NFP (2021) -> KAMILLE STONE (2025, seller not the prior grantee of record); assessor says BP CAPITAL; forfeited 2022 sale |
| 29102240510000 | contested | deed chain ends SHAYNA L. HARRIS (2022 warranty); assessor says CHICAGO ANTI EVICTION; forfeited |
| 29111190340000 | contested | 2014 deed from DAVID D. ORR (County Clerk; tax-deed pattern) with buyer recorded as UNKNOWN, against a 2017 JOHNSON -> DOSS chain; assessor says RAYMOUND DOSS; forfeited. Per M-RI-11 I6, the UNKNOWN row contributes no owner claim |
| 29034020350000 | contested | ERIC LONG (2005) against 2025 NETNET, LLC -> ERIC RIVERA deed (seller not in chain); assessor says ERIC LONG; forfeited |
| 29031010050000 | contested (borderline) | deeds end JAMES STANDORS (2002); assessor says WILIE MAE STANDORS; distinct strings, plausibly related — kept as the borderline case |
| 29031100330000 | happy path | clean chain to JOHN HERNDON; assessor matches |
| 29092100180000 | happy path | clean chain to LEZETTE MILTON; assessor matches |
| 29031060220000 | happy path | single deed to ILLIANA FINANCIAL CREDIT UNION; assessor matches |

Frame-size handling (plan-gate item 6, approved): mapped ownership
claims per parcel are only (i) the latest deed per distinct chain tail,
(ii) the current assessor roll entry, (iii) any live tax-sale interest.
Historical deeds enter the log as record events without share claims.
Worst frame here is 4 hypotheses (engine limit 8). If a future export
surfaces a parcel exceeding 6, it is dropped for one that does not.
