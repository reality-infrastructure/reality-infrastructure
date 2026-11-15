"""PREREG A47 gates (P42): a second payload the frame derives a cohort from, the exchange's
own leaderboard file (R218), and cohort 2026-11-15 pinned from it. The known answers of A47
on the real pins; the refusals (S87, S89, S128) on a small synthetic file; the two earlier
cohorts' events untouched (S129). Offline; no network, no clock.
"""
from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import (
    EXCHANGE_CLAIMANT, PAYLOAD_KIND_HL, VENUE_CLAIMANT, check_frame, cohort_from_leaderboard,
    cohort_from_payload, hundred_from_leaderboard, parse_arena_capture, sha256_hex,
)
from rights_events.adapters.common import AdapterError

FIX = runner._FIXTURES
ARENA = FIX / "arena"
C3 = ARENA / "2026-11-15"
PAYLOAD = C3 / "hl_leaderboard_2026-11-15.json"
CAPTURE = C3 / "capture_ARENA_2026-11-15_2026-11-15.json"
PAYLOAD_SHA = "3d46d4dac7fe27fc97d02da105f9c1153ae41c29128b0770fbbd1b7992f485e3"
PRIOR = [FIX / "gdex_hl_top_traders_by_pnl_2026-10-25.json",
         ARENA / "2026-11-03" / "gdex_hl_top_traders_by_pnl_2026-11-03.json"]
RECORD = "0x9f976123e7c48952be487664b8130aad144b7f23"
FIRST_OF_HUNDRED = "0x5b5d51203a0f9079f8aeb098a6523a13f298c060"
LAST_OF_HUNDRED = "0x9dead8fffcbf130e7658f672d2c081d91178d617"
FIRST_OF_COHORT = "0x15a4f009bb324a3fb9e36137136b201e3fe0dfdb"

_spec = importlib.util.spec_from_file_location("capture_arena_from_leaderboard",
                                               ARENA / "capture_arena_from_leaderboard.py")
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture(scope="module")
def real():
    raw = PAYLOAD.read_bytes()
    return {"raw": raw, "hundred": hundred_from_leaderboard(raw),
            "doc": json.loads(CAPTURE.read_text(encoding="utf-8"))}


# ---- the known answers on the real pins ---------------------------------------------------

def test_s130_the_pinned_payload_is_the_observation_a47_names(real):
    assert len(real["raw"]) == 38_796_356
    assert sha256_hex(real["raw"]) == PAYLOAD_SHA
    assert b"\r" not in real["raw"]
    assert len(json.loads(real["raw"].decode("utf-8"))["leaderboardRows"]) == 47_487


def test_the_hundred_is_the_week_ranking_of_the_files_own_strings(real):
    h = real["hundred"]
    assert len(h) == 100 and [e["first_rank"] for e in h] == list(range(1, 101))
    assert h[0]["address"] == FIRST_OF_HUNDRED and h[-1]["address"] == LAST_OF_HUNDRED
    assert h[0]["displayed"]["week"]["pnl"] == Decimal("87867537.7880669981")
    assert h[-1]["displayed"]["week"]["pnl"] == Decimal("1206920.632954")
    pnls = [e["displayed"]["week"]["pnl"] for e in h]
    assert pnls == sorted(pnls, reverse=True)
    assert all(set(e["displayed"]) == {"week"} and e["first_window"] == "week" for e in h)


def test_r220_excluded_is_exactly_what_the_two_earlier_cohorts_hold(real):
    held = set()
    for p in PRIOR:
        cohort, _ = cohort_from_payload(p.read_bytes())
        held |= {a["address"].lower() for a in cohort}
    want = [e["address"] for e in real["hundred"] if e["address"].lower() in held]
    co = real["doc"]["cohort"]
    assert co["excluded"] == want and len(want) == 31
    assert [q["sha256"] for q in co["prior_payloads"]] == [sha256_hex(p.read_bytes()) for p in PRIOR]
    assert builder.excluded_from(real["raw"], [p.read_bytes() for p in PRIOR]) == want
    assert not held & {a["address"].lower() for a in co["addresses"]}


def test_the_committed_capture_is_the_derivation_and_the_window_is_the_rules(real):
    doc, boards = parse_arena_capture(CAPTURE.read_text(encoding="utf-8"))
    check_frame(boards, real["raw"])
    c = boards.claim
    assert boards.claimant == EXCHANGE_CLAIMANT and c["payload_kind"] == PAYLOAD_KIND_HL
    assert c["addresses"] == 69 and len(c["excluded"]) == 31
    assert c["rows_per_window"] == {"day": 0, "week": 100, "month": 0, "allTime": 0}
    first, last = doc["cohort"]["addresses"][0], doc["cohort"]["addresses"][-1]
    assert (first["address"], first["first_rank"]) == (FIRST_OF_COHORT, 9)
    assert first["displayed"]["week"] == {"rank": 9, "pnl": "13183570.8353259992",
                                          "roi": "1.0140805972", "vlm": "0.0"}
    assert (last["address"], last["first_rank"]) == (LAST_OF_HUNDRED, 100)
    w = c["window"]
    assert (w["t0_ms"], w["t1_ms"], w["days"]) == (1794787200000, 1795391999999, 7)
    assert (w["t0_date"], w["t1_date"]) == ("2026-11-16", "2026-11-22")
    assert w["started"] is False and w["complete"] is False
    assert c["observed_ms"] == 1794710961000 and doc["rows"] == []


def test_the_grader_accepts_the_observation_and_names_the_exchange(tmp_path, capsys):
    """Known answer 3, run by the unmodified command into a temporary directory. The
    observation day's arena output is NOT committed (A47.1): the feed and the board entry
    re-derive their newest pin over every cohort directory and refuse an arena file dated
    after their own as-of (S99, S102); the first committed output is the first graded day's."""
    run = tmp_path / "run.ri"
    assert runner.main(["--capture", str(CAPTURE), "--out", str(run),
                        "--arena-out", str(tmp_path / "arena")]) == 0
    assert "AGENT-RECORD ARENA RUN: OK" in capsys.readouterr().out
    arena = json.loads((tmp_path / "arena.json").read_text(encoding="utf-8"))
    assert arena["cohort_date"] == "2026-11-15" and arena["as_of"] == "2026-11-15"
    assert arena["counts"] == {"FULL": 0, "PARTIAL": 0, "NONE": 0, "REFUSED": 0}
    assert arena["venue"]["name"] == runner.EXCHANGE_NAME and "gdex" not in arena["venue"]["name"].lower()
    assert arena["venue"]["addresses"] == 69 and arena["venue"]["payload_sha256"] == PAYLOAD_SHA
    assert "four windows" not in (tmp_path / "arena.html").read_text(encoding="utf-8")
    ok, _report = runner.verify_run(run)
    assert ok
    assert not list(C3.glob("arena_*")) or min(p.name for p in C3.glob("arena_*.json")) > "arena_2026-11-15_2026-11-15.json"


def test_r221_the_tapes_cohort_file_is_the_69_and_the_record(real):
    tape = json.loads((C3 / "cohort_2026-11-15.json").read_text(encoding="utf-8"))
    addrs = [a["address"].lower() for a in real["doc"]["cohort"]["addresses"]]
    assert tape["addresses"] == addrs + [RECORD] and len(tape["addresses"]) == 70
    assert (tape["cohort_date"], tape["t0_ms"], tape["t1_ms"]) == ("2026-11-15", 1794787200000, 1795391999999)
    assert tape["payload_sha256"] == PAYLOAD_SHA


def test_s129_the_earlier_cohorts_events_carry_no_new_key_and_keep_their_claimant():
    for cap in (ARENA / "2026-10-25" / "capture_ARENA_2026-10-25_2026-11-03.json",
                ARENA / "2026-11-03" / "capture_ARENA_2026-11-03_2026-11-03.json"):
        _doc, boards = parse_arena_capture(cap.read_text(encoding="utf-8"))
        assert boards.claimant == VENUE_CLAIMANT
        assert "payload_kind" not in boards.claim and "excluded" not in boards.claim
        assert runner.listing_name(boards) == runner.VENUE_NAME
        check_frame(boards, runner.payload_path_for(cap, boards).read_bytes())


# ---- the refusals, on a small synthetic file ----------------------------------------------

def _addr(i: int) -> str:
    return "0x" + f"{i:040x}"


def _file(n: int = 105, dup: bool = False, drop_week: int | None = None) -> bytes:
    rows = []
    for i in range(1, n + 1):
        perf = [[w, {"pnl": f"{(n - i) * 10}.5", "roi": "0.01", "vlm": "1000.0"}]
                for w in ("day", "week", "month", "allTime")]
        if drop_week == i:
            perf = [p for p in perf if p[0] != "week"]
        rows.append({"ethAddress": _addr(i), "accountValue": f"{i}000.25",
                     "windowPerformances": perf, "prize": 0, "displayName": None})
    if dup:
        rows.append(dict(rows[0]))
    return json.dumps({"leaderboardRows": rows}).encode("utf-8")


def _capture(payload: bytes, excluded: list[str]) -> dict:
    cohort, rpw = cohort_from_leaderboard(payload, excluded)
    return {
        "kind": "agent_record_arena_capture", "synthetic": True,
        "actor": {"actor_id": RECORD},
        "cohort": {"cohort_date": "2026-11-15", "observed_ms": 1794710961000,
                   "payload_kind": PAYLOAD_KIND_HL, "payload_file": "p.json",
                   "payload_sha256": sha256_hex(payload), "source_url": builder.SOURCE_URL,
                   "excluded": excluded, "rows_per_window": rpw,
                   "addresses": [builder._entry(e) for e in cohort]},
        "window": {"t0_ms": 1794787200000, "t1_ms": 1795391999999, "days": 7,
                   "started": False, "complete": False},
        "as_of": {"as_of_date": "2026-11-15", "api": "x"}, "paper": {"files": []}, "rows": [],
    }


def _frame(doc: dict, payload: bytes) -> None:
    _d, boards = parse_arena_capture(json.dumps(doc))
    check_frame(boards, payload)


def test_synthetic_file_derives_and_passes_and_ties_break_by_address():
    payload = _file()
    h = hundred_from_leaderboard(payload)
    assert [e["address"] for e in h] == [_addr(i) for i in range(1, 101)]
    doc = _capture(payload, [_addr(2), _addr(50)])
    assert len(doc["cohort"]["addresses"]) == 98
    _frame(doc, payload)
    tie = json.loads(payload)
    for r in tie["leaderboardRows"][:3]:
        r["windowPerformances"][1][1]["pnl"] = "999999"
    tied = hundred_from_leaderboard(json.dumps(tie).encode("utf-8"))
    assert [e["address"] for e in tied[:3]] == [_addr(1), _addr(2), _addr(3)]


def test_s87_a_planted_address_a_dropped_one_or_a_changed_figure_is_refused():
    payload = _file()
    doc = _capture(payload, [_addr(2)])
    planted = json.loads(json.dumps(doc))
    planted["cohort"]["addresses"].append(
        {"address": _addr(104), "first_window": "week", "first_rank": 104, "account_value": "1",
         "displayed": {"week": {"rank": 104, "pnl": "1", "roi": "0", "vlm": "0"}}})
    with pytest.raises(AdapterError, match="S87"):
        _frame(planted, payload)
    dropped = json.loads(json.dumps(doc))
    dropped["cohort"]["addresses"].pop(10)
    with pytest.raises(AdapterError, match="S87"):
        _frame(dropped, payload)
    changed = json.loads(json.dumps(doc))
    changed["cohort"]["addresses"][0]["displayed"]["week"]["pnl"] = "1040.6"
    with pytest.raises(AdapterError, match="S87"):
        _frame(changed, payload)


def test_s128_an_excluded_address_outside_the_hundred_and_a_malformed_file_are_refused():
    payload = _file()
    doc = _capture(payload, [_addr(2)])
    doc["cohort"]["excluded"] = [_addr(104)]
    with pytest.raises(AdapterError, match="S128"):
        _frame(doc, payload)
    with pytest.raises(AdapterError, match="S128"):
        hundred_from_leaderboard(_file(dup=True))
    with pytest.raises(AdapterError, match="S128"):
        hundred_from_leaderboard(_file(drop_week=7))
    with pytest.raises(AdapterError, match="S128"):
        hundred_from_leaderboard(b'{"isSuccess": true, "topTraders": {}}')


def test_s89_one_digit_of_the_payload_changed_with_the_pin_left_as_it_was():
    payload = _file()
    doc = _capture(payload, [])
    with pytest.raises(AdapterError, match="S89"):
        _frame(doc, payload.replace(b"1000.25", b"1000.26", 1))


def test_an_unknown_payload_kind_or_a_capture_without_its_excluded_list_is_refused():
    payload = _file()
    doc = _capture(payload, [])
    bad = json.loads(json.dumps(doc))
    bad["cohort"]["payload_kind"] = "something_else"
    with pytest.raises(AdapterError, match="R218"):
        _frame(bad, payload)
    bad = json.loads(json.dumps(doc))
    del bad["cohort"]["excluded"]
    with pytest.raises(AdapterError, match="excluded"):
        _frame(bad, payload)


def test_the_builder_reads_no_clock_and_no_network():
    src = (ARENA / "capture_arena_from_leaderboard.py").read_text(encoding="utf-8")
    for needle in ("time.time", "urllib", "import requests", "socket", "http.client",
                   "datetime.now", "utcnow"):
        assert needle not in src, needle
