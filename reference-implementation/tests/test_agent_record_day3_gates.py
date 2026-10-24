"""Day-3 gates for agent_record: the REAL LIVE captures (A2.1 open, A2.3 close) and
the Day-3 run file. Each pin was committed strictly before this file (A2.1 144b78a,
A2.3 the commit before P5). The numbers below are the A2.1 / A2.3 known answers,
not re-derived from the fixtures. Pre-existing gates are untouched; these only add.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    GAP_CHECK, INTENT_CLAIMANT, LIVE_CLAIMANT, LIVE_PNL_CHECK, PAPER_CLAIMANT,
    parse_events,
)
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
OPEN_PV = "pv_e1849abce514440c"
CLOSE_PV = "pv_286c449157434b1e"
OPEN_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}.json"
CLOSE_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}_close.json"
RUN_FILE = _FIX / f"run_LIVE_2026-10-24_{OPEN_PV}.ri"
OPEN_TEXT = OPEN_CAP.read_text(encoding="utf-8")
CLOSE_TEXT = CLOSE_CAP.read_text(encoding="utf-8")
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"

PINS = {
    # A2.1 (open leg)
    f"capture_LIVE_2026-10-24_{OPEN_PV}.json":
        "2e9538c0629b751c847726058421439ab8202c3e5f203157c08aad508e8f7e5c",
    f"MANIFEST_LIVE_2026-10-24_{OPEN_PV}.json":
        "33d7d39e7019e7017cb1828acac8bc3e5dfcf94f5f81d6caf10acf38cf804483",
    f"gdex_preview_{OPEN_PV}.json":
        "0a56d9994c8e637f1d3783d1ca646f8166d7acad99774e30fa150826fd6cfaf5",
    "hl_userFillsByTime_1792823307404.json":
        "d90c24212a18c29af61b35ce8d2e22b940a92f504a529426dcd213859bc6747f",
    "hl_allMids_1792823307660.json":
        "b800493b2b5af0efcc93cc7c78fae48767c5f07be90386c43f0c81e358eefe51",
    # A2.2 (the close-preview probe, never executed)
    "gdex_preview_pv_b3918dbcef0b40d7_probe.json":
        "29617e0f66720a93dda929d3588981bd338f2b08375ab74eb0f9be07ac3a0e1c",
    # A2.3 (close leg)
    f"capture_LIVE_2026-10-24_{OPEN_PV}_close.json":
        "9404f0502910828260b2a64af1e091fe0e3cf509720b6b2693821e8f30d80850",
    f"MANIFEST_LIVE_2026-10-24_{OPEN_PV}_close.json":
        "ff00fac48c3c1aa209f26baf1d7ddb686d816077500a9d2998b3aa87476924eb",
    f"gdex_preview_{CLOSE_PV}.json":
        "c586a311f7e0156b57dd0254d04ae682d3eacce6f8de38b7ab28ef6fcdca24e1",
    "hl_userFillsByTime_1792824335531.json":
        "a2f3595419831f4fa8a5c81f1192efd8ecd6513dcbdbb78cf5cc882eb17f1d40",
    "hl_allMids_1792824335729.json":
        "137e4c5a912fdce869c4f199914306efc86c9f5093cbb90a056f06610b3e5be6",
}

OPEN_TX = "0x8402a8c353e460c7857c04473db27f02010b00a8eee77f9927cb541612e83ab2"
CLOSE_TX = "0x906ccd1d991bb21c91e604473de9e402041d0003341ed0ee34357870581f8c07"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _by(events, claimant):
    return [e for e in events if e.claimant == claimant]


# --- S15 / S17: pinned inputs -----------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_day3_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_close_capture_names_the_pinned_open_leg():
    c = json.loads(CLOSE_TEXT)["closes"]
    assert c["capture"] == OPEN_CAP.name
    assert c["sha256"] == PINS[OPEN_CAP.name]                 # S17
    assert c["intent_id"] == OPEN_PV and c["fill_id"] == f"live:{OPEN_PV}:open"
    assert c["size"] == "0.00014" and c["fill_price_usd"] == "80778.0"
    assert c["fill_fee_usd"] == "0.016193"


def test_captures_match_their_verbatim_payloads():
    """The capture's numbers are the chain's and the mid's, not typed in."""
    for cap, fills_name, mids_name in (
        (OPEN_TEXT, "hl_userFillsByTime_1792823307404.json", "hl_allMids_1792823307660.json"),
        (CLOSE_TEXT, "hl_userFillsByTime_1792824335531.json", "hl_allMids_1792824335729.json"),
    ):
        doc = json.loads(cap)
        rows = json.loads((_FIX / fills_name).read_text(encoding="utf-8"))
        assert len(rows) == 1 == doc["live_fill"]["rows"]
        row = rows[0]
        assert doc["live_fill"]["tx_hashes"] == [row["hash"]]
        assert Decimal(doc["live_fill"]["price_usd"]) == Decimal(row["px"])
        assert Decimal(doc["live_fill"]["fee_usd"]) == (
            Decimal(row["fee"]) + Decimal(row["builderFee"]))
        assert doc["live_fill"]["fill_time_ms"] == row["time"]
        mids = json.loads((_FIX / mids_name).read_text(encoding="utf-8"))
        assert Decimal(doc["shadow_fill"]["price_usd"]) == Decimal(mids["BTC"])


# --- A2.1 known answer: the open leg --------------------------------------------

def test_day3_open_leg_known_answer():
    events = parse_events(OPEN_TEXT)
    assert len(events) == 4
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    assert {e.observed_date for e in events} == {"2026-10-24"}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["quote_price_usd"] == Decimal("80776")
    assert intent.claim["size"] == Decimal("0.00014")
    assert intent.claim["leverage"] == 1 and intent.claim["margin_mode"] == "cross"
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == Decimal("80778.0")
    assert live.claim["fee_usd"] == Decimal("0.016193")
    assert live.claim["tx_hashes"] == [OPEN_TX]
    assert live.claim["dir"] == "Open Long"
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.ep_type is EPType.SELF_ASSERTED
    assert shadow.claim["price_usd"] == Decimal("80777.5")
    assert shadow.claim["mode"] == "PAPER"
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06189842468509176441459564854")
    assert gap.claim["cost_sign"] == 1 and gap.claim["shadow_lag_ms"] == 2056
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert signed == [live]
    assert parse_events(OPEN_TEXT) == events


# --- A2.3 known answer: the close leg -------------------------------------------

def test_day3_close_leg_known_answer():
    events = parse_events(CLOSE_TEXT)
    assert len(events) == 5
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["kind"] == "perp_close" and intent.claim["side"] == "sell"
    assert intent.claim["quote_price_usd"] == Decimal("80758")
    assert intent.claim["reduce_only"] is True and intent.claim["is_full_close"] is True
    assert "leverage" not in intent.claim
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == Decimal("80758.0")
    assert live.claim["fee_usd"] == Decimal("0.016190")
    assert live.claim["tx_hashes"] == [CLOSE_TX]
    assert live.claim["dir"] == "Close Long"
    assert live.claim["closed_pnl_usd"] == Decimal("-0.0028")
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06191298748738522879944525963")
    assert gap.claim["cost_sign"] == -1 and gap.claim["shadow_lag_ms"] == 938
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert r.claim["realized_pnl_usd"] == Decimal("-0.035183")
    assert r.claim["fees_usd"] == Decimal("0.032383")
    assert r.claim["bucket"] == "LOSS"
    assert r.claim["venue_closed_pnl_usd"] == Decimal("-0.0028")
    assert r.claim["realized_pnl_usd"] + r.claim["fees_usd"] == r.claim["venue_closed_pnl_usd"]
    assert r.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",
                                  f"agent_record:fill:live:{OPEN_PV}:close")
    assert parse_events(CLOSE_TEXT) == events


# --- R19 / S10: the Day-3 run, one log, nine events --------------------------------

def _day3_run():
    return runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT])


def test_day3_run_is_nine_events_two_signed_zero_disputes():
    pipeline, events, indices = _day3_run()
    assert len(events) == len(pipeline.event_log) == 9
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert sorted(e.event_id for e in signed) == [
        f"agent_record:fill:live:{OPEN_PV}:close", f"agent_record:fill:live:{OPEN_PV}:open"]
    assert len(_by(events, GAP_CHECK)) == 2
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                               # S10
    assert runner._all_inclusions_verify(pipeline)


def test_day3_committed_run_file_is_the_run(tmp_path):
    """The committed Day-3 run file is byte-identical to a fresh run of the two
    pinned captures and re-verifies as a stranger would check it."""
    pipeline, _e, _i = _day3_run()
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    assert fresh.read_bytes() == RUN_FILE.read_bytes()
    ok, report = runner.verify_run(RUN_FILE)
    assert ok, report
    assert "reloaded 9 events" in report


def test_day3_runner_main_ok(tmp_path, capsys):
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD RUN: OK" in text
    assert "2 gap, 2 cryptographically_signed" in text
    assert "Realized live PnL" in text and "LOSS" in text


def test_paper_run_files_untouched():
    day1 = _FIX / "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri"
    day2 = _FIX / "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri"
    assert _lf_sha(day1) == "598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699"
    assert _lf_sha(day2) == "8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d"
    ok1, r1 = runner.verify_run(day1)
    ok2, r2 = runner.verify_run(day2)
    assert ok1 and r1.endswith("14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c")
    assert ok2 and r2.endswith("2b5a846b714d578da06f71d3dc1e9e29c6d92e1358e0c76cbabf5f6f32adfc38")


def test_default_run_still_paper_only_and_live_captures_are_exactly_two():
    names = [p.name for p in runner.pinned_captures()]
    assert names and all(n.startswith("capture_PAPER_") for n in names)
    live = sorted(p.name for p in _FIX.glob("capture_LIVE_*.json"))
    assert live == [OPEN_CAP.name, CLOSE_CAP.name]
    unexecuted = ("pv_a92f3a6925f7404f", "pv_11bbb908b7f74c6d", "pv_3351b5b948e9488b")
    assert not any((_FIX / f"gdex_preview_{pv}.json").exists() for pv in unexecuted)
