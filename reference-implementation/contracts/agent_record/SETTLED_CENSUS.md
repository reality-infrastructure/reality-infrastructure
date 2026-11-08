# The census: a second, weaker class of evidence, named as such

Status: written by the executor on 2026-11-08 under PREREG A30 (R129) and RATIFIED the same
day on the operator's word (A34). SETTLED.md is frozen and is not changed by this document; a
census row is never a settled outcome under SETTLED.md and is never shown as one. From the
ratification line on, this document's sha256 is a frozen-file gate; a change is a new document
with a new name and a new ratification.

1. Why it exists. The arena pins every page of every graded address verbatim; that is what lets
   a stranger recompute a grade from the record's own bytes, and it is why the arena can carry
   about seventy addresses a day on this channel (A30: 14.4 MB an hour, two addresses half of
   it). The venue's board lists 48 237 addresses. To score all of them every day, a cheaper
   instrument is needed, and a cheaper instrument is weaker evidence. This document says
   exactly how much weaker, so that the two are never confused.

2. What a census row is. For each address on the venue's board as served on day D, one
   `userFillsByTime` request for the window [D−1 00:00:00.000Z, D−1 23:59:59.999Z] with at most
   2 000 fills. From the response, and before the response is discarded, the census keeps: the
   address, the day, the number of fills served, Σ `closedPnl`, Σ `fee` (which includes
   `builderFee`), the first and last fill time, the response's byte length and sha256, and the
   fetch time. Nothing else is kept and the bytes are not pinned.

3. What a census row is not. It is not re-verifiable from the record: a stranger can only
   re-fetch the same window while the API still serves it (its 10 000-fill horizon) and compare
   the sha256. It carries no funding (one request per address, not two). It is never `FULL`,
   `PARTIAL` or `NONE`; its words are **CENSUS-WHOLE** (fewer than 2 000 fills served: the whole
   day was served) and **CENSUS-CUT** (2 000 served: the day was cut by the page cap). It is
   never ranked with arena rows, never averaged, never a status under R119, never a board row.

4. What a census row may do. An address that is CENSUS-WHOLE with Σ `closedPnl` − Σ `fee` > 0
   on k consecutive days (k = the marker's `k_for` of the number of addresses so counted, never
   fewer than 5) may be named in a dated PREREG amendment for the next pinned cohort, where it
   is graded under SETTLED.md with its pages verbatim. The census finds candidates for the
   arena; it decides nothing by itself.

5. Cost, as pre-registered. About 48 237 requests a day (≈ 2 010 an hour, inside the API's
   1 200 weight a minute; the census runs as its own process with its own budget and never
   borrows the arena tape's), about 10 MB a day of rows kept, zero pages pinned. It starts only
   when a dated amendment (P26) installs it, which is the operator's act on the VPS.

6. The machine never edits this document. The operator may.

ratified 2026-11-08 (the operator, in session at 06:1xZ: "Use the three transcripts verbatim to sign the following: … the census decision …")
