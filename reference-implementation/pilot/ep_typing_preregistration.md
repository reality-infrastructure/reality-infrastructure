# M-RI-13 PRE-REGISTRATION — EP typing wired into RI's evidence layer (Dolton parcel)

Committed BEFORE any reconciliation/projection code change (verify ordering in git history).
Baseline: M-RI-11 dossier at 5811b69, golden `tests/golden/pilot/dolton_dossier.out`
sha256 `6ece101e4d96c2d81ee61b816597f6025a0644f44e49320e635cc664a32f93a2`.
Vocabulary: EP promoted set-valued schema, CANON CF-020
(`capability-factory/canon/provenance-assertion-schema-set.md`): `uncertaintyType` is a
set (JSON list, 1+ terms, no duplicates, order not meaningful) over the closed five-term
vocabulary {measured · estimated · asserted-by-interested-party · inferred-from-proxy ·
true-as-of-date-decaying}. Matching is membership, never string comparison of the set form.

## 1. Type assignment for each Dolton claim (FIXED NOW, ruling R1 of the GO)

| Obs | Claim | uncertaintyType | Justification from the source |
|-----|-------|-----------------|-------------------------------|
| O1 `obs_o1_ccao_owner` | current_owner ← CSMA BLT LLC | `["measured"]` | Recorded deed (doc 1717247010): an instrument of record; the buyer_name field is read off the recorded document. |
| O2 `obs_o2_assessor_owner` | current_owner ← FIRSTKEY HOMES | `["measured"]` | Assessor roll row: an administrative record of what the roll states — a reading of the record, not an estimate (R1). |
| O3 `obs_o3_crm_disposition` | sslbda_disposition ← conveyed | `["asserted-by-interested-party"]` | SSLBDA's CRM self-reports SSLBDA's own inventory state; SSLBDA is the interested party. TEMPORAL TERM DROPPED per R1's stated condition — see §1a. |
| O4 `obs_o4_ccao_disposition` | sslbda_disposition ← not_conveyed | `["inferred-from-proxy", "measured"]` | The deed row itself is measured (recorded instrument); the not_conveyed claim is INFERRED from grantor identity as proxy (grantor is RICHARD THORTON, not SSLBDA). First real `inferred-from-proxy` encode (closes the CF-020 gate-item gap). The dossier's O4 entry must print BOTH terms with the existing A2 inference sentence as the proxy explanation. |

Sets are STORED sorted lexicographically (order not meaningful per canon; sorting gives
canonical serialization bytes). Hence O4 stores `["inferred-from-proxy", "measured"]`.

### 1a. Why O3 drops `true-as-of-date-decaying` (R1 condition exercised)

R1: type O3 `["asserted-by-interested-party", "true-as-of-date-decaying"]` ONLY if the
schema's temporal form can express "asserted 2017-01-01, staleness unbounded" cleanly;
otherwise drop the temporal term and state why. It cannot be expressed cleanly:
CF-020 carries forward the NORMATIVE rule `validUntil: null` means DOES NOT DECAY — never
"unknown expiry." A decaying claim with unbounded/unknown staleness would need
`validUntil = unknown`, which the schema explicitly forbids reading into null; and
supplying any concrete expiry date would be fabrication (no-fab). Therefore O3 is typed
`["asserted-by-interested-party"]` alone, and NO temporal-validity fields are added to the
RI claim schema in this contract (no claim can honestly carry them under CF-020 semantics).

## 2. Expected effect on the belief state (stated before running)

**Pre-registered hypothesis: typing does NOT change the belief state; it enriches the
JUSTIFICATION only.** The Denœux cautious fusion (`ri_core/reconcile.py::cautious_fuse`,
pointwise min of conjunctive weights) is not modified; masses continue to come solely from
the pre-registered M-RI-11 source-type table (`pilot/mass_assignments.md`). Expected typed
re-run masses — EXACTLY the M-RI-11 baseline:

```
sslbda_disposition:  m(∅)=0.4000  m({not_conveyed})=0.4000  m({conveyed})=0.1000  m(Ω)=0.1000
current_owner:       m(∅)=0.4800  m({CSMA BLT LLC})=0.3200  m({FIRSTKEY HOMES})=0.1200  m(Ω)=0.0800
counterfactual (O3 removed): m({not_conveyed})=0.8000  m(Ω)=0.2000  m(∅)=0.0000
```

What typing adds: the deed's dominance remains, but the CRM's discount becomes EXPLAINABLE
as "interested-party assertion that also self-contradicts the recorded deed" rather than
merely a lower weight; and O1 vs O4 — identical 0.8/0.2 weight — become DISTINGUISHABLE
(`["measured"]` vs `["inferred-from-proxy","measured"]`): the type carries information the
weight provably does not. Any mass differing from the table above = unexpected belief
change, reported as a pre-registration violation (not absorbed, not tuned away).

## 3. The replay invariant (hash discipline)

Mechanism: `uncertaintyType` rides inside the observation `payload` (sibling of
`frame`/`mass`/`trace`), so it is part of the signed bytes and the Merkle log entry.
Justification records emit the field ONLY when the observation payload carries it —
untyped logs must serialize byte-identically to today.

- **FORBIDDEN (logic drift → HALT/FAIL):** any byte change to ANY pre-existing golden
  (`tests/golden/**`, incl. `dolton_dossier.out`), regardless of cause (ruling R2); any
  failure of the existing test suite; any change to `encode(...)` bytes of an UNTYPED
  observation, belief, or belief state.
- **EXPECTED (schema change → allowed):** the TYPED run's Merkle root differs from the
  M-RI-11 run's root (typed payloads are new signed bytes — a new log, not a drifted one).
  The typed run gets its OWN script (`pilot/dolton_dossier_typed.py`) and its OWN NEW
  golden (`tests/golden/pilot/dolton_dossier_typed.out`); `dolton_dossier.out` is the
  M-RI-11 artifact and is untouched (R2).
- **MUST HOLD within the typed run:** replay of the typed log is byte-identical —
  `encode(belief_state) == encode(replay(log_export, ...))` — and the typed dossier is
  byte-stable across processes (PYTHONHASHSEED variation), same discipline as M-RI-11.

Hashes to report at verdict: sha256 of `dolton_dossier.out` before/after (must equal
`6ece101e...93a2` both times), sha256 of the new typed golden, both Merkle roots.

## 4. The falsifier (what would mean the integration made things worse or broke replay)

1. Any pre-existing golden's bytes change, or any existing test fails → logic drift →
   **FAIL**, halt, do not tune.
2. Typed-run masses differ from the §2 table → typing changed belief unjustifiedly →
   **FAIL** against pre-registration.
3. Typed-log replay is not byte-identical, or cross-process bytes differ → replay broken →
   **FAIL**.
4. **Decoration check (Gate-2 risk):** if the typed justification conveys nothing beyond
   the weights — i.e. types collapse to a relabeling of the 0.8/0.6/0.5 weight tiers with
   no distinction the weight didn't already make — the verdict is TYPING-IS-DECORATION
   (a real, reportable FAIL of the stack's value claim). Concrete discriminator,
   fixed now: O1 and O4 share weight 0.8/0.2 but carry DIFFERENT type sets, and O3's
   discount is explained by interested-party status + self-contradiction rather than by
   its 0.5 weight alone. If the built artifact cannot honestly print that distinction,
   decoration is the verdict.
