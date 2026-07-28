#!/usr/bin/env python3
"""EP-typed title-belief dossier: PIN 29-02-408-053-0000 (M-RI-13).

Re-runs the M-RI-11 Dolton dossier with EP set-valued uncertaintyType
(capability-factory canon CF-020) attached to every claim, per the type
map frozen in pilot/ep_typing_preregistration.md BEFORE this file
existed.  Deterministic: reads only snapshot bytes; no network, no wall
clock.

Pre-registered expectations this script asserts (ep_typing_preregistration.md):
  - Belief state IDENTICAL to the M-RI-11 baseline (typing enriches the
    justification only):
      sslbda_disposition: m(emptyset)=0.4000, m({not_conveyed})=0.4000,
                          m({conveyed})=0.1000, m(Omega)=0.1000
      current_owner:      m(emptyset)=0.4800, m({CSMA BLT LLC})=0.3200,
                          m({FIRSTKEY HOMES})=0.1200, m(Omega)=0.0800
      counterfactual (remove O3): m({not_conveyed})=0.8000, m(Omega)=0.2000
  - Typed-log replay byte-identical (encode(belief_state) == encode(replay)).
  - The typed log's Merkle root DIFFERS from M-RI-11's (typed payloads are
    new signed bytes) — pre-registered SCHEMA change, not drift.  Proof:
    an untyped rebuild of the same observations reproduces the frozen
    M-RI-11 root exactly, and its belief bytes equal the typed run's.
  - The justification records carry the pre-registered type sets (the type
    flows through ri_core project(), not through this script's printing).
"""

import decimal
import sys
from decimal import Decimal

from dolton_dossier import (
    _AS_OF,
    belief_to_masses,
    fmt,
    load_snapshot,
    make_obs,
    pct,
    print_masses,
    resolve,
)
from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.provenance import ProvenanceGraph
from ri_core.rules import RuleStore
from ri_core.project import submit, project
from ri_core.replay import counterfactual, export_log, replay
from ri_core.serialization import encode

# Frozen M-RI-11 Merkle root (tests/golden/pilot/dolton_dossier.out, line
# "Merkle root:", golden sha256 6ece101e...93a2).  The untyped rebuild
# below must reproduce it exactly or this script halts.
_M_RI_11_ROOT = "68b45d8b431f84a3fddf8a9ff0dbe0f9a20de75ce537d1161ea19a8fa22a39fa"

# Pre-registered type map (ep_typing_preregistration.md section 1, GO
# ruling R1).  Sets stored sorted (order not meaningful per CF-020;
# sorting gives canonical bytes).
_TYPE_MAP = {
    "obs_o1_ccao_owner": ["measured"],
    "obs_o2_assessor_owner": ["measured"],
    "obs_o3_crm_disposition": ["asserted-by-interested-party"],
    "obs_o4_ccao_disposition": ["inferred-from-proxy", "measured"],
}


def make_typed_obs(obs_id, source_id, proposition, frame, mass, ltime,
                   trace, authority):
    """make_obs with the pre-registered uncertaintyType in the payload."""
    unsigned = {
        "kind": "observation",
        "id": obs_id,
        "source_id": source_id,
        "proposition": proposition,
        "payload": {
            "frame": sorted(frame),
            "mass": mass,
            "uncertaintyType": _TYPE_MAP[obs_id],
            "trace": trace,
        },
        "ltime": ltime,
    }
    ub = encode(unsigned)
    identity = Identity(
        identity_id=source_id,
        anchor_id=authority.anchor_id,
        name=source_id,
    )
    sig = authority.sign(identity, ub)
    obs = dict(unsigned)
    obs["sig"] = sig
    return obs


def build_authority():
    """The M-RI-11 authority: same seed, same identities, same linkage."""
    auth = LocalAuthority(anchor_id="pilot", seed=b"m-ri-11-dolton-pilot")
    for src in ("ccao_parcel_sales", "cc_assessor", "tax_agency",
                "sslbda_crm"):
        auth.issue_identity(src)
    id_ccao = Identity(identity_id="ccao_parcel_sales", anchor_id="pilot",
                       name="ccao_parcel_sales")
    id_assessor = Identity(identity_id="cc_assessor", anchor_id="pilot",
                           name="cc_assessor")
    auth.link_identities(id_ccao, id_assessor)
    return auth


def extract_observation_values():
    """Extract O1-O4 payload values from the frozen snapshots (I6), with
    the same field-level asserts as the M-RI-11 dossier."""
    snap_ccao = load_snapshot("ccao_parcel_sales.json")
    snap_assessor = load_snapshot("cc_assessor.json")
    snap_crm = load_snapshot("crm_extract.json")

    ccao_rows = sorted(snap_ccao["records"],
                       key=lambda r: (r["sale_date"], r["row_id"]))
    assessor_rows = sorted(snap_assessor["records"],
                           key=lambda r: int(float(r["year"])))
    crm_props = snap_crm["records"][0]["properties"]

    latest_sale = ccao_rows[-1]
    assert latest_sale["row_id"] == "97219177"
    o1_raw = latest_sale["buyer_name"]
    o1_entity = resolve(o1_raw)
    o4_grantor_raw = latest_sale["seller_name"]
    assert resolve(o4_grantor_raw) != "SSLBDA"

    latest_roll = assessor_rows[-1]
    assert latest_roll["row_id"] == "290240805300002026"
    o2_raw = latest_roll["owner_address_name"]
    o2_entity = resolve(o2_raw)

    assert crm_props["USER_disp_status"] == "Sold"
    assert crm_props["USER_date_disposed"] == "2017-01-01"
    assert crm_props["USER_applicant_purchaser"] is None

    owner_frame = sorted({o1_entity, o2_entity})
    assert owner_frame == ["CSMA BLT LLC", "FIRSTKEY HOMES"]

    return {
        "o1_raw": o1_raw, "o1_entity": o1_entity,
        "o2_raw": o2_raw, "o2_entity": o2_entity,
        "o4_grantor_raw": o4_grantor_raw,
        "owner_frame": owner_frame,
        "latest_sale": latest_sale,
        "crm_props": crm_props,
    }


def build_observations(vals, auth, maker):
    """Build O1-O4 via *maker* (make_obs = untyped M-RI-11 encoding,
    make_typed_obs = M-RI-13 typed encoding).  Values, masses, ltimes,
    and traces are byte-for-byte the M-RI-11 ones."""
    owner_frame = vals["owner_frame"]
    owner_omega = ",".join(owner_frame)
    disp_frame = ["conveyed", "not_conveyed"]
    disp_omega = ",".join(disp_frame)
    latest_sale = vals["latest_sale"]
    crm_props = vals["crm_props"]

    return [
        maker("obs_o1_ccao_owner", "ccao_parcel_sales", "current_owner",
              owner_frame,
              {vals["o1_entity"]: Decimal("0.8"),
               owner_omega: Decimal("0.2")},
              26,
              {"file": "ccao_parcel_sales.json", "row_id": "97219177",
               "field": "buyer_name", "raw": vals["o1_raw"],
               "doc_no": latest_sale["doc_no"],
               "sale_date": latest_sale["sale_date"]},
              auth),
        maker("obs_o2_assessor_owner", "cc_assessor", "current_owner",
              owner_frame,
              {vals["o2_entity"]: Decimal("0.6"),
               owner_omega: Decimal("0.4")},
              35,
              {"file": "cc_assessor.json",
               "row_id": "290240805300002026",
               "field": "owner_address_name", "raw": vals["o2_raw"]},
              auth),
        maker("obs_o3_crm_disposition", "sslbda_crm", "sslbda_disposition",
              disp_frame,
              {"conveyed": Decimal("0.5"), disp_omega: Decimal("0.5")},
              25,
              {"file": "crm_extract.json", "feature_id": "258",
               "fields": "USER_disp_status, USER_date_disposed",
               "raw": crm_props["USER_disp_status"] + " "
                      + crm_props["USER_date_disposed"]},
              auth),
        maker("obs_o4_ccao_disposition", "ccao_parcel_sales",
              "sslbda_disposition",
              disp_frame,
              {"not_conveyed": Decimal("0.8"), disp_omega: Decimal("0.2")},
              26,
              {"file": "ccao_parcel_sales.json", "row_id": "97219177",
               "fields": "seller_name, doc_no, sale_date",
               "raw": vals["o4_grantor_raw"],
               "inference": "The recorded conveyance at the window the CRM"
                            " claims SSLBDA disposed (doc 1717247010,"
                            " 2017-06-16) names grantor RICHARD THORTON,"
                            " not SSLBDA; this is read as evidence SSLBDA"
                            " did not convey the parcel."},
              auth),
    ]


def run_pipeline(vals, maker):
    """Authority + log + rule + observations -> (belief_state, log,
    log_indices, auth)."""
    auth = build_authority()
    log = EvidenceLog()
    graph = ProvenanceGraph()
    rule_store = RuleStore()

    vintage_rule = rule_store.register(
        rule_id="vintage_check",
        version=1,
        fn_spec=["ge", ["field", "ltime"], ["const", 1]],
        ltime=0,
    )
    log.append(vintage_rule)

    rule_bindings = {
        "current_owner": ("vintage_check", 1),
        "sslbda_disposition": ("vintage_check", 1),
    }

    observations = build_observations(vals, auth, maker)
    log_indices = {}
    for obs in observations:
        idx, _ = submit(obs, log, graph, auth)
        log_indices[obs["id"]] = idx

    belief_state = project(log, graph, auth, rule_store, rule_bindings,
                           as_of=_AS_OF)
    return belief_state, log, log_indices, auth, rule_bindings, observations


def justification_types(belief_state):
    """Read back obs_id -> uncertaintyType from the ri_core justification
    records (proof the type flows through project(), not this script)."""
    out = {}
    for prop in belief_state["propositions"].values():
        for cls in prop["justification"]["classes"]:
            for rec in cls["observations"]:
                if "uncertaintyType" in rec:
                    obs_id = rec["entity_id"].removeprefix("obs:")
                    out[obs_id] = rec["uncertaintyType"]
    return out


def type_label(terms):
    return "[" + ", ".join(terms) + "]"


def main():
    sys.stdout.reconfigure(newline="\n")

    vals = extract_observation_values()

    # Typed pipeline (M-RI-13) and untyped rebuild (M-RI-11 encoding).
    (typed_state, typed_log, typed_indices, typed_auth,
     rule_bindings, typed_obs) = run_pipeline(vals, make_typed_obs)
    (untyped_state, untyped_log, _ui, _ua, _ub,
     _uo) = run_pipeline(vals, make_obs)

    typed_masses = {
        p: belief_to_masses(typed_state["propositions"][p]["belief"])
        for p in sorted(typed_state["propositions"])
    }

    print("=" * 70)
    print("EP-TYPED TITLE-BELIEF DOSSIER -- REAL PUBLIC RECORDS (M-RI-13)")
    print("Parcel: PIN 29-02-408-053-0000")
    print("14347 Woodlawn Ave, Dolton, IL 60419 (Cook County)")
    print("=" * 70)
    print()
    print("Informational analysis of public records for demonstration")
    print("purposes. NOT a title opinion, title insurance commitment, or")
    print("legal advice. Records as retrieved on dates listed in MANIFEST.")
    print()
    print("M-RI-11 dossier re-run with EP set-valued uncertaintyType")
    print("(capability-factory canon CF-020) attached to every claim.")
    print("Type map frozen in pilot/ep_typing_preregistration.md BEFORE")
    print("the typed pipeline existed. Closed five-term vocabulary:")
    print("  measured - estimated - asserted-by-interested-party -")
    print("  inferred-from-proxy - true-as-of-date-decaying")
    print("Sets are 1+ terms; matching is membership, never string form.")
    print()

    # ── Section 1: typed evidence intake ──────────────────────────────
    print("-" * 70)
    print("SECTION 1: TYPED EVIDENCE INTAKE")
    print("-" * 70)
    print()
    for obs in typed_obs:
        t = obs["payload"]["trace"]
        mass = obs["payload"]["mass"]
        omega_key = ",".join(sorted(obs["payload"]["frame"]))
        focal = [(k, v) for k, v in sorted(mass.items()) if k != omega_key]
        claim = f"{focal[0][0]} (m={focal[0][1]}, Omega={mass[omega_key]})"
        print(f"  {obs['id']}  [{obs['source_id']}, ltime {obs['ltime']}]")
        print(f"    {obs['proposition']} <- {claim}")
        print(f"    uncertaintyType: "
              f"{type_label(obs['payload']['uncertaintyType'])}")
        src_ref = t.get("row_id") or t.get("feature_id")
        fields = t.get("field") or t.get("fields")
        print(f"    from {t['file']} record {src_ref}, field(s): {fields}")
        print(f"    raw value: {t['raw']!r}")
        if "inference" in t:
            print(f"    PROXY EXPLANATION (A2 inference): {t['inference']}")
        print()

    # ── Section 2: type assignment rationale (pre-registered) ─────────
    print("-" * 70)
    print("SECTION 2: TYPE ASSIGNMENT RATIONALE (PRE-REGISTERED)")
    print("-" * 70)
    print()
    print("  O1 [measured]: recorded deed (doc 1717247010) -- the")
    print("     buyer_name field is read off an instrument of record.")
    print("  O2 [measured]: assessor roll row -- an administrative record")
    print("     of what the roll states, not an estimate (GO ruling R1).")
    print("  O3 [asserted-by-interested-party]: SSLBDA's CRM self-reports")
    print("     SSLBDA's own inventory state; SSLBDA is the interested")
    print("     party. Temporal term true-as-of-date-decaying DROPPED per")
    print("     pre-registration 1a: CF-020's validUntil:null normatively")
    print("     means DOES-NOT-DECAY, so 'asserted 2017-01-01, staleness")
    print("     unbounded' is inexpressible without fabricating an expiry")
    print("     (no-fab).")
    print("  O4 [inferred-from-proxy, measured]: the deed row is measured")
    print("     (recorded instrument); the not_conveyed claim is INFERRED")
    print("     from grantor identity as proxy (grantor is RICHARD")
    print("     THORTON, not SSLBDA). Dual-typed -- the set is the point.")
    print("     First real inferred-from-proxy encode in the EP canon.")
    print()

    # ── Section 3: fused belief (must equal the M-RI-11 baseline) ─────
    print("-" * 70)
    print("SECTION 3: FUSED BELIEF (TYPED PIPELINE)")
    print("-" * 70)
    print()
    print("Masses come solely from the M-RI-11 pre-registered source-type")
    print("table (pilot/mass_assignments.md); the type NEVER changes the")
    print("fusion math (Denoeux cautious rule, pointwise min, untouched).")
    print()
    for prop_name in sorted(typed_state["propositions"]):
        print(f"  Proposition: {prop_name}")
        print_masses(typed_masses[prop_name])
        print()

    # Pre-registered baseline asserts (ep_typing_preregistration.md 2).
    disp = typed_masses["sslbda_disposition"]
    assert fmt(disp[frozenset()]) == "0.4000"
    assert fmt(disp[frozenset({"not_conveyed"})]) == "0.4000"
    assert fmt(disp[frozenset({"conveyed"})]) == "0.1000"
    assert fmt(disp[frozenset({"conveyed", "not_conveyed"})]) == "0.1000"
    owner = typed_masses["current_owner"]
    assert fmt(owner[frozenset()]) == "0.4800"
    assert fmt(owner[frozenset({"CSMA BLT LLC"})]) == "0.3200"
    assert fmt(owner[frozenset({"FIRSTKEY HOMES"})]) == "0.1200"
    assert fmt(owner[frozenset(vals["owner_frame"])]) == "0.0800"

    # Belief bytes typed vs untyped: must be IDENTICAL per proposition.
    for prop_name in sorted(typed_state["propositions"]):
        tb = typed_state["propositions"][prop_name]["belief"]
        ub = untyped_state["propositions"][prop_name]["belief"]
        assert encode(tb) == encode(ub), (
            f"belief bytes differ for {prop_name} -- typing changed the "
            "belief state (pre-registration violation)")
    print("  Belief bytes, typed vs untyped pipeline: IDENTICAL per")
    print("  proposition -- typing enriched the justification only, as")
    print("  pre-registered.")
    print()

    # ── Section 4: epistemic justification ────────────────────────────
    print("-" * 70)
    print("SECTION 4: EPISTEMIC JUSTIFICATION")
    print("-" * 70)
    print()
    print("Types below are read back from the ri_core justification")
    print("records (project() step 2g), not from this script's inputs --")
    print("the type flows through the reconciliation layer.")
    print()

    jt = justification_types(typed_state)
    assert jt == _TYPE_MAP, (
        f"justification type sets {jt} != pre-registered map {_TYPE_MAP}")

    print("  Proposition: current_owner")
    print(f"    obs_o1_ccao_owner    {type_label(jt['obs_o1_ccao_owner'])}")
    print("      Trusted as a MEASURED record: grantee read off recorded")
    print("      deed doc 1717247010; carries the deed-tier weight (0.8).")
    print(f"    obs_o2_assessor_owner"
          f" {type_label(jt['obs_o2_assessor_owner'])}")
    print("      A MEASURED administrative record of the roll's stated")
    print("      taxpayer name; carries the roll-tier weight (0.6).")
    print(f"    The {pct(owner[frozenset()])} conflict is")
    print("    measured-vs-measured: two authentic records disagree, so")
    print("    the conflict is a records problem (REQUIRES VERIFICATION),")
    print("    not an artifact of a weak epistemic type on either side.")
    print()
    print("  Proposition: sslbda_disposition")
    print(f"    obs_o3_crm_disposition"
          f" {type_label(jt['obs_o3_crm_disposition'])}")
    print("      DISCOUNTED as an interested-party assertion: SSLBDA")
    print("      self-reports its own inventory state ('Sold',")
    print("      2017-01-01) -- and the assertion also SELF-CONTRADICTS")
    print("      the recorded deed record (doc 1717247010 names grantor")
    print("      RICHARD THORTON, not SSLBDA). The 0.5 weight is now")
    print("      EXPLAINED by the type, not merely assigned.")
    print(f"    obs_o4_ccao_disposition"
          f" {type_label(jt['obs_o4_ccao_disposition'])}")
    print("      MEASURED deed row; the not_conveyed reading is INFERRED")
    print("      from grantor identity as proxy (see Section 1 PROXY")
    print("      EXPLANATION). The set carries both natures honestly.")
    print()
    print("  Why the type does work the weight cannot (decoration check,")
    print("  pre-registered discriminator):")
    print("    O1 and O4 carry the SAME weight (0.8 focal / 0.2 Omega)")
    print("    but DIFFERENT type sets -- [measured] vs")
    print("    [inferred-from-proxy, measured]. The weight cannot")
    print("    distinguish a direct reading from a proxy inference; the")
    print("    type can, and a membership query for 'everything")
    print("    inferred-from-proxy' returns exactly O4.")
    print()

    # ── Section 5: counterfactual (typed) ─────────────────────────────
    print("-" * 70)
    print("SECTION 5: COUNTERFACTUAL (TYPED)")
    print("-" * 70)
    print()

    typed_export = export_log(typed_log)
    typed_root = typed_log.root()

    o3_index = typed_indices["obs_o3_crm_disposition"]
    cf_result = counterfactual(
        typed_export, {"remove_entry_indices": [o3_index]},
        typed_auth, rule_bindings, _AS_OF)
    cf_masses = belief_to_masses(
        cf_result["propositions"]["sslbda_disposition"]["belief"])
    assert fmt(cf_masses[frozenset({"not_conveyed"})]) == "0.8000"
    assert fmt(cf_masses[frozenset({"conveyed", "not_conveyed"})]) == "0.2000"
    assert fmt(cf_masses[frozenset()]) == "0.0000"

    print("  Scenario: remove the interested-party assertion (O3) -- what")
    print("  the dossier would say if the CRM entry were corrected.")
    print()
    print("  After (interested-party assertion removed):")
    print_masses(cf_masses, indent="    ")
    print()
    print(f"  Conflict falls from {pct(disp[frozenset()])} to "
          f"{pct(cf_masses[frozenset()])}; belief rests on the")
    print("  measured+inferred-from-proxy deed evidence alone.")
    print()

    # ── Section 6: replay attestation and hash classification ─────────
    print("-" * 70)
    print("SECTION 6: REPLAY ATTESTATION AND HASH CLASSIFICATION")
    print("-" * 70)
    print()

    replay_result = replay(typed_export, typed_auth, rule_bindings,
                           _AS_OF, typed_root)
    replay_ok = encode(typed_state) == encode(replay_result)
    assert replay_ok

    untyped_root = untyped_log.root()
    assert untyped_root.hex() == _M_RI_11_ROOT, (
        f"untyped rebuild root {untyped_root.hex()} != frozen M-RI-11 "
        f"root {_M_RI_11_ROOT} -- LOGIC DRIFT, halt")

    print(f"  Typed log Merkle root:   {typed_root.hex()}")
    print(f"  byte-identical replay (typed log): "
          f"{'OK' if replay_ok else 'FAIL'}")
    print()
    print(f"  Untyped rebuild root:    {untyped_root.hex()}")
    print(f"  Frozen M-RI-11 root:     {_M_RI_11_ROOT}")
    print("  Untyped rebuild == M-RI-11 root: MATCH")
    print()
    print("  Classification (pre-registered, ep_typing_preregistration.md")
    print("  3): the typed root differs from the M-RI-11 root because")
    print("  typed payloads are new signed bytes -- a SCHEMA change, not")
    print("  drift. The untyped path reproduces the M-RI-11 root and")
    print("  belief bytes exactly; the M-RI-11 golden is untouched (R2).")
    print()

    # ── Section 7: verdict inputs (against pre-registration) ──────────
    print("-" * 70)
    print("SECTION 7: VERDICT INPUTS (AGAINST PRE-REGISTRATION)")
    print("-" * 70)
    print()
    print("  Belief-state check: typed masses equal the M-RI-11 baseline")
    print("  exactly (asserted above) -- typing did NOT change belief, as")
    print("  pre-registered.")
    print("  Replay check: typed-log replay byte-identical; root change")
    print("  classified as pre-registered schema change (untyped rebuild")
    print("  reproduces the frozen M-RI-11 root).")
    print("  Decoration check: type sets distinguish O1 from O4 at equal")
    print("  weight, and O3's discount is explained as interested-party +")
    print("  self-contradiction rather than a bare 0.5 -- the type does")
    print("  work the weight alone cannot.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
