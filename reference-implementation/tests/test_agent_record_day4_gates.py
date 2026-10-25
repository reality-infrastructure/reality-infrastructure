"""Day-4 gates for agent_record: the REAL board capture (A3.1) and the committed
board run + mirror files. The pins were committed strictly before this file
(A3.1 59c8ae4). The numbers below are the A3 / A3.1 known answers, not re-derived
from the fixtures. Pre-existing gates are untouched; these only add.

Widened 2026-10-25 evening (P8d, disclosed): the board of 2026-10-25 mirrored the record
AS OF its observation — the three run files its own verified row names. Each later day's
pair adds a run file beside them (A2 R19), so the gates below render over that named set
(RECORD_AT_OBSERVATION) instead of "every run file in the directory", and the directory
gate asserts the record has GROWN rather than that it is frozen.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_board as runner
from rights_events.adapters.agent_board import (
    MIRROR_CLAIMANT, VENUE_CLAIMANT, parse_board_capture,
)
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURES
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
DATE = "2026-10-25"
OBS_MS = 1792906235038
CAPTURE = _FIX / f"capture_BOARD_{DATE}.json"
PAYLOAD = _FIX / f"gdex_hl_top_traders_by_pnl_{DATE}.json"
RUN_FILE = _FIX / f"run_BOARD_{DATE}.ri"
TEXT = CAPTURE.read_text(encoding="utf-8")
BOARD_ROOT = "6190df8f34f3066b6c52a9e088f6c6957e0d81e810bc1bdf91883267f66e72d3"

PINS = {
    # A3.1
    f"gdex_hl_top_traders_by_pnl_{DATE}.json":
        "4caa7ef634ebe3bb23767f5062a4cfc57d5f1ed501e0a34552f2ce3940b19316",
    f"capture_BOARD_{DATE}.json":
        "3c79b46c7b300c63b6aa14e00c5d07d4c355618f7224fdf92543d2c7b9417504",
    f"MANIFEST_BOARD_{DATE}.json":
        "e158701124bfef1e7dd6b9a4c51bf2a853a10e33a6e03fa0b2d793ff3979d3b9",
    # P7 outputs (the run of the pinned inputs)
    f"run_BOARD_{DATE}.ri":
        "3d4f13d611d0383bdd6af71a4285e5aa4a6d1cb2a77b968f5ac5eb9c09b8d1ab",
    f"board_{DATE}.json":
        "79240201ac3acfdf883a0d32abb94fc55751e0a4891d1ac21de9f201d563bce9",
    f"board_{DATE}.md":
        "677371aa2d124cbda4d482c08df5395feb7bb4a5d7e87e160049cd0c193d8211",
    f"board_{DATE}.html":
        "d16b07c86db96ad32e195e869f30a4ed39fbc5f9900e64702db06d6824d5772b",
}
OPEN_TX = "0x8402a8c353e460c7857c04473db27f02010b00a8eee77f9927cb541612e83ab2"
CLOSE_TX = "0x906ccd1d991bb21c91e604473de9e402041d0003341ed0ee34357870581f8c07"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_day4_pinned_inputs_and_outputs_unchanged(name, sha):
    path = _FIX / name
    actual = _lf_sha(path) if path.suffix != ".ri" else hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == sha


def test_capture_is_the_payload_verbatim():
    """Every one of the thirty rows carries the venue's own strings (R24, C6)."""
    doc = json.loads(TEXT)
    raw = PAYLOAD.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == doc["observation"]["payload_sha256"]
    week = json.loads(raw.decode("utf-8"))["topTraders"]["week"]
    assert len(week) == 30 == doc["observation"]["rows"] == len(doc["rows"])
    for r, src in zip(doc["rows"], week):
        wk = dict(src["windowPerformances"])["week"]
        assert r["address"] == src["ethAddress"]
        assert r["account_value_usdc"] == src["accountValue"]
        assert (r["week_pnl_usdc"], r["week_roi"], r["week_vlm"]) == (wk["pnl"], wk["roi"], wk["vlm"])
    manifest = json.loads((_FIX / f"MANIFEST_BOARD_{DATE}.json").read_text(encoding="utf-8"))
    assert manifest["known_answer"] == {"rows": 30, "actor_on_board": False,
                                        "boards_listing_actor": []}
    assert manifest["sha256"] == PINS[CAPTURE.name]


def test_day4_board_known_answer():
    _doc, event = parse_board_capture(TEXT)
    assert event.event_id == f"agent_record:board:week:{OBS_MS}"
    assert event.ep_type is EPType.SELF_ASSERTED and event.claimant == VENUE_CLAIMANT
    assert event.observed_date == DATE
    c = event.claim
    assert c["rows"] == 30 and c["actor_on_board"] is False and c["boards_listing_actor"] == []
    assert c["rows_verbatim"][0]["address"] == "0x5b5d51203a0f9079f8aeb098a6523a13f298c060"
    assert c["rows_verbatim"][0]["week_pnl_usdc"] == Decimal("10599150.8316670004")
    assert c["rows_verbatim"][29]["week_pnl_usdc"] == Decimal("1112000.0")
    assert not any(r["address"].lower() == ACTOR for r in c["rows_verbatim"])


RECORD_AT_OBSERVATION = [_FIX / n for n in (
    "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri",
    "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri",
    "run_LIVE_2026-10-24_pv_e1849abce514440c.ri")]


def _day4_run():
    return runner.build(TEXT, RECORD_AT_OBSERVATION)


def test_day4_run_is_two_events_zero_disputes_zero_signed():
    pipeline, events, indices, _doc, _summary, loaded = _day4_run()
    assert len(events) == len(pipeline.event_log) == 2
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert not [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]   # R25
    mirror = next(e for e in events if e.claimant == MIRROR_CLAIMANT)
    c = mirror.claim
    assert c["settled_pairs"] == {"PAPER": 1, "LIVE": 1}
    assert c["realized_paper_usd"] == Decimal("0.087640")
    assert c["realized_live_usd"] == Decimal("-0.035183")
    assert c["fees_live_usd"] == Decimal("0.032383")
    assert sorted(c["tx_hashes"]) == sorted([OPEN_TX, CLOSE_TX])
    assert len(c["run_files"]) == 3 and c["actor_on_board"] is False
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices
    assert runner.trace_verified_row(mirror, loaded) == []                            # S20
    assert pipeline.event_log.root(2).hex() == BOARD_ROOT


def test_day4_committed_run_file_is_the_run(tmp_path):
    pipeline, _e, _i, _d, _s, _l = _day4_run()
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    assert fresh.read_bytes() == RUN_FILE.read_bytes()
    ok, report = runner.verify_run(RUN_FILE)
    assert ok, report
    assert "reloaded 2 events" in report and report.endswith(BOARD_ROOT)


def test_day4_committed_mirror_files_are_the_render():
    pipeline, events, _i, doc, _s, _l = _day4_run()
    m = runner.render_mirror(doc, events, RUN_FILE.name, pipeline.event_log.root(2).hex())
    assert runner.mirror_json(m).encode("utf-8") == (_FIX / f"board_{DATE}.json").read_bytes().replace(b"\r\n", b"\n")
    assert runner.render_markdown(m).encode("utf-8") == (_FIX / f"board_{DATE}.md").read_bytes().replace(b"\r\n", b"\n")
    assert runner.render_html(m).encode("utf-8") == (_FIX / f"board_{DATE}.html").read_bytes().replace(b"\r\n", b"\n")
    committed = json.loads((_FIX / f"board_{DATE}.json").read_text(encoding="utf-8"))
    assert committed["board_run"]["root"] == BOARD_ROOT
    assert len(committed["rows"]) == 30 and committed["verified_row"]["on_venue_board"] is False
    assert Decimal(committed["verified_row"]["realized_live_usd"]) == Decimal("-0.035183")
    html_text = (_FIX / f"board_{DATE}.html").read_text(encoding="utf-8")
    for h in (OPEN_TX, CLOSE_TX):
        assert runner.HL_EXPLORER + h in html_text
    for r in committed["rows"]:
        assert r["week_pnl_usdc"] in html_text


def test_day4_runner_main_ok_on_the_record_at_observation(tmp_path, capsys):
    out = tmp_path / "run.ri"
    argv = ["--out", str(out), "--mirror-out", str(tmp_path / "board")]
    for path in RECORD_AT_OBSERVATION:
        argv += ["--run-file", str(path)]
    assert runner.main(argv) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD BOARD RUN: OK" in text
    assert "PASS  C6 venue rows carry the pinned payload's strings unchanged\n" in text
    assert "actor on board: False" in text
    assert out.read_bytes() == RUN_FILE.read_bytes()


def test_exactly_one_pinned_board_capture_and_record_files_untouched():
    assert [p.name for p in runner.pinned_board_captures()] == [CAPTURE.name]
    today = [p.name for p in runner.record_run_files()]
    assert today[:3] == [p.name for p in RECORD_AT_OBSERVATION]
    # The record has grown since the observation (Day 4's own pair, A4.2 / A5.1); the
    # committed board files stay the render over the three files they name.
    assert today[3:] == ["run_LIVE_2026-10-25_pv_aca51be96df9478c.ri"]
    pins = {
        "run_LIVE_2026-10-25_pv_aca51be96df9478c.ri":
            "4c03441d4c6224fb8fc2358eea2b5819ed34bd98dca0fa3cec38c3766ec80d1b",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri":
            "598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri":
            "8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri":
            "126afbe5a4bb5116162919c6cd47cedcaa41d55805475ceb1b4167de13c9559a",
    }
    for name, sha in pins.items():
        assert hashlib.sha256((_FIX / name).read_bytes()).hexdigest() == sha
