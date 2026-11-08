"""A29 / P23 gates: THE AI BOARD ENTRY.

R123  pure function of pinned captures, pages and marks; S101 latest byte-equal; no network / clock
R124  the record's rows: a trade = a round trip (startPosition 0 -> position 0), P&L = sum closedPnl - sum fee,
      FEES = all fills' fees, open trips counted never valued; S102 a page off its pin refuses the row
R125  forks and controls from pinned marks, void days excluded, bps never USD
R126  ROI not computed on every row; rank within a unit class, among rows with >= 1 trade, controls included
Known answers on the real pins: record cohort 2026-10-25 = 2 trades, 1 win, +0.144370 / -0.067163, fees 0.041793,
total 0.073533 USD; cohort 2026-11-03 not graded (pages not on the branch); population as of 2026-11-08.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import arena_ai_board as ab
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_SRC = _ROOT / "rights_events" / "arena_ai_board.py"


def _fill(t, side, sz, start, pnl, fee, h):
    return {"coin": "BTC", "px": "100", "sz": sz, "side": side, "time": t, "startPosition": start, "dir": "x",
            "closedPnl": pnl, "hash": h, "oid": 1, "crossed": True, "fee": fee, "builderFee": "0", "tid": t, "feeToken": "USDC"}


def test_r124_round_trips():
    fills = [_fill(1, "B", "1", "0", "0", "0.1", "a"), _fill(2, "B", "1", "1", "0", "0.1", "b"),       # open in two fills
             _fill(3, "A", "2", "2", "5", "0.2", "c"),                                                   # close -> one trip, 3 fills
             _fill(4, "A", "1", "0", "0", "0.1", "d"), _fill(5, "B", "1", "-1", "-0.5", "0.1", "e"),    # a short trip
             _fill(6, "B", "1", "0", "0", "0.1", "f")]                                                  # left open
    trips = ab.round_trips(fills)
    assert len(trips) == 3 and trips[0]["closed"] and trips[0]["fills"] == 3 and trips[0]["net"] == Decimal("4.6")
    assert trips[1]["closed"] and trips[1]["net"] == Decimal("-0.7") and trips[2]["closed"] is False and trips[2]["net"] is None


def _write_page(path: Path, pages: list[list[dict]]) -> list[dict]:
    lines = [json.dumps(p, separators=(",", ":")).encode("utf-8") for p in pages]
    with gzip.open(path, "wb") as f:
        f.write(b"\n".join(lines) + b"\n")
    return [{"line": i, "sha256": hashlib.sha256(l).hexdigest(), "bytes": len(l), "items": len(pages[i])} for i, l in enumerate(lines)]


def _synthetic(tmp: Path, tamper=False):
    arena = tmp / "arena"
    c = arena / "2026-10-01"
    c.mkdir(parents=True)
    t0, t1 = 1_000_000, 2_000_000
    fills = [_fill(1_100_000, "B", "1", "0", "0", "0.1", "0xa"), _fill(1_200_000, "A", "1", "1", "2.0", "0.1", "0xb"),
             _fill(1_300_000, "B", "1", "0", "0", "0.1", "0xc"), _fill(1_400_000, "A", "1", "1", "-1.0", "0.1", "0xd"),
             _fill(1_500_000, "B", "1", "0", "0", "0.1", "0xe")]                                        # open at window end
    funding = [{"time": 1_250_000, "hash": "0x0", "delta": {"type": "funding", "coin": "BTC", "usdc": "-0.05"}}]
    fp = _write_page(c / "hl_fills_0xrec.jsonl.gz", [fills])
    up = _write_page(c / "hl_funding_0xrec.jsonl.gz", [funding])
    if tamper:
        with gzip.open(c / "hl_fills_0xrec.jsonl.gz", "wb") as f:
            f.write(json.dumps(fills[:4], separators=(",", ":")).encode("utf-8") + b"\n")
    total = Decimal("2.0") - Decimal("1.0") - Decimal("0.5") + Decimal("-0.05")
    (c / "capture_ARENA_2026-10-01_2026-10-10.json").write_text(json.dumps({
        "as_of_date": "2026-10-10", "rows": [{"address": "0xrec", "fills_file": "hl_fills_0xrec.jsonl.gz", "fills_pages": fp,
                                               "funding_file": "hl_funding_0xrec.jsonl.gz", "funding_pages": up}]}), encoding="utf-8")
    (c / "arena_2026-10-01_2026-10-10.json").write_text(json.dumps({
        "as_of": "2026-10-10", "window": {"t0_ms": t0, "t1_ms": t1, "t0_date": "2026-10-02", "t1_date": "2026-10-09", "complete": True},
        "rows": [], "record_row": {"address": "0xrec", "net_with_funding": format(total, "f")}, "arena_run": {"root": "r"}, "settled_rule": "x"}), encoding="utf-8")
    # a second cohort whose pages are not on the branch
    c2 = arena / "2026-10-11"
    c2.mkdir()
    (c2 / "capture_ARENA_2026-10-11_2026-10-12.json").write_text(json.dumps({"as_of_date": "2026-10-12", "rows": [
        {"address": "0xrec", "fills_file": "hl_fills_0xrec.jsonl.gz", "fills_pages": [], "funding_file": "hl_funding_0xrec.jsonl.gz", "funding_pages": []}]}), encoding="utf-8")
    (c2 / "arena_2026-10-11_2026-10-12.json").write_text(json.dumps({
        "as_of": "2026-10-12", "window": {"t0_ms": 3_000_000, "t1_ms": 4_000_000, "t0_date": "2026-10-12", "t1_date": "2026-10-19", "complete": False},
        "rows": [], "record_row": {"address": "0xrec", "net_with_funding": "0"}, "arena_run": {"root": "r"}, "settled_rule": "x"}), encoding="utf-8")
    vps = tmp / "vps"
    vps.mkdir()

    def row(fork, net, cost=18.64):
        fam, coin = fork.split(":")
        return json.dumps({"fork": fork, "family": fam, "coin": coin, "net_bps": net, "gross_bps": net + cost, "cost_bps": cost, "exit_reason": "gate", "in_sample": False})
    (vps / "marks_2026-11-01.jsonl").write_text("\n".join([row("F4:AAA", 10.0), row("F4:AAA", -30.0), row("C1:AAA", -5.0)]) + "\n", encoding="utf-8")
    (vps / "marks_2026-11-02.jsonl").write_text("\n".join([json.dumps({"type": "void", "day": "2026-11-02", "ms": 1, "reason": "S72"}), row("F4:AAA", 999.0)]) + "\n", encoding="utf-8")
    (vps / "marks_2026-11-03.jsonl").write_text("\n".join([row("F4:AAA", 50.0), row("C1:AAA", 7.0), row("F3:AAA", 999.0)]) + "\n", encoding="utf-8")
    settled = tmp / "SETTLED.md"
    settled.write_text("# s\n", encoding="utf-8")
    live = tmp / "live"
    live.mkdir()
    (live / "capture_LIVE_2026-09-30_pv_x.json").write_text(json.dumps({"live_fill": {"fill_time_ms": 900_000, "dir": "Open Long", "tx_hashes": ["0xold"]}}), encoding="utf-8")
    return arena, vps, settled, live


def test_r124_r125_r126_on_synthetic_pins(tmp_path):
    arena, vps, settled, live = _synthetic(tmp_path)
    m = ab.board("2026-11-04", arena, vps, settled, ab.led.MARKER, live)
    rec = [r for r in m["rows"] if r["klass"] == "USD"]
    assert len(rec) == 1 and rec[0]["trades"] == 2 and rec[0]["wins"] == 1 and rec[0]["win_rate"] == 0.5
    assert rec[0]["biggest_win"] == "1.8" and rec[0]["biggest_loss"] == "-1.2" and rec[0]["fees"] == "0.5"   # 2.0 - 0.1 - 0.1; -1.0 - 0.1 - 0.1
    assert rec[0]["total_pnl"] == "0.45" and rec[0]["open_round_trips_at_window_end"] == 1 and rec[0]["fills"] == 5
    assert rec[0]["roi"] == ab.ROI_NOT_COMPUTED and rec[0]["rank"] == 1 and rec[0]["rank_of"] == 1
    assert m["record_not_graded"][0]["cohort_date"] == "2026-10-11" and "not on the branch" in m["record_not_graded"][0]["reason"]
    assert m["record_outside_windows"][0]["capture"] == "capture_LIVE_2026-09-30_pv_x.json"
    pop = {r["fork"]: r for r in m["rows"] if r["klass"] == "bps"}
    assert m["population"]["days"] == ["2026-11-01", "2026-11-03"] and "2026-11-02" in m["population"]["void_days_excluded"]
    assert pop["F4:AAA"]["trades"] == 3 and pop["F4:AAA"]["wins"] == 2 and pop["F4:AAA"]["total_pnl"] == pytest.approx(30.0)
    assert pop["F4:AAA"]["biggest_win"] == 50.0 and pop["F4:AAA"]["biggest_loss"] == -30.0 and pop["F4:AAA"]["fees"] == pytest.approx(3 * 18.64)
    assert pop["C1:AAA"]["control"] is True and pop["C1:AAA"]["trades"] == 2 and pop["C1:AAA"]["total_pnl"] == pytest.approx(2.0)
    assert pop["F4:AAA"]["rank"] == 1 and pop["C1:AAA"]["rank"] == 2 and pop["C1:AAA"]["rank_of"] == 2
    assert all(r["roi"] == ab.ROI_NOT_COMPUTED for r in m["rows"])
    md = ab.render_markdown(m)
    assert "| 1 of 1 |" in md and "never USD" in md and "not computed" in md
    html = ab.render_html_section(m)
    assert 'id="ai-board"' in html and "<script" not in html


def test_s102_page_off_its_pin_refuses(tmp_path):
    arena, vps, settled, live = _synthetic(tmp_path, tamper=True)
    with pytest.raises(AdapterError, match="S102"):
        ab.board("2026-11-04", arena, vps, settled, ab.led.MARKER, live)


def test_r123_s101_write_latest_and_cli(tmp_path, capsys):
    arena, vps, settled, live = _synthetic(tmp_path)
    out = tmp_path / "board"
    rc = ab.main(["--as-of", "2026-11-04", "--arena-dir", str(arena), "--vps-dir", str(vps), "--out-dir", str(out), "--settled", str(settled), "--live-dir", str(live)])
    assert rc == 0 and "AI BOARD ENTRY as of 2026-11-04" in capsys.readouterr().out
    assert (out / "ai_board_2026-11-04.json").read_bytes() == (out / "ai_board_latest.json").read_bytes()
    assert ab.check_latest(out) == "ai_board_2026-11-04.json"
    (out / "ai_board_latest.json").write_bytes(b"{}\n")
    with pytest.raises(AdapterError, match="S101"):
        ab.check_latest(out)
    # the CLI on a refusal writes nothing
    arena2, vps2, settled2, live2 = _synthetic(tmp_path / "t", tamper=True)
    out2 = tmp_path / "board2"
    rc = ab.main(["--as-of", "2026-11-04", "--arena-dir", str(arena2), "--vps-dir", str(vps2), "--out-dir", str(out2), "--settled", str(settled2), "--live-dir", str(live2)])
    assert rc == 1 and "AI BOARD REFUSED" in capsys.readouterr().out and not out2.exists()


def test_r123_no_network_clock_or_randomness():
    src = _SRC.read_text(encoding="utf-8")
    for banned in ("urllib", "socket", "requests", "http.client", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert banned not in src, banned


def test_known_answers_on_the_real_pins():
    m = ab.board("2026-11-08")
    rec = [r for r in m["rows"] if r["klass"] == "USD"]
    assert len(rec) == 1 and rec[0]["cohort_date"] == "2026-10-25" and rec[0]["address"] == "0x9f976123e7c48952be487664b8130aad144b7f23"
    r = rec[0]
    assert r["trades"] == 2 and r["wins"] == 1 and r["win_rate"] == 0.5 and r["fills"] == 4 and r["funding_rows"] == 27
    assert r["biggest_win"] == "0.144370" and r["biggest_loss"] == "-0.067163" and r["fees"] == "0.041793"
    assert r["realized_ex_funding"] == "0.077207" and r["funding"] == "-0.003674" and r["total_pnl"] == "0.073533"
    assert r["pins"]["fills_pages"] == ["28c2f8c641f490078c9861e41fdd9fd20bdf0649decc34ee9c1de6a5e807df9b"]
    assert m["record_not_graded"] == [{"cohort_date": "2026-11-03", "address": "0x9f976123e7c48952be487664b8130aad144b7f23",
                                       "reason": "pages not on the branch (A27 (2): archived at the window's close)",
                                       "fills_file": "hl_fills_0x9f976123e7c48952be487664b8130aad144b7f23.jsonl.gz", "pins": 0}]
    assert [x["capture"][13:23] for x in m["record_outside_windows"]] == ["2026-10-24", "2026-10-24", "2026-10-25", "2026-10-25"]
    assert m["population"]["days"] == ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    assert set(m["population"]["void_days_excluded"]) == {"2026-11-06", "2026-11-07"}
    pop = {r["fork"]: r for r in m["rows"] if r["klass"] == "bps"}
    want = {"F4:BTC": (50, 13, 230.35, -67.43, -1071.4, 939.9), "F4:ETH": (62, 12, 327.94, -84.28, -1669.4, 1184.1),
            "F4:HYPE": (91, 11, 438.66, -78.91, -1730.9, 1735.0), "F4:NEAR": (32, 6, 915.98, -65.61, 595.6, 634.4),
            "F4:SOL": (53, 14, 553.55, -70.31, 188.1, 996.8), "F4:ZEC": (104, 11, 917.38, -122.33, -2931.6, 2052.5),
            "C1:BTC": (5, 2, 30.70, -53.59, -100.6, 93.8), "C1:ETH": (5, 2, 193.11, -53.46, 138.3, 95.4),
            "C1:HYPE": (5, 0, -49.71, -52.06, -254.5, 97.1), "C1:NEAR": (5, 0, -49.79, -58.91, -261.5, 101.0),
            "C1:SOL": (5, 1, 17.94, -61.70, -197.3, 95.6), "C1:ZEC": (5, 1, 69.09, -100.16, -187.3, 98.1)}
    for fork, (n, w, bw, bl, tot, fees) in want.items():
        p = pop[fork]
        assert p["trades"] == n and p["wins"] == w, fork
        assert p["biggest_win"] == pytest.approx(bw, abs=0.005) and p["biggest_loss"] == pytest.approx(bl, abs=0.005), fork
        assert p["total_pnl"] == pytest.approx(tot, abs=0.05) and p["fees"] == pytest.approx(fees, abs=0.05), fork
        assert p["control"] == fork.startswith("C1:")
    order = [r["fork"] for r in m["rows"] if r["klass"] == "bps"]
    assert order[:4] == ["F4:NEAR", "F4:SOL", "C1:ETH", "C1:BTC"] and order[-1] == "F4:ZEC" and pop["F4:ZEC"]["rank"] == 12
    assert rec[0]["rank"] == 1 and rec[0]["rank_of"] == 1


def test_board_latest_is_the_newest_dated_pin():
    if not ab.BOARD_DIR.exists():
        pytest.skip("no board committed yet")
    name = ab.check_latest(ab.BOARD_DIR)
    m = json.loads((ab.BOARD_DIR / name).read_text(encoding="utf-8"))
    assert m["kind"] == ab.BOARD_KIND and ab.board_json(ab.board(m["as_of"])) == (ab.BOARD_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
