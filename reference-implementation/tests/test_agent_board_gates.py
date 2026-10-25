"""PREREG A3 (Day 4) gates on DERIVED documents: a synthetic board payload run
through the capture tool's pure builder and the pure adapter, beside the
operator's already-committed run files (Days 1-3, pinned by earlier gates). No
real board payload is pinned yet (that is A3.1); nothing here reads the network.
Pre-existing gates are untouched; these only add.
"""

from __future__ import annotations

import html
import importlib.util
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_board as runner
from rights_events.adapters.agent_board import (
    MIRROR_CLAIMANT, STATUS_SELF_REPORTED, STATUS_VERIFIED, VENUE_CLAIMANT,
    parse_board_capture, parse_events, verified_row_event,
)
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURES
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
CONTROL = "0xa62993eb48ddcf74e2ac5cbeede580be0c915b92"
OBS_MS = 1792900000000           # 2026-10-25 UTC
DAY1_ROOT = "14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c"
DAY2_ROOT = "2b5a846b714d578da06f71d3dc1e9e29c6d92e1358e0c76cbabf5f6f32adfc38"
DAY3_ROOT = "8777b0a1e37df424f804943eb6c2e37b6c9853d8e241e1daefd8b772a754ee95"
OPEN_TX = "0x8402a8c353e460c7857c04473db27f02010b00a8eee77f9927cb541612e83ab2"
CLOSE_TX = "0x906ccd1d991bb21c91e604473de9e402041d0003341ed0ee34357870581f8c07"
GAP_OPEN = Decimal("0.06189842468509176441459564854")
GAP_CLOSE = Decimal("0.06191298748738522879944525963")


def _tool():
    path = _FIX / "capture_board_from_gdex.py"
    spec = importlib.util.spec_from_file_location("agent_board_capture_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(n: int = 30, actor_at: int | None = None) -> dict:
    rows = []
    for i in range(n):
        addr = ACTOR if actor_at == i else "0x" + format(0xabc << 148 | i, "040x")
        rows.append({"ethAddress": addr, "accountValue": f"{1000000 + i}.5",
                     "windowPerformances": [
                         ["day", {"pnl": "1.0", "roi": "0.1", "vlm": "0.0"}],
                         ["week", {"pnl": f"{500000 - i}.25", "roi": f"0.{i:02d}1",
                                   "vlm": "12.0"}],
                         ["month", {"pnl": "3.0", "roi": "0.3", "vlm": "0.0"}],
                         ["allTime", {"pnl": "4.0", "roi": "0.4", "vlm": "0.0"}]]})
    return {"isSuccess": True,
            "topTraders": {"day": rows[:5], "week": rows, "month": rows, "allTime": rows}}


def _capture(payload=None, **kw) -> dict:
    payload = payload or _payload()
    cap, _man = _tool().build_capture(
        payload, OBS_MS, ACTOR, CONTROL, "gdex_hl_top_traders_by_pnl_2026-10-25.json",
        "a" * 64, "synthetic (gate)", **kw)
    return cap


def _text(cap: dict) -> str:
    return json.dumps(cap, indent=2) + "\n"


def _run_files():
    # The record AS OF the 2026-10-25 board observation (the three run files its verified
    # row names); later days add run files beside them (widened 2026-10-25, P8d, disclosed).
    return [_FIX / n for n in (
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri")]


# --- R20: the board observation ------------------------------------------------------

def test_board_known_answer_from_synthetic_payload():
    cap = _capture()
    assert cap["kind"] == "agent_record_board_capture"
    assert cap["observation"]["observed_date"] == "2026-10-25"
    assert cap["observation"]["rows"] == 30 and cap["observation"]["actor_on_board"] is False
    assert cap["observation"]["boards_listing_actor"] == []
    doc, event = parse_board_capture(_text(cap))
    assert event.event_id == f"agent_record:board:week:{OBS_MS}"
    assert event.event_type is EventType.CHAIN_ASSERTION
    assert event.ep_type is EPType.SELF_ASSERTED
    assert event.claimant == VENUE_CLAIMANT
    assert event.subject_ids == (f"agent:{ACTOR}",)
    assert event.claim["mechanism"] == "venue-board-observation"
    assert event.claim["rows"] == 30 == len(event.claim["rows_verbatim"])
    first = event.claim["rows_verbatim"][0]
    assert first["rank"] == 1 and first["week_pnl_usdc"] == Decimal("500000.25")
    assert first["account_value_usdc"] == Decimal("1000000.5")
    assert first["week_roi"] == Decimal("0.001") and first["week_vlm"] == Decimal("12.0")
    assert event.source_url == "https://trade-api.gemach.io/v1/hl/top_traders_by_pnl"
    assert parse_board_capture(_text(cap))[1] == event


def test_actor_on_board_is_measured_not_asserted():
    cap = _capture(_payload(actor_at=4))
    assert cap["observation"]["actor_on_board"] is True
    assert cap["observation"]["boards_listing_actor"] == ["day", "week", "month", "allTime"]
    _doc, event = parse_board_capture(_text(cap))
    assert event.claim["actor_on_board"] is True
    assert event.claim["rows_verbatim"][4]["address"] == ACTOR


def test_rejects_actor_flag_that_disagrees_with_rows():
    cap = _capture()
    cap["observation"]["actor_on_board"] = True
    with pytest.raises(AdapterError, match="actor_on_board"):
        parse_board_capture(_text(cap))
    cap = _capture(_payload(actor_at=2))
    cap["observation"]["boards_listing_actor"] = []
    with pytest.raises(AdapterError, match="boards_listing_actor"):
        parse_board_capture(_text(cap))


def test_rejects_row_count_mismatch_and_reranking():
    cap = _capture()
    cap["observation"]["rows"] = 29
    with pytest.raises(AdapterError, match="row count is never invented"):
        parse_board_capture(_text(cap))
    cap = _capture()
    cap["rows"][0]["rank"], cap["rows"][1]["rank"] = 2, 1
    with pytest.raises(AdapterError, match="no re-ranking"):
        parse_board_capture(_text(cap))


def test_rejects_non_week_window_bad_sha_wrong_kind_bad_number():
    cap = _capture()
    cap["observation"]["window"] = "day"
    with pytest.raises(AdapterError, match="window"):
        parse_board_capture(_text(cap))
    cap = _capture()
    cap["observation"]["payload_sha256"] = "abc"
    with pytest.raises(AdapterError, match="64 lowercase hex"):
        parse_board_capture(_text(cap))
    cap = _capture()
    cap["kind"] = "agent_record_capture"
    with pytest.raises(AdapterError, match="kind"):
        parse_board_capture(_text(cap))
    cap = _capture()
    cap["rows"][3]["week_pnl_usdc"] = "n/a"
    with pytest.raises(AdapterError, match="not numeric"):
        parse_board_capture(_text(cap))


# --- S18: the tool writes nothing on a bad payload ------------------------------------

def test_tool_refuses_bad_payloads():
    tool = _tool()
    bad = _payload(); bad["isSuccess"] = False
    with pytest.raises(SystemExit, match="isSuccess"):
        tool.week_rows(bad)
    bad = _payload(); del bad["topTraders"]["week"]
    with pytest.raises(SystemExit, match="no topTraders.week"):
        tool.week_rows(bad)
    bad = _payload(); bad["topTraders"]["week"][7]["windowPerformances"] = [["day", {}]]
    with pytest.raises(SystemExit, match="week row 7"):
        tool.week_rows(bad)


def test_tool_carries_payload_strings_unchanged():
    payload = _payload()
    rows = _tool().week_rows(payload)
    for r, src in zip(rows, payload["topTraders"]["week"]):
        wk = dict(src["windowPerformances"])["week"]
        assert r["address"] == src["ethAddress"]
        assert r["account_value_usdc"] == src["accountValue"]
        assert (r["week_pnl_usdc"], r["week_roi"], r["week_vlm"]) == (wk["pnl"], wk["roi"], wk["vlm"])


def test_tool_reads_one_public_page_and_nothing_else():
    """S21 / S14: no fills, no exchange, no order or funding path, no HL info calls."""
    src = (_FIX / "capture_board_from_gdex.py").read_text(encoding="utf-8")
    assert src.count("https://trade-api.gemach.io/v1") >= 1
    for forbidden in ("/exchange", "userFills", "clearinghouseState", "api.hyperliquid.xyz",
                      "execute_trade", "place_perp_order", "open_perp_position",
                      "perp_deposit", "transfer_", "preview_trade"):
        assert forbidden not in src, forbidden


# --- R21: the verified row over the committed run files --------------------------------

def test_record_summary_from_committed_run_files():
    summary, loaded = runner.summarize_record(_run_files(), ACTOR)
    files = summary["run_files"]
    assert [f["file"] for f in files] == [
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri"]
    assert [f["root"] for f in files] == [DAY1_ROOT, DAY2_ROOT, DAY3_ROOT]
    assert [f["events"] for f in files] == [2, 5, 9]
    assert [f["cryptographically_signed"] for f in files] == [0, 0, 2]
    assert [f["modes"] for f in files] == [["PAPER"], ["PAPER"], ["LIVE"]]
    assert files[0]["realized"] == [] and len(files[1]["realized"]) == 1
    assert files[2]["tx_hashes"] == [CLOSE_TX, OPEN_TX]        # log order (by event id)
    assert files[2]["gaps_bps"] == [GAP_OPEN, GAP_CLOSE]        # open leg before close leg
    assert set(loaded) == {f["file"] for f in files}


def test_verified_row_known_answer():
    events = parse_events(_text(_capture()),
                          runner.summarize_record(_run_files(), ACTOR)[0],
                          runner.RECORD_SOURCE_URL)
    assert len(events) == 2
    board, mirror = events
    assert board.claimant == VENUE_CLAIMANT and mirror.claimant == MIRROR_CLAIMANT
    assert mirror.event_id == "agent_record:mirror:2026-10-25"
    assert mirror.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert mirror.prior_event_refs == (board.event_id,)
    assert mirror.observed_date == board.observed_date == "2026-10-25"
    c = mirror.claim
    assert c["mechanism"] == "verified-row" and c["status"] == STATUS_VERIFIED
    assert c["roots"] == [DAY1_ROOT, DAY2_ROOT, DAY3_ROOT]
    assert sorted(c["tx_hashes"]) == sorted([OPEN_TX, CLOSE_TX])
    assert c["explorer_urls"] == [runner.HL_EXPLORER + h for h in c["tx_hashes"]]
    assert c["settled_pairs"] == {"PAPER": 1, "LIVE": 1}
    assert c["realized_paper_usd"] == Decimal("0.087640")
    assert c["realized_live_usd"] == Decimal("-0.035183")
    assert c["fees_live_usd"] == Decimal("0.032383")
    assert c["gaps_bps"] == [GAP_OPEN, GAP_CLOSE]
    assert c["never_summed_across_modes"] is True
    assert c["actor_on_board"] is False
    assert [r["bucket"] for r in c["realized_events"]] == ["GAIN", "LOSS"]
    assert not [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]  # R25
    assert not [e for e in events if e.event_type is EventType.DISPUTE]


def test_trace_holds_on_the_real_record_and_catches_an_invented_number():
    pipeline, events, _i, _doc, _summary, loaded = runner.build(_text(_capture()), _run_files())
    mirror = next(e for e in events if e.claimant == MIRROR_CLAIMANT)
    assert runner.trace_verified_row(mirror, loaded) == []
    forged = dict(mirror.claim)
    forged["realized_live_usd"] = Decimal("0.5")
    from rights_events.schema import RightsEvent
    fake = RightsEvent(event_id=mirror.event_id, event_type=mirror.event_type,
                       subject_ids=mirror.subject_ids, claimant=mirror.claimant,
                       claim=forged, ep_type=mirror.ep_type, source_url=mirror.source_url,
                       observed_date=mirror.observed_date,
                       prior_event_refs=mirror.prior_event_refs)
    assert any("realized_live_usd" in m for m in runner.trace_verified_row(fake, loaded))


def test_s19_tampered_run_file_is_never_summarized(tmp_path):
    src = _FIX / "run_LIVE_2026-10-24_pv_e1849abce514440c.ri"
    bad = tmp_path / src.name
    data = bytearray(src.read_bytes())
    data[len(data) // 2] ^= 0x01
    bad.write_bytes(bytes(data))
    with pytest.raises(AdapterError, match="S19"):
        runner.summarize_record([bad], ACTOR)


def test_board_run_is_never_its_own_evidence(tmp_path):
    bogus = tmp_path / "run_BOARD_2026-10-25.ri"
    shutil.copy(_FIX / "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri", bogus)
    with pytest.raises(AdapterError, match="R22"):
        runner.load_run_events(bogus)
    assert not any(p.name.startswith("run_BOARD_") for p in _run_files())
    _doc, board = parse_board_capture(_text(_capture()))
    summary = {"actor_id": ACTOR, "run_files": [{
        "file": "run_BOARD_x.ri", "sha256": "b" * 64, "root": "c" * 64, "events": 2,
        "cryptographically_signed": 0, "modes": ["PAPER"], "realized": [],
        "gaps_bps": [], "tx_hashes": [], "explorer_urls": []}]}
    with pytest.raises(AdapterError, match="R22"):
        verified_row_event(board, summary, runner.RECORD_SOURCE_URL)


def test_summary_validation_rejects_invented_record_facts():
    _doc, board = parse_board_capture(_text(_capture()))
    base = {"file": "run_X.ri", "sha256": "b" * 64, "root": "c" * 64, "events": 2,
            "cryptographically_signed": 0, "modes": ["PAPER"], "realized": [],
            "gaps_bps": [], "tx_hashes": [], "explorer_urls": []}
    def with_(**kw):
        return {"actor_id": ACTOR, "run_files": [{**base, **kw}]}
    with pytest.raises(AdapterError, match="R19"):
        verified_row_event(board, with_(modes=["PAPER", "LIVE"]), runner.RECORD_SOURCE_URL)
    with pytest.raises(AdapterError, match="PAPER run file cannot carry chain hashes"):
        verified_row_event(board, with_(tx_hashes=["0xab"], explorer_urls=["u"]),
                           runner.RECORD_SOURCE_URL)
    with pytest.raises(AdapterError, match="tx hashes !="):
        verified_row_event(board, with_(modes=["LIVE"], tx_hashes=["0xab"],
                                        explorer_urls=["u"]), runner.RECORD_SOURCE_URL)
    with pytest.raises(AdapterError, match="realized\\[0\\].mode"):
        verified_row_event(board, with_(realized=[{"event_id": "x", "mode": "LIVE",
                                                   "realized_pnl_usd": "1", "fees_usd": "0",
                                                   "bucket": "GAIN"}]),
                           runner.RECORD_SOURCE_URL)
    with pytest.raises(AdapterError, match="not the board event's subject"):
        verified_row_event(board, {"actor_id": CONTROL, "run_files": [base]},
                           runner.RECORD_SOURCE_URL)


# --- R22 / R23: the run and the rendered mirror are deterministic ------------------------

def test_board_run_byte_identical_and_reverifies(tmp_path):
    text = _text(_capture())
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    p1 = runner.build(text, _run_files())[0]
    p2 = runner.build(text, _run_files())[0]
    p1.save(a); p2.save(b)
    assert a.read_bytes() == b.read_bytes()
    ok, report = runner.verify_run(a)
    assert ok and "reloaded 2 events" in report
    assert len(p1.event_log) == 2


def test_mirror_is_a_pure_function_and_keeps_venue_strings():
    payload = _payload()
    text = _text(_capture(payload))
    pipeline, events, _i, doc, _s, _l = runner.build(text, _run_files())
    root = pipeline.event_log.root(2).hex()
    m1 = runner.render_mirror(doc, events, "run_BOARD_2026-10-25.ri", root)
    m2 = runner.render_mirror(doc, events, "run_BOARD_2026-10-25.ri", root)
    assert runner.mirror_json(m1) == runner.mirror_json(m2)
    assert runner.render_html(m1) == runner.render_html(m2)
    assert runner.render_markdown(m1) == runner.render_markdown(m2)
    assert m1["kind"] == "proof_of_outcome_board_mirror" and m1["as_of"] == "2026-10-25"
    assert len(m1["rows"]) == 30 and all(r["status"] == STATUS_SELF_REPORTED for r in m1["rows"])
    for r, src in zip(m1["rows"], payload["topTraders"]["week"]):
        wk = dict(src["windowPerformances"])["week"]
        assert r["address"] == src["ethAddress"]
        assert r["week_pnl_usdc"] == wk["pnl"] and r["account_value_usdc"] == src["accountValue"]
    v = m1["verified_row"]
    assert v["status"] == STATUS_VERIFIED and v["address"] == ACTOR
    assert v["on_venue_board"] is False
    assert Decimal(v["realized_live_usd"]) == Decimal("-0.035183")
    assert Decimal(v["realized_paper_usd"]) == Decimal("0.087640")
    assert v["never_summed_across_modes"] is True
    assert [f["root"] for f in v["run_files"]] == [DAY1_ROOT, DAY2_ROOT, DAY3_ROOT]
    assert m1["board_run"]["root"] == root
    html_text, md_text = runner.render_html(m1), runner.render_markdown(m1)
    for r in m1["rows"]:
        assert r["week_pnl_usdc"] in html_text and r["week_pnl_usdc"] in md_text
    for status in (STATUS_SELF_REPORTED, STATUS_VERIFIED):
        assert html.escape(m1["statuses"][status]) in html_text
        assert m1["statuses"][status] in md_text
    assert html_text.startswith("<title>Proof of Outcome Week Board</title>")
    assert "<!doctype" not in html_text.lower() and "<body" not in html_text
    assert html_text.index("The venue's board") < html_text.index("The operator's verified row")
    for h in (OPEN_TX, CLOSE_TX):
        assert runner.HL_EXPLORER + h in html_text


def test_runner_main_ok_on_derived_capture(tmp_path, capsys):
    cap = tmp_path / "capture_BOARD_2026-10-25.json"
    cap.write_text(_text(_capture()), encoding="utf-8")
    out = tmp_path / "run_BOARD_2026-10-25.ri"
    rc = runner.main(["--capture", str(cap), "--out", str(out),
                      "--mirror-out", str(tmp_path / "board_2026-10-25")])
    text = capsys.readouterr().out
    assert rc == 0, text
    assert "AGENT-RECORD BOARD RUN: OK" in text
    assert "0 dispute, 0 cryptographically_signed" in text
    assert "C6 venue rows carry the pinned payload's strings unchanged (payload not beside capture; skipped)" in text
    for suffix in (".json", ".md", ".html"):
        assert (tmp_path / f"board_2026-10-25{suffix}").exists()
    assert runner.main(["--verify", "--run", str(out)]) == 0


def test_paper_and_live_run_files_untouched_by_the_board_machinery():
    """The mirror READS the record; the Day 1-3 run files keep their pinned bytes."""
    import hashlib
    pins = {
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri":
            "598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri":
            "8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri":
            "126afbe5a4bb5116162919c6cd47cedcaa41d55805475ceb1b4167de13c9559a",
    }
    for name, sha in pins.items():
        assert hashlib.sha256((_FIX / name).read_bytes()).hexdigest() == sha
