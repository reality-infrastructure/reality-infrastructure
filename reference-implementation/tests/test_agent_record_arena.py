"""PREREG A18 gates on THE ARENA's code (P14): the adapter and runner over a synthetic,
offline capture — the founder's arithmetic (R89), coverage FULL/PARTIAL/NONE (R90), the
ranking (R91), the honeypot gates (R95: a one-digit change in a pinned page refuses the
row; a changed byte of a run file fails --verify), determinism, and R96 (no input but
files). The real pins (A18.1/A18.2) get their own gates once the captures are committed.
Nothing here reads the network or the clock.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import (
    FILLS_CLAIMANT, GRADER_CLAIMANT, STATUS_FULL, STATUS_NONE, STATUS_PARTIAL,
    VENUE_CLAIMANT, coverage, parse_arena_capture, settle,
)
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
A1 = "0x1111111111111111111111111111111111111111"
A2 = "0x2222222222222222222222222222222222222222"
A3 = "0x3333333333333333333333333333333333333333"
OBS_MS = 1792906235038          # 2026-10-25
T0 = 1792972800000              # 2026-10-26 00:00:00.000Z
T1 = 1793664000000 - 1          # 2026-11-02 23:59:59.999Z
RUN_FILES = [runner._FIXTURES / n for n in (
    "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri",
    "run_LIVE_2026-10-24_pv_e1849abce514440c.ri")]


def _fill(t, coin, side, px, sz, start, closed, fee, h, tid):
    return {"coin": coin, "px": px, "sz": sz, "side": side, "time": t, "startPosition": start,
            "dir": "Open Long" if side == "B" else "Close Long", "closedPnl": closed, "hash": h,
            "oid": tid, "crossed": True, "fee": fee, "feeToken": "USDC", "tid": tid}


def _funding(t, coin, usdc):
    return {"time": t, "hash": "0x" + "0" * 64,
            "delta": {"type": "funding", "coin": coin, "usdc": usdc, "szi": "0.00014",
                      "fundingRate": "0.00001", "nSamples": None}}


def _page(items) -> bytes:
    return json.dumps(items, separators=(",", ":")).encode("utf-8")


def _gz(pages: list[bytes]) -> bytes:
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g:
        for p in pages:
            g.write(p + b"\n")
    return bio.getvalue()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _pins(pages: list[bytes]) -> list[dict]:
    return [{"line": i, "sha256": _sha(p), "bytes": len(p), "items": len(json.loads(p))}
            for i, p in enumerate(pages)]


def make_capture(tmp: Path, *, a1_items=2000) -> Path:
    """Three cohort addresses + the operator: A1 FULL (two pairs), A2 NONE, A3 PARTIAL (a
    full first page starting 3 days late); the operator = Day 6's real pair figures."""
    board = {"isSuccess": True, "topTraders": {
        "day": [], "week": [{"ethAddress": A1, "accountValue": "100", "windowPerformances": [["week", {"pnl": "9", "roi": "0.1", "vlm": "50"}]]},
                            {"ethAddress": A2, "accountValue": "200", "windowPerformances": [["week", {"pnl": "8", "roi": "0.1", "vlm": "40"}]]}],
        "month": [{"ethAddress": A3, "accountValue": "300", "windowPerformances": [["month", {"pnl": "7", "roi": "0.1", "vlm": "30"}]]},
                  {"ethAddress": A1, "accountValue": "100", "windowPerformances": [["month", {"pnl": "6", "roi": "0.1", "vlm": "20"}]]}],
        "allTime": []}}
    raw = json.dumps(board).encode("utf-8")
    (tmp / "board.json").write_bytes(raw)
    pages = {}
    # A1: open+close twice inside the window, one fill before it (ignored)
    a1 = [_fill(T0 - 5, "ETH", "B", "100", "1", "0", "0.0", "0.1", "0xa0", 1),
          _fill(T0 + 1000, "ETH", "B", "100", "1", "0", "0.0", "0.1", "0xa1", 2),
          _fill(T0 + 2000, "ETH", "A", "110", "1", "1", "10.0", "0.1", "0xa2", 3),
          _fill(T0 + 3000, "BTC", "B", "100", "2", "0", "0.0", "0.2", "0xa3", 4),
          _fill(T0 + 4000, "BTC", "A", "99", "1", "2", "-1.0", "0.2", "0xa4", 5)]
    pages[A1] = ([_page(a1[:3]), _page(a1[3:])], [_page([_funding(T0 + 10, "ETH", "-0.5"), _funding(T1 + 1, "ETH", "9")])])
    pages[A2] = ([_page([])], [_page([])])
    late = T0 + 3 * 86_400_000
    a3 = [_fill(late + i, "SOL", "B" if i % 2 == 0 else "A", "10", "1", "0" if i % 2 == 0 else "1",
                "0.0" if i % 2 == 0 else "0.5", "0.01", f"0xc{i}", 100 + i) for i in range(a1_items)]
    pages[A3] = ([_page(a3)], [_page([])])
    op = [_fill(1793078284458, "BTC", "B", "79776.0", "0.00014", "0.0", "0.0", "0.010408", "0xec47", 7),
          _fill(1793160808256, "BTC", "A", "80957.0", "0.00014", "0.00014", "0.16534", "0.010562", "0x3c12", 8)]
    pages[ACTOR] = ([_page(op)], [_page([_funding(1793080800032, "BTC", "-0.003224")])])
    rows = []
    for addr, (fp, qp) in pages.items():
        (tmp / f"hl_fills_{addr}.jsonl.gz").write_bytes(_gz(fp))
        (tmp / f"hl_funding_{addr}.jsonl.gz").write_bytes(_gz(qp))
        rows.append({"address": addr, "fills_file": f"hl_fills_{addr}.jsonl.gz", "fills_pages": _pins(fp),
                     "funding_file": f"hl_funding_{addr}.jsonl.gz", "funding_pages": _pins(qp)})
    doc = {
        "kind": "agent_record_arena_capture", "synthetic": True,
        "actor": {"actor_id": ACTOR},
        "cohort": {"cohort_date": "2026-10-25", "observed_ms": OBS_MS, "payload_file": "board.json",
                   "payload_sha256": _sha(raw), "source_url": "https://trade-api.gemach.io/v1/hl/top_traders_by_pnl",
                   "rows_per_window": {"day": 0, "week": 2, "month": 2, "allTime": 0},
                   "addresses": [
                       {"address": A1, "first_window": "week", "first_rank": 1, "account_value": "100",
                        "displayed": {"week": {"rank": 1, "pnl": "9", "roi": "0.1", "vlm": "50"},
                                      "month": {"rank": 2, "pnl": "6", "roi": "0.1", "vlm": "20"}}},
                       {"address": A2, "first_window": "week", "first_rank": 2, "account_value": "200",
                        "displayed": {"week": {"rank": 2, "pnl": "8", "roi": "0.1", "vlm": "40"}}},
                       {"address": A3, "first_window": "month", "first_rank": 1, "account_value": "300",
                        "displayed": {"month": {"rank": 1, "pnl": "7", "roi": "0.1", "vlm": "30"}}}]},
        "window": {"t0_ms": T0, "t1_ms": T1, "days": 8, "started": True, "complete": True},
        "as_of": {"as_of_date": "2026-11-03", "api": "https://api.hyperliquid.xyz/info"},
        "paper": {"files": []},
        "rows": rows,
    }
    path = tmp / "capture_ARENA_2026-10-25_2026-11-03.json"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def test_settle_is_the_founders_arithmetic():
    fills = [_fill(T0 + 1, "ETH", "B", "100", "1", "0", "0.0", "0.1", "0x1", 1),
             _fill(T0 + 2, "ETH", "A", "110", "1", "1", "10.0", "0.1", "0x2", 2),
             _fill(T0 + 2, "ETH", "A", "110", "1", "1", "10.0", "0.1", "0x2", 2),   # a duplicate page item
             _fill(T1 + 1, "ETH", "B", "100", "1", "0", "0.0", "0.1", "0x3", 3)]    # outside the window
    s = settle(fills, [_funding(T0 + 5, "ETH", "-0.25"), _funding(T0 - 1, "ETH", "99")], T0, T1, "t")
    assert s["fills"] == 2 and s["closed_pnl"] == Decimal("10.0") and s["fees"] == Decimal("0.2")
    assert s["realized_ex_funding"] == Decimal("9.8") and s["funding"] == Decimal("-0.25")
    assert s["net_with_funding"] == Decimal("9.55") and s["funding_rows"] == 1
    assert s["open_at_window_end"] == {} and s["first_tx"] == "0x1" and s["last_tx"] == "0x2"
    assert sum((d["net"] for d in s["daily"]), Decimal(0)) == Decimal("9.55")


def test_coverage_rule():
    assert coverage(0, [{"items": 0}], None, T0)[0] == STATUS_NONE
    assert coverage(5, [{"items": 5}], T0 + 1, T0)[0] == STATUS_FULL
    assert coverage(2000, [{"items": 2000}], T0 + 3 * 86_400_000, T0)[0] == STATUS_PARTIAL
    assert coverage(2000, [{"items": 2000}], T0 + 1000, T0)[0] == STATUS_FULL
    assert coverage(10000, [{"items": 2000}] * 5, T0 + 1, T0)[0] == STATUS_PARTIAL


def test_window_must_open_after_observation(tmp_path):
    cap = make_capture(tmp_path)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    doc["window"]["t0_ms"] = OBS_MS - 1
    with pytest.raises(AdapterError, match="AFTER the observation"):
        parse_arena_capture(json.dumps(doc))


def test_arena_run_grades_every_address_and_ranks_full_only(tmp_path):
    cap = make_capture(tmp_path)
    pipeline, events, indices, _doc, refused, _loaded = runner.build(cap, RUN_FILES)
    assert refused == []
    boards = next(e for e in events if e.claimant == VENUE_CLAIMANT)
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    settled = {e.claim["address"]: e for e in events if e.claimant == FILLS_CLAIMANT}
    assert boards.ep_type is EPType.SELF_ASSERTED and boards.claim["addresses"] == 3
    assert boards.claim["addresses_verbatim"][0]["displayed"]["week"]["pnl"] == Decimal("9")
    assert len(settled) == 4 and all(e.ep_type is EPType.THIRD_PARTY_ATTESTED for e in settled.values())
    assert settled[A1].claim["coverage"] == STATUS_FULL
    assert settled[A1].claim["realized_ex_funding"] == Decimal("8.4")        # 9.0 closed - 0.6 fees
    assert settled[A1].claim["net_with_funding"] == Decimal("7.9")           # + (-0.5); the 9 is outside
    assert settled[A1].claim["open_at_window_end"] == {"BTC": Decimal("1")}
    assert settled[A2].claim["coverage"] == STATUS_NONE
    assert settled[A3].claim["coverage"] == STATUS_PARTIAL
    c = ranking.claim
    assert [r["address"] for r in c["ranked"]] == [A1]
    assert {u["address"]: u["status"] for u in c["unranked"]} == {A2: STATUS_NONE, A3: STATUS_PARTIAL}
    assert c["counts"] == {"FULL": 1, "PARTIAL": 1, "NONE": 1, "REFUSED": 0}
    assert c["median_net_full"] == Decimal("7.9") and c["share_positive_full"] == Decimal(1)
    rr = c["record_row"]
    assert rr["address"] == ACTOR and rr["realized_ex_funding"] == Decimal("0.144370")
    assert rr["funding"] == Decimal("-0.003224") and rr["net_with_funding"] == Decimal("0.141146")
    assert rr["settled_pairs_on_record"] == {"PAPER": 1, "LIVE": 1} and len(rr["tx_hashes"]) == 2
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert not [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices
    assert runner.trace_ranking(ranking, list(settled.values())) == []
    assert len(pipeline.event_log) == 6


def test_run_is_deterministic_and_render_is_pure(tmp_path):
    cap = make_capture(tmp_path)
    p1, e1, _i, d1, _r, _l = runner.build(cap, RUN_FILES)
    p2, e2, _i, d2, _r, _l = runner.build(cap, RUN_FILES)
    f1, f2 = tmp_path / "a.ri", tmp_path / "b.ri"
    p1.save(f1)
    p2.save(f2)
    assert f1.read_bytes() == f2.read_bytes()
    root = p1.event_log.root(len(p1.event_log)).hex()
    m1 = runner.render_arena(d1, e1, "x.ri", root)
    m2 = runner.render_arena(d2, e2, "x.ri", root)
    assert runner.arena_json(m1) == runner.arena_json(m2)
    assert runner.render_html(m1) == runner.render_html(m2)
    html = runner.render_html(m1)
    assert "<svg" in html and ACTOR in html and A2 in html
    assert m1["rows"][0]["net_with_funding"] == "7.9" and m1["record_row"]["net_with_funding"] == "0.141146"


def test_honeypot_one_digit_in_a_pinned_page_refuses_the_row(tmp_path):
    cap = make_capture(tmp_path)
    path = tmp_path / f"hl_fills_{A1}.jsonl.gz"
    pages = runner.read_pages(path)
    tampered = pages[0].replace(b'"closedPnl":"10.0"', b'"closedPnl":"19.0"')
    assert tampered != pages[0]
    path.write_bytes(_gz([tampered, pages[1]]))
    _p, events, _i, _d, refused, _l = runner.build(cap, RUN_FILES)
    assert [r["address"] for r in refused] == [A1]
    assert "S84" in refused[0]["reason"]
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    assert ranking.claim["counts"]["REFUSED"] == 1 and ranking.claim["ranked"] == []
    assert ranking.claim["refused"][0]["address"] == A1


def test_honeypot_a_changed_byte_in_the_run_file_fails_verify(tmp_path):
    cap = make_capture(tmp_path)
    pipeline, _e, _i, _d, _r, _l = runner.build(cap, RUN_FILES)
    out = tmp_path / "run.ri"
    data = pipeline.save(out)
    ok, _ = runner.verify_run(out)
    assert ok
    i = data.index(b'"__v":"') + 7 + 40          # a byte inside the first logged entry
    swap = b"A" if data[i:i + 1] != b"A" else b"B"
    out.write_bytes(data[:i] + swap + data[i + 1:])
    ok, report = runner.verify_run(out)
    assert not ok and "FAILED" in report


def test_runner_main_end_to_end(tmp_path, capsys):
    cap = make_capture(tmp_path)
    out = tmp_path / "run.ri"
    argv = ["--capture", str(cap), "--out", str(out), "--arena-out", str(tmp_path / "arena")]
    for p in RUN_FILES:
        argv += ["--run-file", str(p)]
    assert runner.main(argv) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD ARENA RUN: OK" in text and "PASS  C5" in text
    assert (tmp_path / "arena.html").exists() and (tmp_path / "arena.json").exists()
    ok, report = runner.verify_run(out)
    assert ok and "reloaded 6 events" in report


def test_r96_the_runner_takes_only_files():
    import inspect
    src = inspect.getsource(runner) + inspect.getsource(__import__("rights_events.adapters.agent_arena", fromlist=["x"]))
    for forbidden in ("import urllib", "import requests", "import socket", "time.time(",
                      "datetime.now(", "import random", "from random", "import time"):
        assert forbidden not in src, forbidden
