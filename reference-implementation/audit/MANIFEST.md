# M-RI-14 AUDIT MANIFEST — retrieval provenance
```
Every snapshot consumed by the audit is recorded here: source, exact query or path,
retrieval date, record count, sha256. The audit phase reads only snapshot bytes; this
file is the chain of custody. Discipline mirrors pilot/MANIFEST.md.
```

## Extract-phase entry (written by extract_crm.py)

| file | source | source sha256 | extracted | records | checkable | snapshot sha256 |
|---|---|---|---|---|---|---|
| crm_inventory.json | All_Inventory.geojson | 8d42089d14a03dfceb285a09f22147486f4c5d3279de6f2b833d4d3d46737067 | 2026-08-02 | 740 | 694 | 486f47c2950eacd0d3fedac529029ef03de4eba3074406c2693c46ec374d2db9 |

## Fetch-phase entries (written by fetch_batch.py --consolidate)

| file | source_id | dataset id | dataset name | retrieved | records | failed PINs | sha256 |
|---|---|---|---|---|---|---|---|
| ccao_parcel_sales.json | ccao_parcel_sales | wvhk-k5uv | Assessor - Parcel Sales | 2026-08-02 | 1185 | 0 | ddc838d777e2fc2d3e25c03e56f173105ba5df4a24e75b11c1484c8956b41088 |
| cc_assessor.json | cc_assessor | 3723-97qp | Assessor - Parcel Addresses | 2026-08-02 | 18483 | 0 | 957a0d9b5d1a973ed6e2fceec9215626a8f3b3e59ec3590a9c4f4d1a8a0bd519 |
| tax_agency.json | tax_agency | 55ju-2fs9 | Treasurer - Annual Tax Sale | 2026-08-02 | 1083 | 0 | 5128b816680790eaac90e1b8ce20d34f36d1991f3bd6428cf133349f1bdfe874 |
| tax_agency_scavenger.json | tax_agency_scavenger | ydgz-vkrp | Treasurer - Scavenger Tax Sale | 2026-08-02 | 35 | 0 | 2243c4ec65617ee3d6d2c382acea9b8aaefab21d6b19fd1fec88be039d1987bf |

Query form: SODA `$where=pin in(...)` batches of 50 over the 694 checkable PINs; exact per-batch URLs preserved in `snapshots/shards/<source_id>/batch_NNN.json`.
