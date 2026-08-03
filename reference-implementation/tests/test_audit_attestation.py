"""M-RI-15: attestation events, frozen-surface pins, and delta traceability.

The attested re-run must be the same machine as the baseline plus exactly one
new input (the operator's rulings). These tests pin that property: the frozen
files' hashes, the strict intake (refuses blanks), the round-trip, the overlay
semantics at the rules boundary, determinism, and — the contract's core
assertion — every verdict transition traces to an attestation event.
"""
import hashlib
import json
from pathlib import Path

import pytest

from audit import engine, rules, rerun_attested
from audit.attestation import events as att

AUDIT_DIR = Path(__file__).parent.parent / "audit"


def _yaml_text() -> str:
    return att.DEFAULT_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# intake: strict parse, refuse blanks, round-trip
# --------------------------------------------------------------------------

def test_recorded_attestations_load_and_are_complete():
    events = att.load_events()
    assert len(events) == 13
    assert [e["subject"] for e in events if e["kind"] == "name-variant"] == \
        list(att.EXPECTED_VARIANTS)
    assert sorted(e["subject"] for e in events
                  if e["kind"] == "status-semantics") == \
        list(att.EXPECTED_STATUSES)
    for e in events:
        assert e["attested_by"] == "operator"
        assert e["basis"]
        assert e["date"] == "2026-08-02"


def test_recorded_rulings_are_the_operator_adopted_sheet():
    events = att.load_events()
    assert att.alias_strings(events) == (
        "LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL "
        "AGENCY",
        "SO SUB LAND BANK", "SOUTH SUB LAND BK",
        "SOUTH SUBN LAND BK & DEV AUTH",
        "SO SUB LAND/BK/DEV")  # M-RI-16, §9 amendment A2
    assert att.not_client_strings(events) == (
        "C.C. LAND BANK AUTH. DO NOT USE(NO PINS)",
        "COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY")
    # A7 stays uncertain; every status ruling is uncertain -> no overrides
    assert att.status_overrides(events) == {}
    a7 = [e for e in events if e["subject"] == "SUBURBAN LAND BANK &amp;"]
    assert a7[0]["decision"] == "uncertain"


def test_round_trip():
    events = att.load_events()
    assert att.deserialize(att.serialize(events)) == events


def test_refuses_blank_decision():
    text = _yaml_text().replace('decision: "not-client"',
                                'decision: ""', 1)
    with pytest.raises(att.AttestationError, match="blank decision"):
        att.validate(att.parse(text))


def test_refuses_blank_basis():
    events = att.parse(_yaml_text())
    events[3]["basis"] = ""
    with pytest.raises(att.AttestationError, match="blank basis"):
        att.validate(events)


def test_refuses_unknown_decision_word():
    text = _yaml_text().replace('decision: "client-alias"',
                                'decision: "probably-client"', 1)
    with pytest.raises(att.AttestationError, match="not in"):
        att.validate(att.parse(text))


def test_refuses_inventory_deviation():
    text = _yaml_text().replace("SO SUB LAND BANK", "SO SUB LAND BANC")
    with pytest.raises(att.AttestationError, match="inventory deviates"):
        att.validate(att.parse(text))


def test_refuses_malformed_date():
    text = _yaml_text().replace('date: "2026-08-02"', 'date: "Aug 2 2026"', 1)
    with pytest.raises(att.AttestationError, match="not YYYY-MM-DD"):
        att.validate(att.parse(text))


def test_status_inventory_is_derived_from_frozen_claim_unclear():
    assert att.EXPECTED_STATUSES == tuple(sorted(
        s for s, c in rules.STATUS_CLASS.items() if c == rules.CLAIM_UNCLEAR))


# --------------------------------------------------------------------------
# frozen surfaces: the re-run is the same machine
# --------------------------------------------------------------------------

def test_frozen_surfaces_byte_identical_to_baseline():
    for name, want in sorted(rerun_attested.FROZEN_SHA256.items()):
        got = hashlib.sha256((AUDIT_DIR / name).read_bytes()).hexdigest()
        assert got == want, f"{name} deviates from the frozen baseline"


# --------------------------------------------------------------------------
# overlay semantics at the rules boundary
# --------------------------------------------------------------------------

def test_overlay_exact_string_semantics():
    events = att.load_events()
    cm, nm, sc = rerun_attested.compose_matchers(events)
    # attested alias -> match, near-miss released (normalization-insensitive)
    assert cm("SOUTH SUBN LAND BK & DEV AUTH")
    assert not nm("SOUTH SUBN LAND BK & DEV AUTH")
    # attested not-client -> released from near-miss, still never a match
    assert not cm("COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY")
    assert not nm("COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY")
    # uncertain (A7) -> unchanged: near-miss force stands
    assert not cm("SUBURBAN LAND BANK &amp;")
    assert nm("SUBURBAN LAND BANK &amp;")
    # exact-string only: a ruling never generalizes into a pattern
    assert not cm("SOUTH SUBN LAND BK & DEV AUTH LLC")
    assert nm("SOUTH SUBN LAND BK & DEV AUTH LLC")
    # M-RI-16 (§9 A2): the F1 string is attested; a variant of it is not,
    # and post-amendment the near-miss net now SEES such variants
    assert cm("SO SUB LAND/BK/DEV")
    assert not nm("SO SUB LAND/BK/DEV")
    assert not cm("SO SUB LAND/BK/DEV II")
    assert nm("SO SUB LAND/BK/DEV II")
    # frozen behavior delegated for everything else
    assert cm("SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY")
    assert not cm("US BANK TR") and not nm("US BANK TR")
    # status map unchanged: every status ruling was uncertain
    assert sc == rules.STATUS_CLASS


def test_overlay_is_scoped_and_restored():
    events = att.load_events()
    snaps = engine.load_snapshots(AUDIT_DIR / "snapshots")
    before = (rules.client_match, rules.near_miss, rules.STATUS_CLASS)
    rerun_attested.classify_all_attested(snaps, events)
    assert (rules.client_match, rules.near_miss, rules.STATUS_CLASS) == before
    assert not rules.client_match("SOUTH SUBN LAND BK & DEV AUTH")


# --------------------------------------------------------------------------
# the re-run: determinism, known answer, transition traceability
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rerun():
    """Live machine vs the M-RI-15 attested baseline — the M-RI-16 comparison.

    (The M-RI-14 baseline comparison is preserved as a disk-artifact test
    below; the live machine moved past it with §9 amendment A2.)
    """
    events = att.load_events()
    snaps = engine.load_snapshots(AUDIT_DIR / "snapshots")
    baseline = json.loads(
        (AUDIT_DIR / "out" / "attested-2026-08-02" / "discrepancy_table.json")
        .read_text(encoding="utf-8"))["verdicts"]
    attested = rerun_attested.classify_all_attested(snaps, events)
    return events, snaps, baseline, attested


def test_rerun_deterministic(rerun):
    events, snaps, baseline, attested = rerun
    assert rerun_attested.classify_all_attested(snaps, events) == attested


def test_known_answer_survives_attestation(rerun):
    events, snaps, baseline, attested = rerun
    ka = [v for v in attested if v["pin14"] == rules.KNOWN_ANSWER_PIN14]
    assert ka and ka[0]["verdict"] == rules.KNOWN_ANSWER_VERDICT


def test_every_transition_traces_to_an_attestation_event(rerun):
    events, snaps, baseline, attested = rerun
    delta = rerun_attested.compute_delta(
        baseline, attested, events, rerun_attested.parties_by_pin14(snaps))
    assert delta, "remediation resolved nothing — expected transitions"
    for d in delta:
        assert d["causing_events"], (
            f"{d['pin']}: {d['from_verdict']} -> {d['to_verdict']} has no "
            "causing attestation event — the re-run is not the same machine")


def test_zero_transitions_outside_the_attested_surface(rerun):
    events, snaps, baseline, attested = rerun
    ruled = set(att.alias_strings(events)) | set(att.not_client_strings(events))
    parties = rerun_attested.parties_by_pin14(snaps)
    base_by_pin = {v["pin"]: v for v in baseline}
    for v in attested:
        b = base_by_pin[v["pin"]]
        if b["verdict"] != v["verdict"]:
            touched = (set(b["near_miss_strings"]) | set(
                parties.get(v["pin14"] or "", []))) & ruled
            assert touched, (
                f"{v['pin']} transitioned without a ruled string in its records")


def test_mri15_structural_guarantee_pinned_as_history():
    """The M-RI-15 property, re-pinned on the shipped artifacts: the operator's
    first 12 rulings could not reach the M-RI-14 CONTRADICTED set (any parcel
    with a ruled string was already AMBIGUOUS). Asserted on disk so the live
    machine's later amendments (§9 A2) cannot erode the historical record."""
    base = json.loads((AUDIT_DIR / "out" / "discrepancy_table.json")
                      .read_text(encoding="utf-8"))["verdicts"]
    m15 = json.loads(
        (AUDIT_DIR / "out" / "attested-2026-08-02" / "discrepancy_table.json")
        .read_text(encoding="utf-8"))["verdicts"]
    base_c = {v["pin"] for v in base if v["verdict"] == rules.CONTRADICTED}
    m15_c = {v["pin"] for v in m15 if v["verdict"] == rules.CONTRADICTED}
    assert base_c == m15_c
