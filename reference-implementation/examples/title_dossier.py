#!/usr/bin/env python3
"""Title-Belief Dossier: single-parcel walkthrough.

Builds a complete title-belief dossier for a fictional distressed parcel
(PIN 99-00-000-000-0000) from conflicting public-record evidence,
demonstrating every Reality Infrastructure system capability.

Hand-checked expected values (A4):
  Before (all evidence, owner proposition):
    m(emptyset)            = 0.56
    m({owner_A})           = 0.14
    m({owner_B})           = 0.24
    m({owner_A,owner_B})   = 0.06
  After removing recorder-of-deeds observation:
    m(emptyset)            = 0.42
    m({owner_A})           = 0.28
    m({owner_B})           = 0.18
    m({owner_A,owner_B})   = 0.12
  Linked (4 classes) vs unlinked (5 classes): byte-identical belief.

Hand computation (cautious rule = pointwise min of weights):
  Input weights per observation (mass -> commonality -> weight transform):
    county_assessor  m({A})=0.7,m(O)=0.3 => w(0)=1, w({A})=0.3, w({B})=1.0
    recorder_of_deeds m({B})=0.8,m(O)=0.2 => w(0)=1, w({A})=1.0, w({B})=0.2
    tax_sale         m({B})=0.6,m(O)=0.4 => w(0)=1, w({A})=1.0, w({B})=0.4
    broker_alpha     m({A})=0.5,m(O)=0.5 => w(0)=1, w({A})=0.5, w({B})=1.0
    broker_beta      m({A})=0.5,m(O)=0.5 => w(0)=1, w({A})=0.5, w({B})=1.0
  Fused weights (min): w(0)=1, w({A})=0.3, w({B})=0.2
  Weights -> commonality -> mass:
    Q(0)=1, Q({A})=w(0)*w({B})=0.2, Q({B})=w(0)*w({A})=0.3, Q(O)=0.06
    m(0)=1-0.2-0.3+0.06=0.56, m({A})=0.2-0.06=0.14,
    m({B})=0.3-0.06=0.24, m(O)=0.06
  Counterfactual (remove recorder): min w({B}) becomes 0.4 (from tax_sale)
    Q({A})=0.4, Q({B})=0.3, Q(O)=0.12
    m(0)=1-0.4-0.3+0.12=0.42, m({A})=0.28, m({B})=0.18, m(O)=0.12
"""

import decimal
import os
import sys
from decimal import Decimal

# Ensure ri_core is importable when run as `python examples/title_dossier.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.provenance import HowProvenance, ProvenanceGraph
from ri_core.reconcile import BeliefWeights
from ri_core.rules import RuleStore
from ri_core.project import submit, project
from ri_core.replay import counterfactual, export_log, replay
from ri_core.serialization import encode


# ---------------------------------------------------------------------------
# Formatting helpers (A2: 4-place Decimals, 2-place percentages)
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
# Observation and belief helpers
# ---------------------------------------------------------------------------

def make_obs(obs_id, source_id, proposition, frame, mass, ltime, authority):
    """Build a signed observation dict using only public ri_core APIs."""
    unsigned = {
        "kind": "observation",
        "id": obs_id,
        "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": sorted(frame), "mass": mass},
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
    """Print mass function in canonical subset order."""
    for subset in sorted(mass_dict.keys(),
                         key=lambda s: (len(s), tuple(sorted(s)))):
        label = f"m({subset_label(subset)})"
        val = fmt(mass_dict[subset])
        conflict = " [CONFLICT]" if not subset and mass_dict[subset] > 0 else ""
        print(f"{indent}{label:<30} = {val}{conflict}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # A3: LF line endings on all platforms
    sys.stdout.reconfigure(newline="\n")

    # ── Authority and identity setup ──────────────────────────────────
    auth = LocalAuthority(anchor_id="example", seed=b"dossier-example")
    auth.issue_identity("county_assessor")
    auth.issue_identity("data_broker_alpha")
    auth.issue_identity("data_broker_beta")
    auth.issue_identity("recorder_of_deeds")
    auth.issue_identity("tax_sale_authority")

    # Link the two data brokers (same upstream aggregator = Sybil pair)
    id_dba = Identity(identity_id="data_broker_alpha",
                      anchor_id="example", name="data_broker_alpha")
    id_dbb = Identity(identity_id="data_broker_beta",
                      anchor_id="example", name="data_broker_beta")
    auth.link_identities(id_dba, id_dbb)

    log = EvidenceLog()
    graph = ProvenanceGraph()
    rule_store = RuleStore()

    # ── Register verification rule ────────────────────────────────────
    freshness_rule = rule_store.register(
        rule_id="freshness_check",
        version=1,
        fn_spec=["ge", ["field", "ltime"], ["const", 1]],
        ltime=0,
    )
    log.append(freshness_rule)

    rule_bindings = {
        "owner": ("freshness_check", 1),
        "lien_status": ("freshness_check", 1),
    }

    # ── Build observations ────────────────────────────────────────────
    # Five sources, seven observations across two propositions.
    # Owner proposition: who holds title?
    #   - County assessor tax roll lists owner A (strong, but lags filings)
    #   - Recorder of deeds: 2019 quitclaim deed to owner B (authoritative)
    #   - Tax sale authority: certificate to B after delinquency (strong)
    #   - Data broker alpha: asserts A (raw aggregation, no chain-of-title)
    #   - Data broker beta: asserts A (SAME upstream source as alpha)
    # Lien status proposition: is the parcel encumbered?
    #   - County assessor: 2015 mortgage lien with no release filing
    #   - Data broker beta: asserts lien clear, but data is STALE (ltime=0)
    observations = [
        make_obs("obs_ca_owner", "county_assessor", "owner",
                 ["owner_A", "owner_B"],
                 {"owner_A": Decimal("0.7"),
                  "owner_A,owner_B": Decimal("0.3")}, 1, auth),
        make_obs("obs_rod_owner", "recorder_of_deeds", "owner",
                 ["owner_A", "owner_B"],
                 {"owner_B": Decimal("0.8"),
                  "owner_A,owner_B": Decimal("0.2")}, 2, auth),
        make_obs("obs_ts_owner", "tax_sale_authority", "owner",
                 ["owner_A", "owner_B"],
                 {"owner_B": Decimal("0.6"),
                  "owner_A,owner_B": Decimal("0.4")}, 3, auth),
        make_obs("obs_dba_owner", "data_broker_alpha", "owner",
                 ["owner_A", "owner_B"],
                 {"owner_A": Decimal("0.5"),
                  "owner_A,owner_B": Decimal("0.5")}, 4, auth),
        make_obs("obs_dbb_owner", "data_broker_beta", "owner",
                 ["owner_A", "owner_B"],
                 {"owner_A": Decimal("0.5"),
                  "owner_A,owner_B": Decimal("0.5")}, 5, auth),
        make_obs("obs_ca_lien", "county_assessor", "lien_status",
                 ["lien_clear", "lien_encumbered"],
                 {"lien_encumbered": Decimal("0.6"),
                  "lien_clear,lien_encumbered": Decimal("0.4")}, 6, auth),
        make_obs("obs_dbb_lien", "data_broker_beta", "lien_status",
                 ["lien_clear", "lien_encumbered"],
                 {"lien_clear": Decimal("0.5"),
                  "lien_clear,lien_encumbered": Decimal("0.5")}, 0, auth),
    ]

    log_indices = {}
    for obs in observations:
        idx, _entity_id = submit(obs, log, graph, auth)
        log_indices[obs["id"]] = idx

    # ── Project belief state ──────────────────────────────────────────
    belief_state = project(log, graph, auth, rule_store, rule_bindings,
                           as_of=10)

    # Pre-compute mass dicts for all propositions
    prop_masses = {}
    for prop_name in sorted(belief_state["propositions"]):
        belief = belief_state["propositions"][prop_name].get("belief")
        if belief is not None:
            prop_masses[prop_name] = belief_to_masses(belief)

    # ==================================================================
    # PRINTED DOSSIER
    # ==================================================================

    print("=" * 70)
    print("TITLE-BELIEF DOSSIER")
    print("Parcel: 99-00-000-000-0000 (Example County)")
    print("=" * 70)
    print()
    print("DISCLAIMER: All names, PINs, and records in this dossier are")
    print("fictional. This is a demonstration of the Reality Infrastructure")
    print("system. No real property, person, or transaction is depicted.")
    print()

    # ── Section 1: Evidence Intake ────────────────────────────────────
    print("-" * 70)
    print("SECTION 1: EVIDENCE INTAKE")
    print("-" * 70)
    print()
    print(f"{'Source':<25} {'LTime':>5}  {'Proposition':<15} {'Claim'}")
    print(f"{'-' * 25} {'-' * 5}  {'-' * 15} {'-' * 30}")

    for obs in observations:
        src = obs["source_id"]
        lt = obs["ltime"]
        prop = obs["proposition"]
        mass = obs["payload"]["mass"]
        frame = sorted(obs["payload"]["frame"])
        omega_key = ",".join(frame)
        focal = [(k, v) for k, v in sorted(mass.items()) if k != omega_key]
        claim = f"{focal[0][0]} (m={focal[0][1]})" if focal else "uncertain"
        print(f"{src:<25} {lt:>5}  {prop:<15} {claim}")

    print()
    print(f"Total observations: {len(observations)}")
    print()

    # ── Section 2: Verification Results ───────────────────────────────
    print("-" * 70)
    print("SECTION 2: VERIFICATION RESULTS")
    print("-" * 70)
    print()
    print("Rule applied: freshness_check v1")
    print("Predicate: ltime >= 1")
    print()

    for prop_name in sorted(belief_state["propositions"]):
        just = belief_state["propositions"][prop_name]["justification"]
        if "rule_applied" not in just:
            continue
        verdicts = just["rule_applied"]["verdicts"]
        excluded = just["excluded"]

        print(f"  Proposition: {prop_name}")
        for v in verdicts:
            status = "PASS" if v["verdict"] else "EXCLUDED"
            print(f"    {v['observation_id']:<25} {status}")

        for ex in excluded:
            print(f"    >> {ex['entity_id']} excluded by "
                  f"{ex['rule_id']} v{ex['rule_version']} "
                  f"(reason: {ex['reason']})")
        print()

    # ── Section 3: Provenance Classes ─────────────────────────────────
    print("-" * 70)
    print("SECTION 3: PROVENANCE CLASSES")
    print("-" * 70)
    print()

    for prop_name in sorted(belief_state["propositions"]):
        just = belief_state["propositions"][prop_name]["justification"]
        classes = just["classes"]

        print(f"  Proposition: {prop_name}")

        if not classes:
            print("    (all evidence excluded)")
            print()
            continue

        print(f"  Number of independent evidence classes: {len(classes)}")
        print()

        for cls in classes:
            members = [o["source_id"] for o in cls["observations"]]
            print(f"    Class [{cls['class_repr']}]:")
            print(f"      Members: {', '.join(members)}")
            if len(members) > 1:
                print("      NOTE: These sources share provenance (same upstream")
                print("      data aggregator). The system treats them as a single")
                print("      evidence class -- repetition does not increase")
                print("      confidence.")
            print()

        how_poly = HowProvenance.from_canonical(just["how_provenance"])
        print(f"  How-provenance polynomial: {how_poly}")
        print()

        if prop_name == "owner":
            print(f"  Reading: This belief was derived from {len(classes)}"
                  " independent")
            print("  evidence paths. The two data brokers are jointly"
                  " represented")
            print("  as a single monomial (their product in the polynomial)"
                  " because")
            print("  they share a common upstream data source.")
        elif prop_name == "lien_status":
            print(f"  Reading: This belief was derived from {len(classes)}"
                  " evidence")
            print("  path(s). One source (data_broker_beta) was excluded by"
                  " the")
            print("  freshness rule, leaving only the county assessor's"
                  " record.")
        print()

    # ── Section 4: Fused Belief ───────────────────────────────────────
    print("-" * 70)
    print("SECTION 4: FUSED BELIEF")
    print("-" * 70)
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
            print(f"    Unresolved conflict: {pct(empty_mass)} of belief"
                  " mass")
            print("    represents contradictory evidence requiring curative")
            print("    legal work (e.g., quiet title action) before the")
            print("    parcel can be considered clear.")
        print()

    # ── Section 5: Sybil Demonstration (ILLUSTRATION) ─────────────────
    print("-" * 70)
    print("SECTION 5: SYBIL DEMONSTRATION")
    print("[ILLUSTRATION -- not a system capability]")
    print("-" * 70)
    print()

    # Export log for replay
    log_export = export_log(log)
    merkle_root = log.root()

    # Replay with linked authority (same as projection)
    result_linked = replay(log_export, auth, rule_bindings, 10, merkle_root)

    # Create unlinked authority (same keys, no link_identities)
    auth_unlinked = LocalAuthority(anchor_id="example",
                                   seed=b"dossier-example")
    auth_unlinked.issue_identity("county_assessor")
    auth_unlinked.issue_identity("data_broker_alpha")
    auth_unlinked.issue_identity("data_broker_beta")
    auth_unlinked.issue_identity("recorder_of_deeds")
    auth_unlinked.issue_identity("tax_sale_authority")

    result_unlinked = replay(log_export, auth_unlinked, rule_bindings,
                             10, merkle_root)

    linked_owner = result_linked["propositions"]["owner"]
    unlinked_owner = result_unlinked["propositions"]["owner"]

    linked_classes_n = len(linked_owner["justification"]["classes"])
    unlinked_classes_n = len(unlinked_owner["justification"]["classes"])

    linked_belief_bytes = encode(linked_owner["belief"])
    unlinked_belief_bytes = encode(unlinked_owner["belief"])
    belief_identical = linked_belief_bytes == unlinked_belief_bytes

    # A4: assert class counts and byte-identity
    assert linked_classes_n == 4, (
        f"Expected 4 linked classes, got {linked_classes_n}")
    assert unlinked_classes_n == 5, (
        f"Expected 5 unlinked classes, got {unlinked_classes_n}")
    assert belief_identical, (
        "Linked and unlinked beliefs must be byte-identical")

    print(f"  Linked brokers (provenance-aware):   "
          f"{linked_classes_n} evidence classes")
    print(f"  Unlinked brokers (no provenance):    "
          f"{unlinked_classes_n} evidence classes")
    print(f"  Belief byte-identical:               "
          f"{'YES' if belief_identical else 'NO'}")
    print()

    # Foil: count-based confidence (computed from observation data)
    owner_obs = [o for o in observations if o["proposition"] == "owner"]

    with decimal.localcontext(_CTX):
        # Naive count: every observation is an independent source
        n_for_a = Decimal(sum(
            1 for o in owner_obs
            if o["payload"]["mass"].get("owner_A", Decimal(0)) > 0))
        n_for_b = Decimal(sum(
            1 for o in owner_obs
            if o["payload"]["mass"].get("owner_B", Decimal(0)) > 0))
        f1_naive = n_for_a / (n_for_a + n_for_b)

        # Provenance-aware count: classes, not observations
        source_claim = {}
        for o in owner_obs:
            m = o["payload"]["mass"]
            source_claim[o["source_id"]] = (
                "A" if m.get("owner_A", Decimal(0))
                       > m.get("owner_B", Decimal(0))
                else "B")
        owner_classes = linked_owner["justification"]["classes"]
        n_cls_a = Decimal(sum(
            1 for c in owner_classes
            if source_claim.get(c["class_repr"]) == "A"))
        n_cls_b = Decimal(sum(
            1 for c in owner_classes
            if source_claim.get(c["class_repr"]) == "B"))
        f1_dedup = n_cls_a / (n_cls_a + n_cls_b)

    print("  FOIL (count-based confidence in owner_A):")
    print(f"    Treating brokers as independent:    {pct(f1_naive)}")
    print(f"    After deduplication:                {pct(f1_dedup)}")
    print(f"    Inflation from double-counting:     "
          f"{pct(f1_naive - f1_dedup)}")
    print()

    owner_a_mass = prop_masses["owner"][frozenset({"owner_A"})]
    print(f"  This system's belief in owner_A is {fmt(owner_a_mass)}"
          " regardless")
    print("  of how sources are grouped -- provenance-class partitioning")
    print("  ensures repetition does not increase confidence.")
    print()

    # ── Section 6: Counterfactual ─────────────────────────────────────
    print("-" * 70)
    print("SECTION 6: COUNTERFACTUAL")
    print("-" * 70)
    print()

    rod_index = log_indices["obs_rod_owner"]
    cf_result = counterfactual(
        log_export, {"remove_entry_indices": [rod_index]},
        auth, rule_bindings, 10)

    cf_owner_belief = cf_result["propositions"]["owner"].get("belief")
    assert cf_owner_belief is not None, "Counterfactual must produce a belief"
    cf_masses = belief_to_masses(cf_owner_belief)

    # A4: hand-check assertions (exact values from docstring derivation)
    owner_masses = prop_masses["owner"]
    assert fmt(owner_masses[frozenset()]) == "0.5600"
    assert fmt(owner_masses[frozenset({"owner_A"})]) == "0.1400"
    assert fmt(owner_masses[frozenset({"owner_B"})]) == "0.2400"
    assert fmt(owner_masses[frozenset({"owner_A", "owner_B"})]) == "0.0600"

    assert fmt(cf_masses[frozenset()]) == "0.4200"
    assert fmt(cf_masses[frozenset({"owner_A"})]) == "0.2800"
    assert fmt(cf_masses[frozenset({"owner_B"})]) == "0.1800"
    assert fmt(cf_masses[frozenset({"owner_A", "owner_B"})]) == "0.1200"

    print("  Scenario: Remove the 2019 quitclaim deed"
          " (recorder of deeds, ltime=2)")
    print()
    print("  Before (all evidence):")
    print_masses(owner_masses, indent="    ")
    print()
    print("  After (deed removed):")
    print_masses(cf_masses, indent="    ")
    print()

    before_conflict = owner_masses[frozenset()]
    after_conflict = cf_masses[frozenset()]
    print("  The belief shifts: without the quitclaim deed, owner_A gains")
    print(f"  relative support. Conflict decreases from "
          f"{pct(before_conflict)} to")
    print(f"  {pct(after_conflict)}. This is what the dossier would say if"
          " the")
    print("  deed were successfully challenged.")
    print()

    # ── Section 7: Replay Attestation ─────────────────────────────────
    print("-" * 70)
    print("SECTION 7: REPLAY ATTESTATION")
    print("-" * 70)
    print()

    replay_result = replay(log_export, auth, rule_bindings, 10, merkle_root)
    orig_bytes = encode(belief_state)
    replay_bytes = encode(replay_result)
    replay_ok = orig_bytes == replay_bytes
    assert replay_ok, "Replay must produce byte-identical belief state"

    print(f"  Merkle root: {merkle_root.hex()}")
    print(f"  byte-identical replay: {'OK' if replay_ok else 'FAIL'}")
    print("  This dossier is reproducible from the evidence log alone.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
