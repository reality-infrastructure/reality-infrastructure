# M-RI-17 PREREGISTRATION — belief-engine pass over the post-remediation contested set

FROZEN. Committed strictly before any code under `audit/belief/` exists; the ordering is
provable from git history (`git log --format=%H -- audit/prereg/M-RI-17-PREREGISTRATION.md`
vs. the first commit touching `audit/belief/`). Every discretionary choice this pass makes
is declared here, before any belief object has been computed. A change to this file after
that first belief commit is the failure happening in real time (contract stop condition).

Plan Gate rulings referenced below (D1–D4, corrections, GO): operator session, 2026-08-04.

---

## §1 Frozen input

- Set: every parcel whose post-remediation verdict is CONTRADICTED or AMBIGUOUS in the
  M-RI-16 run — **44 parcels = 9 CONTRADICTED + 35 AMBIGUOUS** (of 740; 405 checkable).
- File of record: `audit/out/attested-remediated-2026-08-02/contested-set-manifest.json`
  sha256 `0a9df51fa5d14fdb609a467bc2534939ce0d40f33e1b80eb941c076895ec36fc`
  (markdown twin sha256 `24ea29624de28119899613e232d49914a319970c998e59f6379a4defdadbc567`).
  Named as M-RI-17's input by M-RI-16's DONE report §10. Run sha256
  `d8567a4f10b6f16b04f19cca3175270a9a257142038c2dd319ea4fc3d7c215f1`.
- Evidence universe: the frozen CF-025 snapshots under `audit/snapshots/` (retrieved
  2026-08-02, per-source retrieval attestations recorded in each snapshot file). No
  re-fetch. A source lacking data produces NO observation. NULL stays NULL.
- Recorder-banner flags (25-29-323-064-0000, 25-30-207-023-0000; docs 2401822036/37) are
  carried per parcel into every output of this pass.

**CORRECTION (recorded per GO ruling, 2026-08-04):** the contract's CONTEXT stated
"approximately 12 genuinely-contested parcels." That figure was wrong and does not bind
this pass. The frozen input is 44 parcels. The nearest on-disk referent of "~12" is the
multi-way-contest band observed at the Plan Gate (16 parcels with 3+ competing claims,
collapsing to ≈13 distinct contests across adjacent-PIN groups). Genuine contestedness is
a property this pass MEASURES; it is not assumed from the contract text.

## §2 Question and frame

One question per parcel: `ownership_shares`, subject `parcel:<pin14>`, exactly as the
wall-frozen C2 machinery poses it. Hypotheses are canonical share tables
(`shares:<ENTITY>=100`) derived from the folded channels' claims (§3) under the
enumeration conventions of §4. The frame is enumerated from the records before any mass
is assigned; a parcel whose facts cannot be expressed as mutually exclusive hypotheses
over one frame is a STOP, never a forced fit. (Plan Gate: all 44 enumerate cleanly.)

## §3 Channels folded and not folded (rulings D3, D4)

Folded (both statutory_registry / uncertaintyType ["measured"]):

1. **Deed chain-tails** — `audit/snapshots/ccao_parcel_sales.json` (Assessor - Parcel
   Sales, wvhk-k5uv). Grant events; a grantee of record never later divested of record
   carries a share claim; all other deed rows enter the log as record events with no mass
   (the C2 claim-window convention, unchanged).
2. **Assessor roll** — `audit/snapshots/cc_assessor.json` (Assessor - Parcel Addresses,
   3723-97qp). The max-year row's `owner_address_name` is the current owner-of-record
   assertion; chain_assertion event with a share claim.

Not folded, reported as cited per-parcel context only:

3. **Tax-sale rows** (annual 55ju-2fs9, scavenger ydgz-vkrp) — the wall-frozen adapter's
   tax-sale parser accepts only the R4-attested 2022 forfeiture-export shape; the
   snapshot rows would need semantic reinterpretation, and certificate-buyer interests
   cannot flow through it at all. Half-folding one side of a channel is worse than
   excluding it. **This under-reports conflict; it never inflates it** (ruling D3). Named
   limitation, citable.
4. **CRM disposition claims** — the frame is *who holds title per the records*; the
   client's self-asserted disposition is a claim about the client's own bookkeeping, not
   a competing answer to that question. Folding it would put two different questions on
   one frame — the frame-of-discernment error the stop condition exists to catch (ruling
   D4). Where the CRM names a purchaser, the determination reports it as context
   verbatim.

Consequence, accepted in advance: a parcel whose M-RI-16 CONTRADICTED verdict rests on
CRM-versus-county disagreement while the county records agree among themselves will
render low/zero conflict here. That is a records-completeness finding, not an ownership
contest, and the determination must say so per parcel in words.

## §4 Enumeration conventions (rulings D1, D2)

- **D1 — attested-alias canonicalization.** Any party string matched by the composed
  client predicate — `audit.rules.client_match(s)` OR `audit.rules.normalize(s)` equal to
  the normalized form of an attested `client-alias` variant from
  `audit/attestation/attestations.yaml` (via `audit.attestation.events.alias_strings`,
  both consumed read-only) — is canonicalized to the single form
  `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` before the adapter sees it.
  The attested client-alias variants at freeze (5):
  `LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY`,
  `SO SUB LAND BANK`, `SOUTH SUB LAND BK`, `SOUTH SUBN LAND BK & DEV AUTH`,
  `SO SUB LAND/BK/DEV`. The `uncertain` string `SUBURBAN LAND BANK &amp;` is NOT
  canonicalized — it stays a distinct hypothesis (the operator declined to attest it).
  The alias source is pinned by test: a silent change to attestations.yaml or to the
  predicate fails the suite. Verbatim strings remain in the determination's citations.
- **D2 — placeholder rule.** Roll owner strings in the pinned placeholder list produce NO
  roll observation (the county named nobody; folding the string would fabricate a
  claimant). Pinned list, exact strings: `TAXPAYER OF`. NULL stays NULL.
- **Spelling/spacing divergences stay distinct** (ZOLLER/ZOLLEN precedent, held hard at
  the gate): `PREFERRED`/`PREFFERED CALUMET LLC`, `B T L EMPIRE LLC`/`BTL EMPIRE LLC`,
  `RICHTON PARK VILLAGE`/`RICHTON PK` are distinct hypotheses. That is the record's own
  content; collapsing them is attestation work, not inference.
- Everything else is the wall-frozen adapter's own mechanical entity resolution
  (word-order and truncation rules), invoked as-is.

## §5 Mass assignments (declared, mirrored in code, test-pinned)

Per evidence-channel EP type, mass toward the event's claimed singleton; remainder to the
ignorance set Ω. These are the frozen declared priors of `rights_events/policy.py`
(`CLAIM_MASS`), restated here as this pass's declaration:

| Channel type | claim mass | folded this pass |
|---|---|---|
| statutory_registry | **0.6** | yes — every mass-bearing event (deed chain-tails, roll) |
| dispute events | **0** (fuse vacuously; all mass to Ω) | yes (adapter-emitted disputes) |
| cryptographically_signed | 0.55 | no event this pass |
| third_party_attested | 0.45 | dispute channel only (mass 0 by the dispute rule) |
| self_asserted | 0.3 | no event this pass (CRM not folded, ruling D4) |

**These assignments are discretionary declared priors, not measurements.** The
byte-identical replay guarantee covers exactly this: that these inputs, under these
declared numbers, reproduce these belief objects. It does not — and cannot — certify that
0.6 is the "right" trust in a statutory register. The numbers are mirrored in
`audit/belief/` and test-pinned against both this document and `policy.CLAIM_MASS`, so a
silent edit of any of the three fails the suite.

**One-element-frame rule (frozen pipeline, restated as the governing expectation):** the
wall-frozen fold declares a single-hypothesis frame uncontested by construction — its
claims fuse vacuously, so a single-claim parcel renders m(Ω) = 1 and m(∅) = 0. This
corrects the Plan Gate table's 0.6/0.4 figures for the n=1 band. The correction was made
pre-run, from reading the frozen `rights_events/pipeline.py`, before any belief object was
computed; the band's classification (high-ignorance) is unchanged. No fold code is
modified.

Fusion: the frozen Denœux cautious rule (`ri_core.reconcile.cautious_fuse`), unnormalized
— conflict is retained as mass on ∅, never normalized away. The cautious rule is
idempotent on equal simple supports: an entity asserted by both a deed tail and the roll
counts once at 0.6, not twice.

## §6 Snapshot → adapter-input mapping (declared)

Only the 44 manifest PINs. All name fields (buyer, seller, owner) pass through D1
canonicalization; roll strings pass the D2 placeholder filter.

- Deeds (`ccao_parcel_sales.json` records): `doc_no` → `doc_number`; `sale_date` →
  first 10 characters (ISO date); `buyer_name`, `seller_name`, `deed_type`, `sale_price`
  verbatim; `pin` = 14-digit PIN.
- Roll (`cc_assessor.json` records): per PIN, the row with the maximum `year`;
  `owner_address_name` → `owner_name`; `ingested_at` = the snapshot's own on-disk
  `retrieval.retrieved_date` (2026-08-02); property address fields carried verbatim;
  fields the snapshot does not carry stay null. NULL stays NULL.
- Forfeitures input to `parse_all`: the empty list (ruling D3).
- Every observation's provenance: `source_url` is the adapter's dataset URL for the
  channel; `observed_date` is the record's own date (deed sale date; roll retrieved
  date). Per-record dataset id, record id (deed doc number / assessor row id), and
  retrieved date are cited in the determination.

## §7 Invocation

`rights_events.adapters.cook_parcels.parse_all` → `rights_events.pipeline.RightsPipeline`
(ingest → `commit(subject, "ownership_shares", as_of)`), both wall-frozen, invoked as-is.
`as_of` = maximum event ltime in the data — derived from the records, never a clock. One
run over all 44 parcels; run file consumable by the existing replay CLI unchanged. If the
pass requires ANY change to ri_core, the adapter, the fold, or a frozen rule, that is a
finding and a STOP, not an edit.

## §8 Outputs

- `audit/belief/out/parcels_belief.ri` — the run file (event log + belief log).
- `audit/belief/out/belief_objects.json` — per-parcel belief objects with context.
- `audit/out/belief-determination.md` — the internal determination. Per parcel: the frame
  enumerated with each hypothesis's backing records; mass on each hypothesis; m(Ω) and
  m(∅) separated explicitly, in words as well as numbers — ignorance says go dig,
  conflict says stop; every source cited (dataset id, record id, source_url,
  observed/retrieved date); unfolded tax-sale and CRM context; Recorder banners carried.
- Mandated wording (GO ruling): for every single-claim (n=1) parcel, one sentence stating
  that mass on Ω means **no counter-claim was found in the captured snapshots** — not
  that the claim is uncontested in the world. Absence is framed as "no record found,"
  never as a claim about reality.
- For every CONTRADICTED parcel whose county records agree among themselves, one sentence
  stating that the M-RI-16 contradiction is CRM-versus-county — a records-completeness
  finding, not an ownership contest.
- No dollar figures. No external-facing claims. Internal determination only.

## §9 Counts: UNKNOWN

The counts of high-conflict versus high-ignorance parcels are **UNKNOWN** at freeze. They
are measured by the run and reported as measured — never predicted here. Plan Gate
expectations exist in the session record and do not bind the run; any divergence between
expectation and measurement is reported as a finding, in either direction.

## §10 Known-answer commitment

The Dolton parcel (`parcel:29024080530000`, PIN 29-02-408-053-0000), re-run through this
pass from the frozen audit snapshots, MUST reproduce **m(∅) = 0.91296 exactly** (the
C2 wall-frozen result). If it does not, that is the finding and a STOP — the pass is not
tuned to match. No mass, convention, or mapping in this document may be adjusted after a
belief object has been seen; that adjustment IS the failure happening in real time.

## §11 Stop conditions (restated)

Halt and report if: the contested set cannot be read unambiguously from the pinned
manifest; a parcel's facts cannot be enumerated as mutually exclusive hypotheses over one
frame; the Dolton known-answer does not reproduce; the pass would require any change to
ri_core, the adapter, the fold, or a frozen rule; a mass assignment is contemplated or
adjusted after a belief object has been seen; a golden file's bytes would change; or an
acceptance test cannot pass without violating a MUST.
