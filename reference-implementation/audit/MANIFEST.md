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
