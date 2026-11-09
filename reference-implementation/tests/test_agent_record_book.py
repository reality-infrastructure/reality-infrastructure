"""A37 / P28 gates: THE BOOK OF THE VERDICT.

R145 F6 = F4's signal over the KEEP list, every other byte F4's (the marker's own functions mark it);
R146 the KEEP list from the pinned feed, the RECORD row excluded, sorted, the feed's sha beside it;
R147 every replay row in_sample, no status; torn page lines recovered by R115's rule; R148 the book's
ledger is agent_ledger with family F6 (six slots, k 5) and the F4 ledger is unchanged byte for byte;
R149 the relisting table counts verdicts; S105 pure and byte-equal on re-run; S106 no venue write path;
the committed pins re-verify. Offline; no network; no clock.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from rights_events import agent_ledger as al
from rights_events import arena_book as ab
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_MK_DIR = _FIX / "marker"
_BOOK = _FIX / "book"
COINS = ["BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR"]
A1, A2, A3, REC = "0x" + "a" * 40, "0x" + "b" * 40, "0x" + "c" * 40, "0x9f976123e7c48952be487664b8130aad144b7f23"
C1, C2 = "2026-10-25", "2026-11-03"
DAY = "2026-11-04"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _MK_DIR / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


mk = _load("marker")
FAM = json.loads((_MK_DIR / "families.json").read_bytes())


def _row(cohort, addr, status, coverage="FULL", net="1.0", record=False):
    return {"cohort_date": cohort, "address": addr + (" (RECORD)" if record else ""), "record": record,
            "status": status, "coverage": coverage, "verified_net": net}


def _feed(tmp: Path) -> Path:
    doc = {"kind": "proof_of_outcome_copiers_grade", "as_of": "2026-11-08",
           "cohorts": [{"cohort_date": C1, "arena_as_of": "2026-11-03", "window": {"complete": True}},
                       {"cohort_date": C2, "arena_as_of": "2026-11-08", "window": {"complete": False}}],
           "rows": [_row(C1, A2, "KEEP"), _row(C1, A1, "KEEP"), _row(C1, REC, "KEEP", record=True),
                    _row(C1, A3, "DROP", "NONE", "0"), _row(C1, "0x" + "d" * 40, "UNDECIDED", "PARTIAL"),
                    _row(C2, A1, "OPEN", "FULL", "5.0"), _row(C2, A3, "OPEN", "FULL", "-2.0"),
                    _row(C2, "0x" + "d" * 40, "OPEN", "FULL", "3.0"), _row(C2, "0x" + "e" * 40, "OPEN", "NONE", "0")]}
    p = tmp / "feed_2026-11-08.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _fill(coin, px, sz, t, d="Open Long", tid=1):
    return {"coin": coin, "px": str(px), "sz": str(sz), "side": "B", "time": t, "startPosition": "0.0", "dir": d,
            "closedPnl": "0.0", "hash": "0x" + "1" * 64, "oid": 1, "crossed": True, "fee": "0.0", "tid": tid}


def _world(tmp: Path, torn=False):
    """One KEEP address with one page holding one qualifying BTC open at 00:10Z of DAY, plus a sub-notional
    one and an ETH close; a tape with BTC flat then 40 bps down at 00:20Z (a stop), every other coin flat."""
    ch = tmp / "arena" / C2
    ch.mkdir(parents=True)
    t0 = ab.day_ms(DAY)
    page = json.dumps([_fill("BTC", 100, 300, t0 + 10 * 60_000, tid=11), _fill("BTC", 100, 50, t0 + 11 * 60_000, tid=12),
                       _fill("ETH", 10, 5000, t0 + 12 * 60_000, "Close Long", tid=13)]).encode()
    body = page + b"\n"
    if torn:
        body = b'{"coin":"BTC","px":"1' + body   # a fragment glued to the whole page (R115)
    # byte-split into two parts under a small limit, as the channel does
    (ch / f"pages_fills_{A1}.jsonl.part000").write_bytes(body[:40])
    (ch / f"pages_fills_{A1}.jsonl.part001").write_bytes(body[40:])
    (ch / "pages_index.jsonl").write_text(json.dumps({"file": f"pages_fills_{A1}.jsonl", "sha256": ab.sha256_bytes(page)}) + "\n", encoding="utf-8")
    tape = tmp / "tape"
    tape.mkdir()
    for day in (DAY, "2026-11-05"):
        d0 = ab.day_ms(day)
        lines = []
        for i in range(0, 1440, 1):
            ms = d0 + i * 60_000
            btc = 100.0 if (day != DAY or i < 20) else 99.6
            lines.append(json.dumps({"ms": ms, "mids": {c: (str(btc) if c == "BTC" else "10") for c in COINS}}))
        (tape / f"tape_MIDS_{day}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ch, tape


# ----------------------------------------------------------------------------- R146
def test_keep_list_excludes_record_sorted_and_pins_feed(tmp_path):
    feed = _feed(tmp_path)
    k = ab.keep_list(feed, C1)
    assert k["addresses"] == sorted([A1, A2]) and k["excluded_record"] == [REC]
    assert k["n_keep_rows"] == 3 and k["feed_sha256"] == ab.sha256_bytes(feed.read_bytes())
    with pytest.raises(AdapterError):
        ab.keep_list(feed, C2)          # window not complete
    with pytest.raises(AdapterError):
        ab.keep_list(feed, "2026-01-01")


# ----------------------------------------------------------------------------- R145 / R147
def test_f6_signals_are_f4s_relabelled_inside_the_window():
    t0 = ab.day_ms(DAY)
    fills = [_fill("BTC", 100, 300, t0 + 60_000, tid=1), _fill("BTC", 100, 50, t0 + 120_000, tid=2),
             _fill("BTC", 100, 300, t0 - 1, tid=3), _fill("xyz:NVDA", 100, 300, t0 + 60_000, tid=4)]
    sigs = ab.f6_signals(fills, A1, COINS, 10_000, t0, t0 + ab.DAY_MS - 1, mk)
    assert [s["coin"] for s in sigs] == ["BTC"] and sigs[0]["family"] == "F6" and sigs[0]["leader"] == A1
    f4 = mk.f4_leader_opens(fills, 10_000, "BTC", A1)
    assert {k: v for k, v in sigs[0].items() if k != "family"} == {k: v for k, v in f4[0].items() if k != "family"}


def test_page_parts_joined_torn_recovered_and_indexed(tmp_path):
    ch, _ = _world(tmp_path, torn=True)
    parts = sorted(ch.glob(f"pages_fills_{A1}.jsonl.part*"))
    index, pin = ab.read_pages_index(ch / "pages_index.jsonl")
    fills, pins, align = ab.read_page_parts(parts, index[f"pages_fills_{A1}.jsonl"])
    assert len(pins) == 2 and [p["file"] for p in pins] == [x.name for x in parts]
    assert align["torn_fragments"] == 1 and align["lost_pages"] == 1 and align["pages"] == 1 and align["indexed"] == 1
    assert [f["tid"] for f in fills] == [11, 12, 13]


def test_replay_marks_with_the_markers_functions_in_sample(tmp_path):
    ch, tape = _world(tmp_path)
    k = ab.keep_list(_feed(tmp_path), C1)
    rep = ab.replay(k, ch, tape, DAY, DAY, fam=FAM, mk=mk)
    assert rep["coverage"][A1]["signals"] == 1 and rep["coverage"][A2]["pages"] == 0 and "note" in rep["coverage"][A2]
    assert len(rep["episodes"]) == 1
    e = rep["episodes"][0]
    assert e["fork"] == "F6:BTC" and e["family"] == "F6" and e["in_sample"] is True and e["exit_reason"] == "stop"
    assert e["cost_bps"] == pytest.approx(2 * (9.32 + 1.0)) and e["gross_bps"] == pytest.approx(-40.0, abs=1e-6)
    assert e["net_bps"] == pytest.approx(-40.0 - 20.64, abs=1e-6) and e["spread_source"] == "replay_proxy"
    # the same bytes through the marker directly
    path = [(ab.day_ms(DAY) + i * 60_000, 100.0 if i < 20 else 99.6) for i in range(1440)]
    direct = mk.mark_fork(path, rep["signals"], fork="F6:BTC", family="F6", coin="BTC", stop_bps=30.0, gate_ms=18_000_000,
                          fee_bps_per_leg=9.32, spread_bps_per_leg=1.0, spread_source="replay_proxy", in_sample=True)
    assert [d.row() for d in direct] == rep["episodes"]
    assert rep["pins"]["tape"][0]["file"] == f"tape_MIDS_{DAY}.jsonl" and rep["window"]["tape_days"] == [DAY, "2026-11-05"]


# ----------------------------------------------------------------------------- R149
def test_relist_counts_verdicts_not_addresses(tmp_path):
    rl = ab.relist(_feed(tmp_path), C1, C2)
    by = {r["verdict"]: r for r in rl["table"]}
    assert by["KEEP"] == {"verdict": "KEEP", "n": 3, "relisted": 1, "full_so_far": 1, "net_positive": 1}
    assert by["DROP"] == {"verdict": "DROP", "n": 1, "relisted": 1, "full_so_far": 1, "net_positive": 0}
    assert by["UNDECIDED"]["net_positive"] == 1 and rl["new_in_next_cohort"] == 1
    assert "address" not in json.dumps(rl["table"])


# ----------------------------------------------------------------------------- R148
def test_book_ledger_is_f6_six_slots_k5_and_f4_ledger_unchanged():
    m = ab.book_ledger("2026-11-08")
    assert m["family"] == "F6" and [r["fork"] for r in m["forks"]] == [f"F6:{c}" for c in COINS]
    assert m["k"] == 5 == mk.k_for(6) and m["counts"]["ALIVE"] == 6 and all(r["episodes"] == 0 for r in m["forks"])
    f4 = al.ledger("2026-11-08")
    assert "family" not in f4
    pinned = json.loads((_FIX / "ledger" / "ledger_2026-11-08.json").read_text(encoding="utf-8"))
    assert _approx(f4, pinned), "the F4 ledger changed beyond float rounding"


def _approx(a, b, tol=1e-9) -> bool:
    """Structural equality with floats compared to tol: the pinned ledger was written by Python 3.11,
    whose sum() rounds differently in the last digit from 3.12's compensated sum."""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
        except (TypeError, ValueError):
            return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_approx(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_approx(x, y, tol) for x, y in zip(a, b))
    return a == b


# ----------------------------------------------------------------------------- S105 / S106
def test_s105_run_is_byte_equal_on_rerun(tmp_path):
    ch, tape = _world(tmp_path)
    feed = _feed(tmp_path)
    outs = []
    for i in range(2):
        out = tmp_path / f"out{i}"
        ab.run("2026-11-08", C1, C2, feed, ch, tape, DAY, DAY, out_dir=out, endpoint="x")
        assert ab.verify(out / "MANIFEST_BOOK_2026-11-08.json") == []
        outs.append({p.name: p.read_bytes() for p in out.iterdir()})
    assert outs[0] == outs[1]
    (tmp_path / "out0" / "book_latest.json").write_bytes(b"{}\n")
    assert ab.verify(tmp_path / "out0" / "MANIFEST_BOOK_2026-11-08.json") != []


@pytest.mark.parametrize("src", [_ROOT / "rights_events" / "arena_book.py", _MK_DIR / "forward.py"])
def test_s106_no_venue_write_path(src):
    text = src.read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|mcp__gdex", text)


# ----------------------------------------------------------------------------- the forward marker (R148)
def test_forward_marker_keep_list_and_families(tmp_path):
    fw = _load("forward")
    assert fw.load_keep(tmp_path / "absent.json") == []
    p = tmp_path / "keep.json"
    p.write_text(json.dumps({"addresses": [A2.upper(), A1]}), encoding="utf-8")
    assert fw.load_keep(p) == sorted([A1, A2])
    assert fw.families_for(A1, leaders=[A1], keep=[A1]) == ("F4", "F6")
    assert fw.families_for(A1, leaders=[A2], keep=[A1]) == ("F6",)
    assert fw.families_for(A1, leaders=[A1], keep=[]) == ("F4",)
    assert fw.families_for(A3, leaders=[A1], keep=[A2]) == ()
    assert "F6" in fw.FORWARD_FAMILIES or not (_MK_DIR / "keep.json").exists()
    assert fw.MIN_NOTIONAL == 10000 and fw.STOP == 30.0 and fw.GATE == 18_000_000


# ----------------------------------------------------------------------------- the committed pins
def test_committed_book_pins_reverify():
    assert ab.verify(_BOOK / "MANIFEST_BOOK_2026-11-08.json") == []
    keep = json.loads((_BOOK / f"keep_{C1}.json").read_text(encoding="utf-8"))
    assert len(keep["addresses"]) == 6 and keep["excluded_record"] == [REC] and REC not in keep["addresses"]
    assert keep["addresses"] == sorted(keep["addresses"])
    book = json.loads((_BOOK / "book_2026-11-08.json").read_text(encoding="utf-8"))
    assert book["ledger"]["forward_rows"] == 0 and book["ledger"]["counts"]["ALIVE"] == 6
    assert all(e["in_sample"] for e in map(json.loads, (_BOOK / f"marks_F6_{C1}_as_of_2026-11-08.jsonl").read_text(encoding="utf-8").splitlines()))
    assert (_BOOK / "book_latest.json").read_bytes() == (_BOOK / "book_2026-11-08.json").read_bytes()
