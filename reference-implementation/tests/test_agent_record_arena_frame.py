"""PREREG A19 gates (P15): the grader re-derives its own frame. The cohort is a function of
the pinned payload's bytes (R98), the window of the cohort date and the flags of the as-of
date (R99), the payload's sha is checked inside build() before any page (R100). Six planted
captures are refused WHOLE with their STOP named (S87/S88/S89); the two committed captures
and the synthetic fixture pass unchanged. Offline; no network, no clock.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import (
    DAY_MS, check_frame, cohort_from_payload, parse_arena_capture, rule_window,
)
from rights_events.adapters.common import AdapterError
from test_agent_record_arena import A1, A3, T0, T1, _fill, _gz, _page, _pins, make_capture

ARENA = runner._FIXTURES / "arena"
C1_CAP = ARENA / "2026-10-25" / "capture_ARENA_2026-10-25_2026-11-03.json"
C2_CAP = ARENA / "2026-11-03" / "capture_ARENA_2026-11-03_2026-11-03.json"
A4 = "0x4444444444444444444444444444444444444444"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def test_rule_window_is_a_function_of_the_cohort_date_and_the_as_of_date():
    w = rule_window("2026-10-25", "2026-11-03")
    assert (w["t0_ms"], w["t1_ms"], w["days"]) == (T0, T1, 8)
    assert w["started"] is True and w["complete"] is True
    w = rule_window("2026-11-03", "2026-11-03")
    assert (w["t0_ms"], w["t1_ms"], w["days"]) == (1793750400000, 1794355199999, 7)
    assert w["started"] is False and w["complete"] is False
    w = rule_window("2026-11-03", "2026-11-06")
    assert w["started"] is True and w["complete"] is False
    w = rule_window("2026-11-03", "2026-11-11")
    assert w["complete"] is True
    assert rule_window("2026-11-09", "2026-11-09")["t0_ms"] == 1793750400000 + 6 * DAY_MS
    with pytest.raises(AdapterError):
        rule_window("2026-13-01", "2026-11-03")


@pytest.mark.parametrize("cap", [C1_CAP, C2_CAP])
def test_committed_captures_equal_their_payloads_derivation(cap):
    """R98: the ONE derivation, applied to the pinned payload, reproduces the committed cohort."""
    doc, boards = parse_arena_capture(cap.read_text(encoding="utf-8"))
    payload = runner.payload_path_for(cap, boards).read_bytes()
    check_frame(boards, payload)
    derived, rpw = cohort_from_payload(payload)
    assert rpw == {"day": 30, "week": 30, "month": 30, "allTime": 30}
    assert [d["address"] for d in derived] == [a["address"] for a in doc["cohort"]["addresses"]]
    assert derived[0]["account_value"] == Decimal(doc["cohort"]["addresses"][0]["account_value"])


def test_cohort_2_builds_and_its_root_is_unchanged_under_the_frame_gates():
    pipeline, events, _i, _d, refused, _l = runner.build(C2_CAP)
    assert refused == [] and len(events) == 2
    assert pipeline.event_log.root(2).hex() == \
        "3e23db83c08e3c1360d5e7a71c92e87d472a1820348ac4b4a3fd8fd8a12b5e4f"


def test_synthetic_fixture_passes_the_frame(tmp_path):
    cap = make_capture(tmp_path)
    _p, events, _i, _d, refused, _l = runner.build(cap)
    assert refused == [] and len(events) == 6


def test_s87_a_planted_address_with_valid_pages_refuses_the_capture_whole(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    fills = [_page([_fill(T0 + 7, "ETH", "B", "100", "1", "0", "0.0", "0.1", "0xd1", 900),
                    _fill(T0 + 8, "ETH", "A", "200", "1", "1", "100.0", "0.1", "0xd2", 901)])]
    funding = [_page([])]
    (tmp_path / f"hl_fills_{A4}.jsonl.gz").write_bytes(_gz(fills))
    (tmp_path / f"hl_funding_{A4}.jsonl.gz").write_bytes(_gz(funding))
    doc["cohort"]["addresses"].append(
        {"address": A4, "first_window": "week", "first_rank": 3, "account_value": "1",
         "displayed": {"week": {"rank": 3, "pnl": "1", "roi": "0.1", "vlm": "1"}}})
    doc["rows"].append({"address": A4, "fills_file": f"hl_fills_{A4}.jsonl.gz", "fills_pages": _pins(fills),
                        "funding_file": f"hl_funding_{A4}.jsonl.gz", "funding_pages": _pins(funding)})
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S87: 4 addresses declared, 3 derived"):
        runner.build(cap)


def test_s87_a_changed_displayed_figure_or_a_reordered_cohort_is_refused(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["cohort"]["addresses"][0]["displayed"]["week"]["pnl"] = "9000"
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S87: cohort\.addresses\[0\] \(" + A1):
        runner.build(cap)
    doc = _load(make_capture(tmp_path))
    doc["cohort"]["addresses"][1], doc["cohort"]["addresses"][2] = \
        doc["cohort"]["addresses"][2], doc["cohort"]["addresses"][1]
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S87: cohort\.addresses\[1\] \(" + A3):
        runner.build(cap)


def test_s88_a_window_moved_one_day_later_is_refused(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["window"]["t0_ms"] = T0 + DAY_MS
    doc["window"]["t1_ms"] = T1 + DAY_MS
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S88: window\.t0_ms declared"):
        runner.build(cap)


def test_s88_a_window_shortened_to_seven_days_on_cohort_1_is_refused(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["window"]["t1_ms"] = T1 - DAY_MS
    doc["window"]["days"] = 7
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S88: window\.t1_ms declared"):
        runner.build(cap)


def test_s88_a_later_cohort_declaring_eight_days_is_refused(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["cohort"]["cohort_date"] = "2026-11-03"
    doc["cohort"]["observed_ms"] = 1793688589648
    t0 = 1793750400000
    doc["window"] = {"t0_ms": t0, "t1_ms": t0 + 8 * DAY_MS - 1, "days": 8,
                     "started": True, "complete": True}
    doc["as_of"]["as_of_date"] = "2026-11-12"
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S88: window\.t1_ms declared .* for cohort 2026-11-03"):
        runner.build(cap)


def test_s88_complete_declared_false_on_a_closed_window_is_refused(tmp_path):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["window"]["complete"] = False
    _save(cap, doc)
    with pytest.raises(AdapterError, match=r"S88: window\.complete declared False, the rule's is True"):
        runner.build(cap)


def test_s89_one_byte_of_the_payload_changed_with_the_pin_left_as_it_was(tmp_path):
    cap = make_capture(tmp_path)
    board = tmp_path / "board.json"
    raw = board.read_bytes()
    assert b'"pnl": "9"' in raw
    board.write_bytes(raw.replace(b'"pnl": "9"', b'"pnl": "8"', 1))
    with pytest.raises(AdapterError, match=r"S89: the payload's bytes hash to"):
        runner.build(cap)
    board.unlink()
    with pytest.raises(AdapterError, match=r"S89: payload 'board.json' not found"):
        runner.build(cap)


def test_r101_a_consistent_forgery_is_a_different_cohort_caught_by_the_pins_not_the_grader(tmp_path):
    """The boundary, stated: payload + pin + cohort rewritten together pass the run-time
    frame (they are internally consistent); provenance is the pinned-file gates' job."""
    import hashlib
    cap = make_capture(tmp_path)
    board = tmp_path / "board.json"
    raw = board.read_bytes().replace(b'"pnl": "9"', b'"pnl": "8"', 1)
    board.write_bytes(raw)
    doc = _load(cap)
    doc["cohort"]["payload_sha256"] = hashlib.sha256(raw).hexdigest()
    doc["cohort"]["addresses"][0]["displayed"]["week"]["pnl"] = "8"
    _save(cap, doc)
    _p, events, _i, _d, refused, _l = runner.build(cap)
    assert refused == [] and len(events) == 6


def test_the_cli_refuses_whole_writes_no_run_file_and_exits_1(tmp_path, capsys):
    cap = make_capture(tmp_path)
    doc = _load(cap)
    doc["window"]["t0_ms"] = T0 + DAY_MS
    doc["window"]["t1_ms"] = T1 + DAY_MS
    _save(cap, doc)
    out = tmp_path / "planted.ri"
    rc = runner.main(["--capture", str(cap), "--out", str(out)])
    text = capsys.readouterr().out
    assert rc == 1 and not out.exists()
    assert "REFUSED WHOLE: S88: window.t0_ms declared" in text
    assert text.rstrip().endswith("AGENT-RECORD ARENA RUN: REFUSED")


def test_r96_the_new_code_reads_no_clock_no_network_no_log():
    src = (Path(runner.__file__).parent / "adapters" / "agent_arena.py").read_text(encoding="utf-8")
    for banned in ("time.time(", "datetime.now(", "utcnow(", "import urllib", "import random",
                   "import socket", "import subprocess"):
        assert banned not in src
