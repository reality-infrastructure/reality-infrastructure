"""M-RI-15: exhibit citation-link integrity.

Every identifier the shipped exhibit cites must resolve, verbatim, in the
frozen snapshots — an exhibit that cites an unresolvable record is decoration,
not evidence. Also pins the honest-number selection outcome and the F1 finding
scan so a silent regeneration can't drift.
"""
import json
import re
from pathlib import Path

from audit import rules
from audit.attestation import events as att
from audit import rerun_attested

OUT = Path(__file__).parent.parent / "audit" / "out" / "attested-2026-08-02"
SNAP = Path(__file__).parent.parent / "audit" / "snapshots"
EXHIBIT = OUT / "exhibit-1-dolton-29-02-408-053-CLIENT-DO-NOT-SEND-PROSPECTS.md"


def _sales_rows(pin14):
    doc = json.loads((SNAP / "ccao_parcel_sales.json").read_text(encoding="utf-8"))
    return [r for r in doc["records"] if str(r["pin"]) == pin14]


def _assessor_rows(pin14):
    doc = json.loads((SNAP / "cc_assessor.json").read_text(encoding="utf-8"))
    return [r for r in doc["records"] if str(r["pin"]) == pin14]


def test_exhibit_deed_citation_resolves_verbatim():
    text = EXHIBIT.read_text(encoding="utf-8")
    rows = [r for r in _sales_rows("29024080530000")
            if r["doc_no"] == "1717247010"]
    assert rows, "cited doc 1717247010 absent from the frozen snapshot"
    r = rows[0]
    assert r["deed_type"] == "Warranty"
    assert str(r["sale_date"])[:10] == "2017-06-16"
    assert r["seller_name"] == "RICHARD  THORTON"      # two spaces, verbatim
    assert r["buyer_name"] == "CSMA BLT, LLC"
    assert "1717247010" in text and "2017-06-16" in text
    assert "RICHARD  THORTON -> CSMA BLT, LLC" in text


def test_exhibit_assessor_rows_resolve():
    text = EXHIBIT.read_text(encoding="utf-8")
    rows = {str(r["row_id"]): r for r in _assessor_rows("29024080530000")}
    cited = set(re.findall(r"29024080530000\d{4}", text))
    assert cited, "no assessor row ids cited"
    for row_id in cited:
        assert row_id in rows, f"cited assessor row {row_id} unresolvable"
    # chain endpoints verbatim
    assert rows["290240805300001999"]["owner_address_name"] == "ROBERT STOKES"
    assert rows["290240805300002016"]["owner_address_name"] == "CSMA BLT LLC"
    assert "FIRST KEY" in rows["290240805300002017"]["owner_address_name"]


def test_exhibit_parcel_survives_all_criteria():
    """(a) stable CONTRADICTED, (c) no client-resembling string, incl. the
    F1 separator variant — the exhibit parcel must stay clean."""
    attested = json.loads((OUT / "discrepancy_table.json")
                          .read_text(encoding="utf-8"))["verdicts"]
    v = [x for x in attested if x["pin14"] == "29024080530000"][0]
    assert v["verdict"] == rules.CONTRADICTED and v["rule"] == "D3"
    assert not v["near_miss_strings"]
    for r in _sales_rows("29024080530000"):
        for s in (r.get("seller_name") or "", r.get("buyer_name") or ""):
            assert not rules.near_miss(re.sub(r"[^A-Za-z0-9&]", " ", s))
    for r in _assessor_rows("29024080530000"):
        for s in (r.get("owner_address_name") or "",
                  r.get("mail_address_name") or ""):
            assert not rules.near_miss(re.sub(r"[^A-Za-z0-9&]", " ", s))


def test_replay_line_runs_clean(capsys):
    rc = rerun_attested.main(["--pin", "29024080530000"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"verdict": "CONTRADICTED"' in out
    assert "baseline verdict: CONTRADICTED (D3) -> attested verdict: "
    assert "CONTRADICTED (D3)" in out


def test_no_string_escapes_the_near_miss_net():
    """Post-A2 (M-RI-16): the F1 escape set is EMPTY — no string in the
    evidence base changes match status under punctuation-neutral
    normalization. (Pre-A2 this asserted the set was exactly
    {'SO SUB LAND/BK/DEV'}; the amendment closed it, and this test now
    holds the net shut.)"""
    escaped = set()
    for fname, fields in (("ccao_parcel_sales.json",
                           ("seller_name", "buyer_name")),
                          ("cc_assessor.json",
                           ("owner_address_name", "mail_address_name"))):
        doc = json.loads((SNAP / fname).read_text(encoding="utf-8"))
        for r in doc["records"]:
            for f in fields:
                s = r.get(f) or ""
                if not s or rules.client_match(s) or rules.near_miss(s):
                    continue
                loose = re.sub(r"[^A-Za-z0-9&]", " ", s)
                if rules.client_match(loose) or rules.near_miss(loose):
                    escaped.add(s)
    assert escaped == set()
