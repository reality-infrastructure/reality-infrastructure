> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Exhibit re-score — post-remediation CONTRADICTED set (M-RI-16 Scope 7)

```
status: honest number holds at 1. Criteria (a)–(e) from M-RI-15, re-applied in
        order over the 9 post-remediation CONTRADICTED parcels. The two
        Recorder-bannered verdicts are excluded from exhibit consideration by
        construction (criterion (b) fails until a human reads docs
        2401822036/2401822037). Predicted at the gate: (c) passes for all 9,
        (b) still fails 8 of 9, honest number likely 1 — actual matches the
        prediction exactly.
```

## Per-parcel scoring (9 CONTRADICTED of 405 checkable)

(a) post-remediation stability · (b) citation completeness (contradicting deed
carries BOTH parties non-blank) · (c) independence from interpretation (the
escape set is now EMPTY — test-pinned — so (c) passes everywhere).

| PIN | (a) | (b) | (c) | Outcome |
|---|---|---|---|---|
| 25-29-323-064-0000 | PASS | FAIL (blank parties, docs 2401822036, 2431724049) | PASS | **EXCLUDED BY CONSTRUCTION** — Recorder banner |
| 25-30-207-023-0000 | PASS | FAIL (blank parties, docs 2401822037, 2424824048) | PASS | **EXCLUDED BY CONSTRUCTION** — Recorder banner |
| 28-30-113-005-0000 | PASS | FAIL (blank parties, doc 2329755175) | PASS | fails (b) |
| **29-02-408-053-0000** | **PASS** | **PASS** | **PASS** | **Exhibit 1 — re-verified** |
| 29-15-200-026-0000 | PASS | FAIL (blank seller, doc 2530824015) | PASS | fails (b) |
| 29-30-218-016-0000 | PASS | FAIL (blank parties, doc 2214007295) | PASS | fails (b) |
| 29-30-225-042-0000 | PASS | FAIL (blank parties, doc 2514124100) | PASS | fails (b) |
| 30-18-208-035-0000 | PASS | FAIL (blank seller, doc 2217317013) | PASS | fails (b) |
| 31-35-100-048-0000 | PASS | FAIL (blank parties, doc 2433824102, multi-parcel) | PASS | fails (b) |

**Tally: (a) 9/9 · (b) 1/9 · (c) 9/9 · survivors of (a)∩(b)∩(c): 1.**
(d) explanation economy: PASS for the survivor (three sentences). (e) diversity:
moot with one exhibit.

What changed vs the M-RI-15 scoring: criterion (c) went from 9/25 to 9/9 —
remediation removed every interpretation dependency (the escape set is empty
and test-pinned). The remaining bar is entirely criterion (b): the
transfer-declaration dataset records these conveyances with blank
grantor/grantee — the pre-registered coverage caveat, curable only by reading
the recorded documents (Recorder of Deeds), which is new data and a different
contract.

## Exhibit 1 re-verification under the M-RI-16 baseline (2026-08-02)

```
python -m audit.rerun_attested --pin 29024080530000 --baseline audit/out/attested-2026-08-02/discrepancy_table.json
```
Executed clean: verdict CONTRADICTED (D3), identical in the M-RI-14 baseline,
the M-RI-15 attested run, and this remediated run; the parcel's record set
contains no attested or escaped string (scan test-pinned); every citation in
`audit/out/attested-2026-08-02/exhibit-1-dolton-29-02-408-053-CLIENT-DO-NOT-SEND-PROSPECTS.md`
resolves against the frozen snapshots (test-asserted). The shipped exhibit
stands unmodified under the new baseline.
