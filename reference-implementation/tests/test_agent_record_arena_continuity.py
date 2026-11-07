"""PREREG A24 gates (R113 / R114 / S97): coverage by continuity for tape-sourced rows, and a
page recovered verbatim from a torn line when the index pins its suffix. API-sourced rows (no
`fetched`) keep A18's rules bit for bit. Offline; synthetic pages; no network, no clock.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import (
    PAGE_CAP, STATUS_FULL, STATUS_NONE, STATUS_PARTIAL, coverage, coverage_by_continuity)

FIXTURES = Path(__file__).resolve().parent.parent / "rights_events" / "fixtures" / "agent_record"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


reader = _load("arena_capture_from_tape_a24", FIXTURES / "arena" / "arena_capture_from_tape.py")

T0 = 1793750400000                     # 2026-11-04 00:00:00Z
H = 3_600_000


def _pin(items: int, fetched_ms: int) -> dict:
    return {"line": 0, "sha256": "0" * 64, "bytes": 1, "items": items, "fetched_ms": fetched_ms}


def _times(start: int, n: int, step: int) -> list[int]:
    return [start + i * step for i in range(n)]


def test_r114_capped_cycle_followed_by_a_gap_above_the_address_own_gap_is_partial():
    # cycle 1 (capped: last page full) covers t0+1s .. ; cycle 2 starts 1 800 s after cycle 1's last fill;
    # the address's own gaps are 1 s inside cycles and 2 s at the un-capped boundary that follows
    c1 = [_times(T0 + 1000, PAGE_CAP, 1000)]
    last1 = c1[0][-1]
    c2 = [_times(last1 + 1_800_000, 50, 1000)]
    c3 = [_times(c2[0][-1] + 2000, 50, 1000)]
    pins = [_pin(PAGE_CAP, T0 + H), _pin(50, T0 + 2 * H), _pin(50, T0 + 3 * H)]
    status, reason, n = coverage_by_continuity(pins, c1 + c2 + c3, T0)
    assert status == STATUS_PARTIAL and n["capped_cycles"] == 1 and n["cycles"] == 3
    assert n["post_cap_gap_ms"] == 1_800_000 and n["own_gap_ms"] == 2000 and "fell behind" in reason


def test_r114_capped_cycle_with_a_small_gap_is_full():
    c1 = [_times(T0 + 1000, PAGE_CAP, 1000)]
    c2 = [_times(c1[0][-1] + 1500, 10, 1000)]       # 1.5 s after a capped cycle
    c3 = [_times(c2[0][-1] + 5000, 10, 1000)]       # a 5 s idle gap after an un-capped cycle sets B = 5 s
    pins = [_pin(PAGE_CAP, T0 + H), _pin(10, T0 + 2 * H), _pin(10, T0 + 3 * H)]
    status, _, n = coverage_by_continuity(pins, c1 + c2 + c3, T0)
    assert status == STATUS_FULL and n["post_cap_gap_ms"] == 1500 and n["own_gap_ms"] == 5000


def test_r114_a_capped_first_cycle_starting_far_after_t0_is_partial():
    # the tape started 4 h behind and its first cycle was capped: the lead from t0 counts as a post-cap gap
    c1 = [_times(T0 + 4 * H, PAGE_CAP, 1000)]
    c2 = [_times(c1[0][-1] + 1000, 5, 1000)]
    pins = [_pin(PAGE_CAP, T0 + 5 * H), _pin(5, T0 + 6 * H)]
    status, _, n = coverage_by_continuity(pins, c1 + c2, T0)
    assert status == STATUS_PARTIAL and n["post_cap_gap_ms"] == 4 * H


def test_r114_idle_gaps_after_uncapped_cycles_never_make_partial_and_no_fills_is_none():
    c1 = [_times(T0 + 1000, 3, 1000)]
    c2 = [_times(c1[0][-1] + 20 * H, 3, 1000)]      # idle 20 h, the API had nothing more
    pins = [_pin(3, T0 + H), _pin(3, T0 + 22 * H)]
    status, _, n = coverage_by_continuity(pins, c1 + c2, T0)
    assert status == STATUS_FULL and n["capped_cycles"] == 0 and n["own_gap_ms"] == 20 * H
    assert coverage_by_continuity([_pin(0, T0 + H)], [[]], T0)[0] == STATUS_NONE


def test_r114_pages_within_ten_minutes_form_one_cycle_and_the_first_cycle_sorts_its_fills():
    # two pages fetched 30 s apart = one cycle; its last page is short -> not capped
    c = [_times(T0 + 1000, PAGE_CAP, 1000), _times(T0 + 1000 + PAGE_CAP * 1000, 7, 1000)]
    pins = [_pin(PAGE_CAP, T0 + H), _pin(7, T0 + H + 30_000)]
    status, _, n = coverage_by_continuity(pins, c, T0)
    assert status == STATUS_FULL and n["cycles"] == 1 and n["capped_cycles"] == 0


def test_a18_rules_untouched_for_rows_without_fetched():
    assert coverage(0, [{"items": 0}], None, T0)[0] == STATUS_NONE
    assert coverage(10000, [{"items": 2000}] * 5, T0 + 1, T0)[0] == STATUS_PARTIAL
    assert coverage(5, [{"items": 5}], T0 + 1, T0)[0] == STATUS_FULL


# --- R113: alignment with the index, torn-page recovery, S97 -------------------------------------

A = "0x1111111111111111111111111111111111111111"
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
T1 = 1794355199999


def _page(items) -> bytes:
    return json.dumps(items, separators=(",", ":")).encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _entry(name: str, raw: bytes, fetched: str) -> str:
    items = json.loads(raw)
    times = [it["time"] for it in items if "time" in it]
    return json.dumps({"fetched": fetched, "file": name, "sha256": _sha(raw), "bytes": len(raw), "items": len(items),
                       "first_time_ms": min(times) if times else None, "last_time_ms": max(times) if times else None,
                       "request": {"type": "userFillsByTime", "user": A, "startTime": T0, "endTime": T1}})


def _cohort_capture(tmp: Path) -> Path:
    doc = {"kind": "agent_record_arena_capture", "synthetic": True, "note": "A24 gate",
           "actor": {"actor_id": ACTOR},
           "cohort": {"cohort_date": "2026-11-03", "observed_ms": 1793688589648, "payload_file": "x.json",
                      "payload_sha256": "0" * 64, "addresses": [{"address": A, "first_window": "week", "first_rank": 1}]},
           "window": {"t0_ms": T0, "t1_ms": T1, "days": 7, "started": True, "complete": False}}
    p = tmp / "capture_ARENA_2026-11-03_2026-11-03.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _channel(tmp: Path, glue: bool, corrupt: bool = False, trailing: bool = False) -> Path:
    ch = tmp / "ch"
    d = ch / "arena" / "2026-11-03"
    d.mkdir(parents=True)
    name = f"pages_fills_{A}.jsonl"
    p1 = _page([{"time": T0 + 1000 * i, "tid": i, "coin": "BTC"} for i in range(5)])
    p2 = _page([{"time": T0 + 90_000, "tid": 99, "coin": "BTC"}])
    frag = b'[{"coin":"BTC","px":"1","sz":"1","ti'           # a write cut by the full disk, no newline
    body = p1 + b"\n" + (frag if glue else b"") + (p2[:10] + b"XX" + p2[12:] if corrupt else p2) + b"\n"   # corrupt: same length, two bytes changed
    if trailing:
        body += _page([{"time": T0 + 95_000, "tid": 100, "coin": "BTC"}]) + b"\n"   # in flight: no entry yet
    (d / name).write_bytes(body)
    (d / f"pages_funding_{A}.jsonl").write_bytes(_page([]) + b"\n")
    (d / f"pages_fills_{ACTOR}.jsonl").write_bytes(_page([]) + b"\n")
    (d / f"pages_funding_{ACTOR}.jsonl").write_bytes(_page([]) + b"\n")
    lines = [_entry(name, p1, "2026-11-04T01:20:00Z"), _entry(name, p2, "2026-11-04T02:20:00Z"),
             _entry(f"pages_funding_{A}.jsonl", _page([]), "2026-11-04T01:20:01Z"),
             _entry(f"pages_fills_{ACTOR}.jsonl", _page([]), "2026-11-04T01:20:02Z"),
             _entry(f"pages_funding_{ACTOR}.jsonl", _page([]), "2026-11-04T01:20:03Z")]
    (d / "pages_index.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ch


def _build(tmp: Path, ch: Path) -> tuple[int, Path]:
    out = tmp / "out"
    rc = reader.main(["--channel-dir", str(ch), "--cohort-capture", str(_cohort_capture(tmp)), "--as-of-date",
                      "2026-11-06", "--now-ms", "1794100000000", "--out-dir", str(out)])
    return rc, out


def test_r113_a_glued_torn_line_recovers_the_page_verbatim(tmp_path):
    rc, out = _build(tmp_path, _channel(tmp_path, glue=True))
    assert rc == 0
    cap = json.loads((out / "capture_ARENA_2026-11-03_2026-11-06.json").read_text(encoding="utf-8"))
    row = next(r for r in cap["rows"] if r["address"] == A)
    p2 = _page([{"time": T0 + 90_000, "tid": 99, "coin": "BTC"}])
    assert [p["items"] for p in row["fills_pages"]] == [5, 1]
    assert row["fills_pages"][1]["sha256"] == _sha(p2) and row["fills_pages"][1]["recovered"] is True
    assert row["fills_pages"][0]["recovered"] is False and row["fills_pages"][0]["fetched"] == "2026-11-04T01:20:00Z"
    assert row["pages_recovered"] == 1 and cap["as_of"]["alignment"]["recovered_pages"] == 1
    # the pinned gz page file holds the recovered page, not the glued line
    with gzip.open(out / row["fills_file"], "rb") as g:
        assert g.read().split(b"\n")[1] == p2


def test_s97_a_line_matching_neither_way_refuses_and_writes_nothing(tmp_path, capsys):
    rc, out = _build(tmp_path, _channel(tmp_path, glue=False, corrupt=True))
    assert rc == 2 and "REFUSED S97" in capsys.readouterr().out
    assert not any(p.name.startswith(("capture_", "MANIFEST_", "hl_")) for p in out.iterdir())


def test_r113_a_trailing_line_without_an_entry_is_dropped_and_counted(tmp_path):
    rc, out = _build(tmp_path, _channel(tmp_path, glue=False, trailing=True))
    assert rc == 0
    cap = json.loads((out / "capture_ARENA_2026-11-03_2026-11-06.json").read_text(encoding="utf-8"))
    row = next(r for r in cap["rows"] if r["address"] == A)
    assert [p["items"] for p in row["fills_pages"]] == [5, 1]
    assert cap["as_of"]["alignment"]["dropped_trailing_lines"] == 1


# --- the grader end to end on tape-sourced pins ----------------------------------------------------

def _fill(t, tid, closed="0.0"):
    return {"coin": "BTC", "px": "100", "sz": "1", "side": "B" if tid % 2 == 0 else "A", "time": t,
            "startPosition": "0" if tid % 2 == 0 else "1", "dir": "Open Long", "closedPnl": closed,
            "hash": f"0x{tid:064x}", "oid": tid, "crossed": True, "fee": "0.1", "feeToken": "USDC", "tid": tid}


def _gz(pages: list[bytes]) -> bytes:
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g:
        for p in pages:
            g.write(p + b"\n")
    return bio.getvalue()


def test_grader_uses_continuity_for_tape_rows_and_puts_the_numbers_in_the_claim(tmp_path):
    arena_tests = _load("arena_tests_for_a24", Path(__file__).resolve().parent / "test_agent_record_arena.py")
    cap_path = arena_tests.make_capture(tmp_path)                    # the synthetic cohort-1 capture
    cap = json.loads(cap_path.read_text(encoding="utf-8"))
    # replace A3 (A18's PARTIAL by a late full first page) with tape-sourced pins: a capped first cycle
    # that starts 3 days after t0 -> PARTIAL by continuity, with the numbers in the claim
    t0 = cap["window"]["t0_ms"]
    late = t0 + 3 * 86_400_000
    a3 = "0x3333333333333333333333333333333333333333"
    page1 = _page([_fill(late + i, 100 + i) for i in range(PAGE_CAP)])
    page2 = _page([_fill(late + PAGE_CAP + 5, 5000)])
    (tmp_path / f"hl_fills_{a3}.jsonl.gz").write_bytes(_gz([page1, page2]))
    row = next(r for r in cap["rows"] if r["address"] == a3)
    row["fills_pages"] = [{"line": 0, "sha256": _sha(page1), "bytes": len(page1), "items": PAGE_CAP, "fetched": "2026-10-29T01:20:00Z", "recovered": False},
                          {"line": 1, "sha256": _sha(page2), "bytes": len(page2), "items": 1, "fetched": "2026-10-29T02:20:00Z", "recovered": True}]
    cap_path.write_text(json.dumps(cap, indent=2) + "\n", encoding="utf-8")
    out = tmp_path / "run.ri"
    rc = runner.main(["--capture", str(cap_path), "--out", str(out), "--arena-out", str(tmp_path / "arena")])
    assert rc == 0
    arena = json.loads((tmp_path / "arena.json").read_text(encoding="utf-8"))
    r3 = next(r for r in arena["rows"] if r["address"].lower() == a3)
    assert r3["status"] == STATUS_PARTIAL
    ev = next(e for e in runner.load_run(out)[1] if e.claim.get("address", "").lower() == a3) if hasattr(runner, "load_run") else None
    if ev is not None:
        assert ev.claim["continuity"]["capped_cycles"] == 1 and ev.claim["continuity"]["pages_recovered"] == 1
        assert ev.claim["continuity"]["post_cap_gap_ms"] == 3 * 86_400_000
