#!/usr/bin/env python3
"""Real-parcel title-belief dossier: PIN 29-02-408-053-0000 (M-RI-11).

Builds a title-belief dossier for one real Dolton parcel from frozen
public-record snapshots (pilot/snapshots/), run through ri_core unmodified.
Deterministic: reads only snapshot bytes; no network, no wall clock.

Hand-checked expected values (A3, frozen at observation-mapping approval):
  sslbda_disposition (O3 conveyed 0.5/Omega 0.5; O4 not_conveyed 0.8/Omega 0.2):
    m(emptyset)       = 0.40
    m({not_conveyed}) = 0.40
    m({conveyed})     = 0.10
    m(Omega)          = 0.10
  current_owner (O1 CSMA 0.8/Omega 0.2; O2 FIRSTKEY 0.6/Omega 0.4):
    m(emptyset)          = 0.48
    m({CSMA BLT LLC})    = 0.32
    m({FIRSTKEY HOMES})  = 0.12
    m(Omega)             = 0.08
  Counterfactual (remove O3): m({not_conveyed}) = 0.8, m(Omega) = 0.2

Hand computation (cautious rule = pointwise min of conjunctive weights;
for two disjoint simple support functions this equals the conjunctive rule):
  sslbda_disposition weights: w({conveyed})=0.5 (from O3), w({not_conveyed})=0.2
  (from O4); Q({conveyed})=0.2, Q({not_conveyed})=0.5, Q(Omega)=0.1;
  m(Omega)=0.1, m({conveyed})=0.2-0.1=0.1, m({not_conveyed})=0.5-0.1=0.4,
  m(emptyset)=1-0.2-0.5+0.1=0.4.
  current_owner weights: w({CSMA})=0.2, w({FIRSTKEY})=0.4; Q({CSMA})=0.4,
  Q({FIRSTKEY})=0.2, Q(Omega)=0.08; m(Omega)=0.08, m({CSMA})=0.4-0.08=0.32,
  m({FIRSTKEY})=0.2-0.08=0.12, m(emptyset)=1-0.4-0.2+0.08=0.48.
  Counterfactual: only O4 remains: m({not_conveyed})=0.8, m(Omega)=0.2.
"""

import decimal
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

# Ensure ri_core is importable when run as `python pilot/dolton_dossier.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.provenance import HowProvenance, ProvenanceGraph
from ri_core.reconcile import BeliefWeights
from ri_core.rules import RuleStore
from ri_core.project import submit, project
from ri_core.replay import counterfactual, export_log, replay
from ri_core.serialization import encode

_SNAPDIR = Path(__file__).resolve().parent / "snapshots"
_AS_OF = 100

# ---------------------------------------------------------------------------
# Formatting helpers (M-RI-10 A2 discipline: 4-place Decimals, 2-place pct)
# ---------------------------------------------------------------------------

_CTX = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN)


def fmt(d):
    """Format Decimal to 4 decimal places under pinned context."""
    with decimal.localcontext(_CTX):
        return str(d.quantize(Decimal("0.0001")))


def pct(d):
    """Format Decimal as percentage with 2 decimal places."""
    with decimal.localcontext(_CTX):
        return str((d * 100).quantize(Decimal("0.01"))) + "%"


def subset_label(s):
    """Human-readable label for a frozenset subset."""
    if not s:
        return "emptyset"
    return "{" + ",".join(sorted(s)) + "}"


# ---------------------------------------------------------------------------
# Snapshot access — the dossier reads ONLY these bytes (I6)
# ---------------------------------------------------------------------------

def load_snapshot(name):
    """Load a frozen snapshot from pilot/snapshots/ by file name."""
    with open(_SNAPDIR / name, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Normalization and attested alias resolution (MANIFEST alias table, R1)
# ---------------------------------------------------------------------------

def normalize(raw):
    """Uppercase; '&' -> ' AND '; strip punctuation; collapse whitespace."""
    s = raw.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r" +", " ", s).strip()


# Attested alias table (pilot/MANIFEST.md, ruling R1): normalized raw string
# -> frame-entity label (normalized form of the attested entity name).
# "UNKNOWN" is intentionally absent: not an owner-designating string (R1).
_ALIAS = {
    "BURTON LATANYA": "LATANYA BURTON",
    "SMITH REGINALD": "REGINALD SMITH",
    "REGINALD SMITH": "REGINALD SMITH",
    "US BANK TR": "US BANK TRUSTEE",
    "STANDARD B AND T T": "STANDARD BANK AND TRUST TRUST 15043",
    "STANDARD B AND T CO TR 0000000015043": "STANDARD BANK AND TRUST TRUST 15043",
    "STD BK TR 15043": "STANDARD BANK AND TRUST TRUST 15043",
    "TRUSSELL CELESTINE": "CELESTINE TRUSSELL",
    "CELESTINE TRUSSELL": "CELESTINE TRUSSELL",
    "ROBERT STOKES": "ROBERT STOKES",
    "LAWANDA TRUSSELL": "LAWANDA TRUSSELL",
    "CSMA BLT LLC": "CSMA BLT LLC",
    "RICHARD THORTON": "RICHARD THORTON",
    "FIRST KEY HOMES": "FIRSTKEY HOMES",
    "FIRSTKEY HOMES": "FIRSTKEY HOMES",
}

# The 17 attested raw strings (verbatim) from the MANIFEST alias table.
# The snapshot-derived inventory MUST equal this set, or the dossier halts.
_ATTESTED_RAW = {
    "BURTON LATANYA", "SMITH REGINALD", "US BANK TR", "STANDARD B&T T",
    "STANDARD B&T CO TR 0000000015043", "TRUSSELL CELESTINE", "UNKNOWN",
    "RICHARD  THORTON", "CSMA BLT, LLC", "ROBERT STOKES", "REGINALD SMITH",
    "STD BK TR 15043", "CELESTINE TRUSSELL", "LAWANDA TRUSSELL",
    "CSMA BLT LLC", "FIRST KEY HOMES", "FIRSTKEY HOMES",
}


def resolve(raw):
    """Raw owner-designating string -> attested frame-entity label, or None
    for strings the operator ruled non-owner-designating (R1: UNKNOWN)."""
    n = normalize(raw)
    if n == "UNKNOWN":
        return None
    if n not in _ALIAS:
        raise SystemExit(
            f"Unattested owner-designating string {raw!r} (normalized {n!r}) "
            "- halt: alias table must be re-attested (no-fab)")
    return _ALIAS[n]


# ---------------------------------------------------------------------------
# Observation builder (M-RI-10 pattern, public ri_core APIs only)
# ---------------------------------------------------------------------------

def make_obs(obs_id, source_id, proposition, frame, mass, ltime, trace, authority):
    """Build a signed observation whose payload carries its snapshot trace."""
    unsigned = {
        "kind": "observation",
        "id": obs_id,
        "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": sorted(frame), "mass": mass, "trace": trace},
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


def belief_to_masses(belief_dict):
    """Reconstruct BeliefWeights from a belief dict and return mass dict."""
    frame = frozenset(belief_dict["frame"])
    weights = {}
    for k, v in belief_dict["weights"].items():
        subset = frozenset(k.split(",")) if k else frozenset()
        weights[subset] = v
    bw = BeliefWeights.from_weights(frame, weights)
    return bw.to_mass_dict()


def print_masses(mass_dict, indent="    "):
    """Print nonzero masses in canonical subset order."""
    for subset in sorted(mass_dict.keys(),
                         key=lambda s: (len(s), tuple(sorted(s)))):
        if mass_dict[subset] == 0 and subset:
            continue
        label = f"m({subset_label(subset)})"
        val = fmt(mass_dict[subset])
        conflict = " [CONFLICT]" if not subset and mass_dict[subset] > 0 else ""
        print(f"{indent}{label:<40} = {val}{conflict}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # M-RI-10 A3: LF line endings on all platforms
    sys.stdout.reconfigure(newline="\n")

    # ── Load frozen snapshots (the only inputs) ───────────────────────
    snap_ccao = load_snapshot("ccao_parcel_sales.json")
    snap_assessor = load_snapshot("cc_assessor.json")
    snap_crm = load_snapshot("crm_extract.json")
    snap_tax = load_snapshot("tax_agency.json")
    snap_tax_scav = load_snapshot("tax_agency_scavenger.json")

    ccao_rows = sorted(snap_ccao["records"],
                       key=lambda r: (r["sale_date"], r["row_id"]))
    assessor_rows = sorted(snap_assessor["records"],
                           key=lambda r: int(float(r["year"])))
    crm_feature = snap_crm["records"][0]
    crm_props = crm_feature["properties"]

    assert len(snap_tax["records"]) == 0
    assert len(snap_tax_scav["records"]) == 0

    # ── Raw owner-designating string inventory (verbatim, from bytes) ─
    raw_inventory = {}  # raw string -> list of (source, field, record id)
    for r in ccao_rows:
        for field in ("seller_name", "buyer_name"):
            if field in r and r[field] is not None:
                raw_inventory.setdefault(r[field], []).append(
                    ("ccao_parcel_sales", field, r["row_id"]))
    for r in assessor_rows:
        for field in ("owner_address_name", "mail_address_name"):
            if field in r and r[field] is not None:
                raw_inventory.setdefault(r[field], []).append(
                    ("cc_assessor", field, r["row_id"]))

    if set(raw_inventory) != _ATTESTED_RAW:
        raise SystemExit(
            "Owner-designating string inventory does not match the attested "
            f"alias table: unexpected {sorted(set(raw_inventory) - _ATTESTED_RAW)}, "
            f"missing {sorted(_ATTESTED_RAW - set(raw_inventory))}")

    entities = sorted({e for e in (resolve(s) for s in raw_inventory)
                       if e is not None})
    assert len(entities) == 10, f"Expected 10 alias-resolved entities, got {len(entities)}"

    # ── Extract observation values from named snapshot fields (I6) ────
    # Latest CCAO sale row (max sale_date; unique in this data).
    latest_sale = ccao_rows[-1]
    assert latest_sale["row_id"] == "97219177"
    o1_raw = latest_sale["buyer_name"]           # "CSMA BLT, LLC"
    o1_entity = resolve(o1_raw)                  # CSMA BLT LLC
    o4_grantor_raw = latest_sale["seller_name"]  # "RICHARD  THORTON"
    o4_grantor = resolve(o4_grantor_raw)         # RICHARD THORTON
    assert o4_grantor != "SSLBDA"

    # Latest assessor roll row (max assessment year).
    latest_roll = assessor_rows[-1]
    assert latest_roll["row_id"] == "290240805300002026"
    o2_raw = latest_roll["owner_address_name"]   # "FIRST KEY HOMES"
    o2_entity = resolve(o2_raw)                  # FIRSTKEY HOMES

    # CRM disposition claim.
    assert crm_props["USER_disp_status"] == "Sold"
    assert crm_props["USER_date_disposed"] == "2017-01-01"
    assert crm_props["USER_applicant_purchaser"] is None  # no owner claim (I6)

    # current_owner frame: per-source latest owner-designating values,
    # alias-resolved (Plan Gate (e); ruling R6).
    owner_frame = sorted({o1_entity, o2_entity})
    assert owner_frame == ["CSMA BLT LLC", "FIRSTKEY HOMES"]
    owner_omega = ",".join(owner_frame)

    disp_frame = ["conveyed", "not_conveyed"]
    disp_omega = ",".join(disp_frame)

    # ── Authority, identities, linkage ────────────────────────────────
    auth = LocalAuthority(anchor_id="pilot", seed=b"m-ri-11-dolton-pilot")
    for src in ("ccao_parcel_sales", "cc_assessor", "tax_agency", "sslbda_crm"):
        auth.issue_identity(src)

    id_ccao = Identity(identity_id="ccao_parcel_sales", anchor_id="pilot",
                       name="ccao_parcel_sales")
    id_assessor = Identity(identity_id="cc_assessor", anchor_id="pilot",
                           name="cc_assessor")
    auth.link_identities(id_ccao, id_assessor)

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

    # ── Observations O1-O4 ────────────────────────────────────────────
    # Masses: pre-registered source-type table, pilot/mass_assignments.md
    # (frozen at Plan Gate approval). ltimes: MANIFEST ltime mapping (A2, R2).
    observations = [
        make_obs("obs_o1_ccao_owner", "ccao_parcel_sales", "current_owner",
                 owner_frame,
                 {o1_entity: Decimal("0.8"), owner_omega: Decimal("0.2")},
                 26,
                 {"file": "ccao_parcel_sales.json", "row_id": "97219177",
                  "field": "buyer_name", "raw": o1_raw,
                  "doc_no": latest_sale["doc_no"],
                  "sale_date": latest_sale["sale_date"]},
                 auth),
        make_obs("obs_o2_assessor_owner", "cc_assessor", "current_owner",
                 owner_frame,
                 {o2_entity: Decimal("0.6"), owner_omega: Decimal("0.4")},
                 35,
                 {"file": "cc_assessor.json", "row_id": "290240805300002026",
                  "field": "owner_address_name", "raw": o2_raw},
                 auth),
        make_obs("obs_o3_crm_disposition", "sslbda_crm", "sslbda_disposition",
                 disp_frame,
                 {"conveyed": Decimal("0.5"), disp_omega: Decimal("0.5")},
                 25,
                 {"file": "crm_extract.json", "feature_id": "258",
                  "fields": "USER_disp_status, USER_date_disposed",
                  "raw": crm_props["USER_disp_status"] + " "
                         + crm_props["USER_date_disposed"]},
                 auth),
        make_obs("obs_o4_ccao_disposition", "ccao_parcel_sales",
                 "sslbda_disposition",
                 disp_frame,
                 {"not_conveyed": Decimal("0.8"), disp_omega: Decimal("0.2")},
                 26,
                 {"file": "ccao_parcel_sales.json", "row_id": "97219177",
                  "fields": "seller_name, doc_no, sale_date",
                  "raw": o4_grantor_raw,
                  "inference": "The recorded conveyance at the window the CRM"
                               " claims SSLBDA disposed (doc 1717247010,"
                               " 2017-06-16) names grantor RICHARD THORTON,"
                               " not SSLBDA; this is read as evidence SSLBDA"
                               " did not convey the parcel."},
                 auth),
    ]

    log_indices = {}
    for obs in observations:
        idx, _entity_id = submit(obs, log, graph, auth)
        log_indices[obs["id"]] = idx

    belief_state = project(log, graph, auth, rule_store, rule_bindings,
                           as_of=_AS_OF)

    prop_masses = {}
    for prop_name in sorted(belief_state["propositions"]):
        belief = belief_state["propositions"][prop_name].get("belief")
        if belief is not None:
            prop_masses[prop_name] = belief_to_masses(belief)

    # ==================================================================
    # PRINTED DOSSIER
    # ==================================================================

    print("=" * 70)
    print("TITLE-BELIEF DOSSIER -- REAL PUBLIC RECORDS")
    print("Parcel: PIN 29-02-408-053-0000")
    print("14347 Woodlawn Ave, Dolton, IL 60419 (Cook County)")
    print("=" * 70)
    print()
    print("Informational analysis of public records for demonstration")
    print("purposes. NOT a title opinion, title insurance commitment, or")
    print("legal advice. Records as retrieved on dates listed in MANIFEST.")
    print()

    # ── Section 1: Evidence Intake ────────────────────────────────────
    print("-" * 70)
    print("SECTION 1: EVIDENCE INTAKE")
    print("-" * 70)
    print()
    print("Sources (one identity per source; operator-attested extracts):")
    print("  ccao_parcel_sales   Assessor - Parcel Sales (wvhk-k5uv):"
          f" {len(ccao_rows)} sale rows")
    print("  cc_assessor         Assessor - Parcel Addresses (3723-97qp):"
          f" {len(assessor_rows)} roll rows")
    print("  tax_agency          Treasurer tax-sale datasets: 0 rows --")
    print("                      no machine-readable tax record found in the")
    print("                      queried datasets; contributes NO observation")
    print("                      (I6). This does NOT imply the parcel is")
    print("                      tax-clear.")
    print("  sslbda_crm          SSLBDA CRM extract: 1 row (feature 258)")
    print()
    print("Observations (every payload value traces to named snapshot fields):")
    print()
    for obs in observations:
        t = obs["payload"]["trace"]
        mass = obs["payload"]["mass"]
        omega_key = ",".join(sorted(obs["payload"]["frame"]))
        focal = [(k, v) for k, v in sorted(mass.items()) if k != omega_key]
        claim = f"{focal[0][0]} (m={focal[0][1]}, Omega={mass[omega_key]})"
        print(f"  {obs['id']}  [{obs['source_id']}, ltime {obs['ltime']}]")
        print(f"    {obs['proposition']} <- {claim}")
        src_ref = t.get("row_id") or t.get("feature_id")
        fields = t.get("field") or t.get("fields")
        print(f"    from {t['file']} record {src_ref}, field(s): {fields}")
        print(f"    raw value: {t['raw']!r}")
        if "inference" in t:
            print(f"    INFERENCE (printed per amendment A2): {t['inference']}")
        print()
    print(f"Total observations: {len(observations)}"
          " (from 3 real sources with records)")
    print()

    # ── Section 2: Frame construction (alias table, R1/R6) ────────────
    print("-" * 70)
    print("SECTION 2: FRAME CONSTRUCTION")
    print("-" * 70)
    print()
    print("Normalization: uppercase; '&' -> ' AND '; strip punctuation;")
    print("collapse whitespace.")
    print()
    print("Attested alias table (operator: Registry Signal/Irvin, 2026-07-27,")
    print("rulings R1/R6; full table in pilot/MANIFEST.md). Raw strings")
    print("verbatim from snapshot bytes:")
    print()
    for raw in sorted(raw_inventory):
        n = normalize(raw)
        if n == "UNKNOWN":
            ent = "(not owner-designating, R1 -- no observation)"
        else:
            ent = _ALIAS[n]
        refs = raw_inventory[raw]
        ref = f"{refs[0][0]}.{refs[0][1]} x{len(refs)}"
        print(f"  {raw!r:<38} -> {ent}")
        print(f"      [{ref}]")
    print()
    print(f"Alias-resolved entities ({len(entities)}):")
    for e in entities:
        print(f"  - {e}")
    print()
    print("Deed chain (ccao_parcel_sales, chronological):")
    for r in ccao_rows:
        grantor = r.get("seller_name")
        grantee = r.get("buyer_name")
        g1 = (resolve(grantor) or "UNKNOWN (R1: no observation)") \
            if grantor is not None else "(no name field in record)"
        g2 = (resolve(grantee) or "UNKNOWN (R1: no observation)") \
            if grantee is not None else "(no name field in record)"
        print(f"  {r['sale_date'][:10]}  doc {r['doc_no']:<12} "
              f"${r['sale_price']:<9} {g1} -> {g2}")
    print()
    print("Assessment roll (cc_assessor, owner_address_name by year):")
    runs = []
    for r in assessor_rows:
        y = int(float(r["year"]))
        e = resolve(r["owner_address_name"])
        if runs and runs[-1][2] == e and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y, e])
    for y0, y1, e in runs:
        span = f"{y0}-{y1}" if y1 != y0 else f"{y0}"
        print(f"  {span:<11} {e}")
    print()
    print("Frame rule (Plan Gate (e), governs per ruling R6): collect the")
    print("owner-designating field per source (latest CCAO sale buyer_name;")
    print("assessor taxpayer name; CRM grantee/owner if the extract asserts")
    print("one), normalize, and the sorted set of distinct normalized names")
    print("is the frame. The CRM asserts no owner (null purchaser).")
    print()
    print(f"current_owner frame ({len(owner_frame)} entities):"
          f" {', '.join(owner_frame)}")
    print("sslbda_disposition frame (2 elements): conveyed, not_conveyed")
    print()
    print("The chain above has 10 parties; the frame has 2 because only the")
    print("latest per-source assertions claim CURRENT ownership. RICHARD")
    print("THORTON is an attested alias-table entity and chain-of-title")
    print("party, not a frame element: no source asserts him as current")
    print("owner (ruling R6).")
    print()

    # ── Section 3: Verification results ───────────────────────────────
    print("-" * 70)
    print("SECTION 3: VERIFICATION RESULTS")
    print("-" * 70)
    print()
    print("Rule applied: vintage_check v1")
    print("Predicate: ltime >= 1 (record-vintage staleness; ltimes are the")
    print("operator-attested MANIFEST mapping: document/record date order,")
    print("ties by source_id then record id (A2); CRM record date is")
    print("USER_date_disposed per ruling R2)")
    print()
    for prop_name in sorted(belief_state["propositions"]):
        just = belief_state["propositions"][prop_name]["justification"]
        if "rule_applied" not in just:
            continue
        print(f"  Proposition: {prop_name}")
        for v in just["rule_applied"]["verdicts"]:
            status = "PASS" if v["verdict"] else "EXCLUDED"
            print(f"    {v['observation_id']:<28} {status}")
        for ex in just["excluded"]:
            print(f"    >> {ex['entity_id']} excluded by "
                  f"{ex['rule_id']} v{ex['rule_version']} "
                  f"(reason: {ex['reason']})")
        print()

    # ── Section 4: Provenance classes ─────────────────────────────────
    print("-" * 70)
    print("SECTION 4: PROVENANCE CLASSES")
    print("-" * 70)
    print()
    for prop_name in sorted(belief_state["propositions"]):
        just = belief_state["propositions"][prop_name]["justification"]
        classes = just["classes"]
        print(f"  Proposition: {prop_name}")
        print(f"  Independent evidence classes: {len(classes)}")
        for cls in classes:
            members = [o["source_id"] for o in cls["observations"]]
            print(f"    Class [{cls['class_repr']}]: {', '.join(members)}")
        how_poly = HowProvenance.from_canonical(just["how_provenance"])
        print(f"  How-provenance polynomial: {how_poly}")
        print()
    print("  Linkage rationale (printed per amendment A3): sale rows")
    print("  originate from recorded deeds published through the Assessor's")
    print("  pipeline; taxpayer-of-record originates from the assessment")
    print("  roll; linked CONSERVATIVELY because independence is not")
    print("  established -- and by idempotence, linking cannot understate")
    print("  evidence, only prevent overstatement.")
    print()

    # ── Section 5: Fused belief ───────────────────────────────────────
    print("-" * 70)
    print("SECTION 5: FUSED BELIEF")
    print("-" * 70)
    print()
    print("Pre-registered mass table applied verbatim")
    print("(pilot/mass_assignments.md, frozen at Plan Gate):")
    print("  Recorded deed / sale record   0.8 focal / 0.2 Omega")
    print("  Assessor taxpayer-of-record   0.6 focal / 0.4 Omega")
    print("  Tax status record             0.6 focal / 0.4 Omega (unused: no record)")
    print("  CRM entry (SSLBDA)            0.5 focal / 0.5 Omega")
    print()

    for prop_name in sorted(belief_state["propositions"]):
        belief = belief_state["propositions"][prop_name].get("belief")
        print(f"  Proposition: {prop_name}")
        if belief is None:
            print("    No passing evidence; belief cannot be computed.")
            print()
            continue
        masses = prop_masses[prop_name]
        print_masses(masses)
        empty_mass = masses.get(frozenset(), Decimal(0))
        if empty_mass > 0:
            print()
            if prop_name == "current_owner":
                print(f"    Unresolved conflict: {pct(empty_mass)} of belief"
                      " mass. The deed")
                print("    record (grantee CSMA BLT LLC, doc 1717247010) and"
                      " the current")
                print("    assessment roll (FIRSTKEY HOMES) disagree. Field"
                      " semantics")
                print("    (ruling R1, not evidence): the assessor"
                      " mailing-name field can")
                print("    reflect a property manager rather than the title"
                      " holder --")
                print("    this conflict reads as REQUIRES VERIFICATION, not"
                      " as proof of")
                print("    a competing claim.")
            else:
                print(f"    Unresolved conflict: {pct(empty_mass)} of belief"
                      " mass --")
                print("    contradictory records requiring curative work:")
                print("    the SSLBDA CRM row (feature 258: disposition"
                      " 'Sold',")
                print("    date 2017-01-01) conflicts with recorded deed doc")
                print("    1717247010 (2017-06-16, grantor RICHARD THORTON,")
                print("    grantee CSMA BLT LLC -- SSLBDA is not a party).")
                print("    Resolution requires correcting the CRM record or")
                print("    locating a recorded SSLBDA conveyance; none exists")
                print("    in the queried datasets.")
        print()

    # A3 hand-check assertions (frozen at observation-mapping approval)
    disp = prop_masses["sslbda_disposition"]
    assert fmt(disp[frozenset()]) == "0.4000"
    assert fmt(disp[frozenset({"not_conveyed"})]) == "0.4000"
    assert fmt(disp[frozenset({"conveyed"})]) == "0.1000"
    assert fmt(disp[frozenset({"conveyed", "not_conveyed"})]) == "0.1000"

    owner = prop_masses["current_owner"]
    assert fmt(owner[frozenset()]) == "0.4800"
    assert fmt(owner[frozenset({"CSMA BLT LLC"})]) == "0.3200"
    assert fmt(owner[frozenset({"FIRSTKEY HOMES"})]) == "0.1200"
    assert fmt(owner[frozenset(owner_frame)]) == "0.0800"

    # ── Section 6: Sybil / foil (ILLUSTRATION, real linked pair) ──────
    print("-" * 70)
    print("SECTION 6: SHARED-UPSTREAM DEMONSTRATION")
    print("[ILLUSTRATION -- real linked pair: ccao_parcel_sales, cc_assessor]")
    print("-" * 70)
    print()

    log_export = export_log(log)
    merkle_root = log.root()

    result_linked = replay(log_export, auth, rule_bindings, _AS_OF,
                           merkle_root)

    auth_unlinked = LocalAuthority(anchor_id="pilot",
                                   seed=b"m-ri-11-dolton-pilot")
    for src in ("ccao_parcel_sales", "cc_assessor", "tax_agency",
                "sslbda_crm"):
        auth_unlinked.issue_identity(src)
    result_unlinked = replay(log_export, auth_unlinked, rule_bindings,
                             _AS_OF, merkle_root)

    linked_owner_p = result_linked["propositions"]["current_owner"]
    unlinked_owner_p = result_unlinked["propositions"]["current_owner"]
    n_linked = len(linked_owner_p["justification"]["classes"])
    n_unlinked = len(unlinked_owner_p["justification"]["classes"])
    identical = (encode(linked_owner_p["belief"])
                 == encode(unlinked_owner_p["belief"]))
    assert n_linked == 1 and n_unlinked == 2
    assert identical

    print(f"  current_owner, linked (provenance-aware):  {n_linked}"
          " evidence class")
    print(f"  current_owner, unlinked:                   {n_unlinked}"
          " evidence classes")
    print(f"  Fused belief byte-identical:               "
          f"{'YES' if identical else 'NO'}")
    print()
    print("  FOIL (count-based confidence): a naive pipeline would report")
    print("  'ownership confirmed by 2 sources' while both derive from")
    print("  county systems -- and here they DISAGREE, which a count")
    print("  presents as a 50/50 tie. Provenance-aware fusion keeps the")
    print("  frozen per-source-type confidences, makes the conflict")
    print(f"  explicit ({pct(owner[frozenset()])} m(emptyset)), and linking"
          " cannot")
    print("  understate evidence -- only prevent overstatement"
          " (idempotence).")
    print()

    # ── Section 7: Counterfactual ─────────────────────────────────────
    print("-" * 70)
    print("SECTION 7: COUNTERFACTUAL")
    print("-" * 70)
    print()

    o3_index = log_indices["obs_o3_crm_disposition"]
    cf_result = counterfactual(
        log_export, {"remove_entry_indices": [o3_index]},
        auth, rule_bindings, _AS_OF)
    cf_belief = cf_result["propositions"]["sslbda_disposition"].get("belief")
    assert cf_belief is not None
    cf_masses = belief_to_masses(cf_belief)

    assert fmt(cf_masses[frozenset({"not_conveyed"})]) == "0.8000"
    assert fmt(cf_masses[frozenset({"conveyed", "not_conveyed"})]) == "0.2000"
    assert fmt(cf_masses[frozenset()]) == "0.0000"

    print("  Scenario: remove the CRM observation -- this is what the")
    print("  dossier would say if the CRM entry were corrected.")
    print()
    print("  Before (all evidence), sslbda_disposition:")
    print_masses(disp, indent="    ")
    print()
    print("  After (CRM observation removed):")
    print_masses(cf_masses, indent="    ")
    print()
    print(f"  Conflict falls from {pct(disp[frozenset()])} to "
          f"{pct(cf_masses[frozenset()])}; belief rests on the recorded")
    print("  deed alone (not_conveyed 0.8000, remainder uncommitted).")
    print()

    # ── Section 8: Replay attestation ─────────────────────────────────
    print("-" * 70)
    print("SECTION 8: REPLAY ATTESTATION")
    print("-" * 70)
    print()

    replay_result = replay(log_export, auth, rule_bindings, _AS_OF,
                           merkle_root)
    replay_ok = encode(belief_state) == encode(replay_result)
    assert replay_ok

    print(f"  Merkle root: {merkle_root.hex()}")
    print(f"  byte-identical replay: {'OK' if replay_ok else 'FAIL'}")
    print("  This dossier is reproducible from the evidence log alone.")
    print()

    # ── Section 9: Methodology note ───────────────────────────────────
    print("-" * 70)
    print("SECTION 9: METHODOLOGY NOTE")
    print("-" * 70)
    print()
    print("  Attestation: LocalAuthority('pilot') issues one identity per")
    print("  source (ccao_parcel_sales, cc_assessor, tax_agency,")
    print("  sslbda_crm). The operator (Registry Signal) signs on each")
    print("  source's behalf, attesting 'retrieved from this source,")
    print("  unaltered' (public records) / 'extracted from operator's local")
    print("  pilot export, unaltered' (CRM). No county office or SSLBDA")
    print("  signed anything.")
    print()
    print("  Masses: pre-registered per source TYPE in")
    print("  pilot/mass_assignments.md, frozen at the Plan Gate BEFORE any")
    print("  snapshot was fetched. Snapshots determined only WHICH frame")
    print("  element received mass, never how much.")
    print()
    print("  Retrieval: dates, dataset ids, exact queries, and snapshot")
    print("  sha256 hashes are in pilot/MANIFEST.md. The tax source found")
    print("  no machine-readable tax record in the queried datasets; this")
    print("  statement must not be read as implying the parcel is")
    print("  tax-clear (ruling R3: the queried Treasurer dataset is a dead")
    print("  endpoint, content frozen circa 2009-2014).")
    print()
    print("  Narrative (not an observation, per I6 and ruling R4): SSLBDA")
    print("  appears in NO row of any queried public dataset for this")
    print("  parcel -- no deed, no roll year, 1999-2026. The dossier's")
    print("  not_conveyed evidence is the single field-traceable 2017 deed")
    print("  row with its printed inference (Section 1), never")
    print("  dataset-wide absence.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
