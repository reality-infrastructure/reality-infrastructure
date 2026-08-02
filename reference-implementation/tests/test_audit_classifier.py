"""M-RI-14: classifier rule branches (PREREGISTRATION.md §5) + the known answer.

The known-answer test drives the engine with the REAL frozen pilot snapshots for
PIN 29024080530000 — the pre-registered commitment is CONTRADICTED via D3. If that
ever fails, it is a STOP S6 finding, not a test to fix.
"""
import json
from pathlib import Path

import pytest

from audit import engine, rules

ROOT = Path(__file__).resolve().parents[1]
CLIENT = "SOUTH SUBURBAN LAND BANK & DEV AUTH"
RETRIEVED = "2026-08-02"


def crm(status, date=None, ppn="11-11-111-111-1111", cook=True, checkable=True):
    return {"USER_ppn": ppn, "USER_disp_status": status,
            "USER_date_disposed": date, "cook_format": cook,
            "checkable": checkable}


def deed(seller, buyer, sale_date, doc="D1"):
    return {"pin": "11111111111111", "seller_name": seller, "buyer_name": buyer,
            "sale_date": f"{sale_date}T00:00:00.000" if sale_date else None,
            "doc_no": doc, "row_id": f"r-{doc}"}


def assr(owner, year, mail=None, row="a1"):
    return {"pin": "11111111111111", "owner_address_name": owner,
            "mail_address_name": mail or owner, "year": year, "row_id": row}


def run(c, deeds=(), assessor=(), tax=(), scav=()):
    return engine.classify(c, list(deeds), list(assessor), list(tax),
                           list(scav), RETRIEVED)


# --- DISPOSED branches -----------------------------------------------------

def test_d1_supported_client_seller_in_window():
    v = run(crm("Sold", "2020-06-15"), deeds=[deed(CLIENT, "JANE DOE", "2020-05-01")])
    assert (v["verdict"], v["rule"]) == (rules.SUPPORTED, "D1")
    assert v["citations"][0]["record"] == "D1"


def test_d3_contradicted_third_party_window_client_absent_everywhere():
    v = run(crm("Sold", "2019-01-01"),
            deeds=[deed("ALICE A", "BOB B", "2019-03-01")],
            assessor=[assr("ALICE A", "2018"), assr("BOB B", "2020")])
    assert (v["verdict"], v["rule"]) == (rules.CONTRADICTED, "D3")


def test_d4_unsupported_no_window_deed_client_absent():
    v = run(crm("Sold", "2018-01-01"), assessor=[assr("CAROL C", "2019")])
    assert (v["verdict"], v["rule"]) == (rules.UNSUPPORTED_NO_RECORD, "D4")
    assert rules.ABSENCE_FRAMING in v["citations"][0]["parties"]


def test_d5_ambiguous_third_party_window_but_client_present():
    v = run(crm("Sold", "2019-01-01"),
            deeds=[deed("ALICE A", "BOB B", "2019-03-01")],
            assessor=[assr(CLIENT, "2017")])
    assert (v["verdict"], v["rule"]) == (rules.AMBIGUOUS, "D5")


def test_d_out_of_window_deed_is_not_a_contradiction():
    v = run(crm("Sold", "2015-01-01"),
            deeds=[deed("ALICE A", "BOB B", "2019-03-01")])
    assert (v["verdict"], v["rule"]) == (rules.UNSUPPORTED_NO_RECORD, "D4")


def test_d_nodate_client_seller_deed_caps_at_ambiguous():
    v = run(crm("Sold", None), deeds=[deed(CLIENT, "JANE DOE", "2020-05-01")])
    assert (v["verdict"], v["rule"]) == (rules.AMBIGUOUS, "D-nodate")


def test_d_nodate_nothing_bearing_is_unsupported():
    v = run(crm("Sold", None), deeds=[deed("ALICE A", "BOB B", "2019-03-01")])
    assert (v["verdict"], v["rule"]) == (rules.UNSUPPORTED_NO_RECORD, "D-nodate")


# --- HELD branches ---------------------------------------------------------

def test_h1_supported_max_year_assessor_owner():
    v = run(crm("Secured Inventory - Active"),
            assessor=[assr("OLD OWNER", "2020"), assr(CLIENT, "2026.0")])
    assert (v["verdict"], v["rule"]) == (rules.SUPPORTED, "H1")


def test_h2_supported_deed_to_client_never_deeded_away():
    v = run(crm("Listed"), deeds=[deed("SELLER S", CLIENT, "2022-04-01")],
            assessor=[assr("SELLER S", "2022")])
    assert (v["verdict"], v["rule"]) == (rules.SUPPORTED, "H2")


def test_h3_contradicted_latest_client_deed_is_outbound():
    v = run(crm("Secured Inventory - Active"),
            deeds=[deed("SELLER S", CLIENT, "2015-01-01", doc="in"),
                   deed(CLIENT, "NEW OWNER", "2018-06-01", doc="out")],
            assessor=[assr("NEW OWNER", "2019")])
    assert (v["verdict"], v["rule"]) == (rules.CONTRADICTED, "H3")
    assert v["citations"][0]["record"] == "out"


def test_h4_unsupported_client_absent():
    v = run(crm("Under Contract"), assessor=[assr("SOMEBODY ELSE", "2026")])
    assert (v["verdict"], v["rule"]) == (rules.UNSUPPORTED_NO_RECORD, "H4")


def test_h5_ambiguous_client_present_only_in_old_years():
    v = run(crm("Demolition Phase"),
            assessor=[assr(CLIENT, "2020"), assr("SOMEBODY ELSE", "2026")])
    assert (v["verdict"], v["rule"]) == (rules.AMBIGUOUS, "H5")


# --- NEAR-MISS override ----------------------------------------------------

def test_near_miss_forces_ambiguous_and_cites_verbatim():
    v = run(crm("Listed"),
            deeds=[deed("COOK COUNTY LAND BANK AUTH", "BOB B", "2021-01-01")])
    assert v["verdict"] == rules.AMBIGUOUS
    assert v["rule"].endswith("+NEAR-MISS")
    assert v["near_miss_strings"] == ["COOK COUNTY LAND BANK AUTH"]


# --- NOT_CHECKABLE gates ---------------------------------------------------

@pytest.mark.parametrize("c,reason", [
    (crm("Sold", "2020-01-01", ppn="4545", cook=False, checkable=False),
     "pin-format"),
    (crm("Sold", "2020-01-01", ppn="31-33-407-020-0000", checkable=False),
     "county-mismatch"),
    (crm("Deed Recorded"), "status-semantics-unresolved"),
    (crm("Test Parcel"), "no-county-checkable-claim"),
])
def test_not_checkable_reasons(c, reason):
    v = run(c)
    assert (v["verdict"], v["reason"]) == (rules.NOT_CHECKABLE, reason)


# --- the pre-registered known answer (STOP S6 if this fails) ---------------

def test_known_answer_dolton_contradicted_from_frozen_pilot_snapshots():
    deeds = json.loads((ROOT / "pilot/snapshots/ccao_parcel_sales.json")
                       .read_text(encoding="utf-8"))["records"]
    assessor = json.loads((ROOT / "pilot/snapshots/cc_assessor.json")
                          .read_text(encoding="utf-8"))["records"]
    crm_snap = json.loads((ROOT / "audit/snapshots/crm_inventory.json")
                          .read_text(encoding="utf-8"))["records"]
    row = [r for r in crm_snap if r["USER_ppn"] == "29-02-408-053-0000"]
    assert row and row[0]["USER_disp_status"] == "Sold"
    assert row[0]["USER_date_disposed"] == "2017-01-01"
    v = engine.classify(row[0], deeds, assessor, [], [], RETRIEVED)
    assert v["verdict"] == rules.KNOWN_ANSWER_VERDICT == rules.CONTRADICTED
    assert v["rule"] == "D3"
    cited = {c["record"] for c in v["citations"]}
    assert "1717247010" in cited  # the 2017-06-16 THORTON -> CSMA deed


# --- import hygiene --------------------------------------------------------

def test_engine_modules_import_no_network():
    for mod in ("pins", "rules", "engine", "report", "run_audit"):
        src = (ROOT / f"audit/{mod}.py").read_text(encoding="utf-8")
        for banned in ("urllib", "socket", "http.client", "requests"):
            assert banned not in src, f"{mod}.py mentions {banned}"
