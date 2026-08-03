> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Contested-set manifest — M-RI-17 frozen input (M-RI-16 final line)

```
definition: every parcel whose post-remediation verdict is CONTRADICTED or
            AMBIGUOUS in the M-RI-16 run — the set the belief-engine pass
            (M-RI-17) takes as its frozen input.
run:        audit/out/attested-remediated-2026-08-02/discrepancy_table.json
run sha256: d8567a4f10b6f16b04f19cca3175270a9a257142038c2dd319ea4fc3d7c215f1
inputs:     audit/attestation/attestations.yaml (13 events) + PREREGISTRATION amendments A1, A2
counts:     CONTRADICTED 9 + AMBIGUOUS 35 = 44 parcels (of 740; 405 checkable)
machine-readable twin: contested-set-manifest.json (byte-stable, emitted by the run)
```

| PIN | verdict | rule | CRM status | Recorder banner |
|---|---|---|---|---|
| 25-29-323-064-0000 | CONTRADICTED | D3 | Sold | YES — docs 2401822036/37 |
| 25-29-328-042-0000 | AMBIGUOUS | D5 | Sold |  |
| 25-29-411-049-0000 | AMBIGUOUS | D5 | Sold |  |
| 25-30-207-023-0000 | CONTRADICTED | D3 | Sold | YES — docs 2401822036/37 |
| 25-32-104-059-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-01-303-027-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-11-302-020-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-11-302-032-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-11-302-033-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 28-16-418-001-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-16-419-001-0000 | AMBIGUOUS | D5 | Sold |  |
| 28-30-113-005-0000 | CONTRADICTED | D3 | Sold |  |
| 29-02-408-053-0000 | CONTRADICTED | D3 | Sold |  |
| 29-15-200-026-0000 | CONTRADICTED | D3 | Sold |  |
| 29-15-200-041-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 29-30-108-016-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-123-019-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-123-020-0000 | AMBIGUOUS | D-nodate | Associated Parcel - Sold |  |
| 29-30-127-028-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-131-036-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-131-038-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-202-016-0000 | AMBIGUOUS | D5 | Sold |  |
| 29-30-218-016-0000 | CONTRADICTED | D3 | Sold |  |
| 29-30-218-038-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 29-30-218-039-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 29-30-218-040-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 29-30-218-041-0000 | AMBIGUOUS | D-nodate | Sold |  |
| 29-30-225-042-0000 | CONTRADICTED | D3 | Sold |  |
| 29-30-226-022-0000 | AMBIGUOUS | D5 | Sold |  |
| 30-17-113-007-0000 | AMBIGUOUS | D5 | Sold |  |
| 30-17-113-008-0000 | AMBIGUOUS | D5 | Sold |  |
| 30-17-202-025-0000 | AMBIGUOUS | D5 | Sold |  |
| 30-18-208-035-0000 | CONTRADICTED | D3 | Sold |  |
| 31-26-300-061-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-100-038-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-100-048-0000 | CONTRADICTED | D3 | Sold |  |
| 31-35-100-049-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-100-053-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-100-054-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-410-017-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-35-413-011-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-36-304-010-0000 | AMBIGUOUS | D5 | Sold |  |
| 31-36-306-026-0000 | AMBIGUOUS | D5 | Sold |  |
| 32-20-107-008-0000 | AMBIGUOUS | D1+NEAR-MISS | Sold |  |

Replay: `python -m audit.rerun_remediated` regenerates this manifest byte-identically from the frozen snapshots + the 13 attestation events.
