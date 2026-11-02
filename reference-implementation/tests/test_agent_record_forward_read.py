"""A17 / P13 gates: the forward-day READER reads through the frozen marker and never decides.

S76  the reader's per-fork numbers equal the arithmetic on the rows (means, stop-first, sums)
S77  the pass line is marker.is_candidate's: k consecutive days beating C0 and C1 plus the 2-sigma
     clause make a candidate; k-1 days do not; a single episode never passes
S78  every file the reader opened is pinned by sha256 in its output
S79  the reader has no network, no wall clock, no randomness and does not import forward.py
S80  in-sample rows and deleted families (F1-F3, R84) are excluded from the forward reading
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_OPS = _ROOT / "rights_events" / "fixtures" / "agent_record" / "ops"
_READER = _OPS / "poo_forward_read.py"


def _load():
    spec = importlib.util.spec_from_file_location("poo_forward_read", _READER)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _row(fork, day_ms, net, gross=None, reason="stop", family=None, in_sample=False):
    fam, coin = fork.split(":")
    return {"fork": fork, "family": family or fam, "coin": coin, "direction": 1, "entry_ms": day_ms + 3_600_000,
            "entry_px": 100.0, "exit_ms": day_ms + 7_200_000, "exit_px": 101.0, "exit_reason": reason,
            "gross_bps": net + 18.64 if gross is None else gross, "cost_bps": 18.64, "funding_bps": 0.0,
            "net_bps": net, "in_sample": in_sample, "spread_bps_per_leg": 0.5, "spread_source": "l2Book:ab", "signal": {}}


def _tree(tmp_path: Path, rows_by_day: dict[str, list[dict]], manifest=None, state=None) -> Path:
    d = tmp_path / "tree"
    (d / "marker").mkdir(parents=True)
    for day, rows in rows_by_day.items():
        (d / "marker" / f"marks_{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (d / "marker" / f"signals_{max(rows_by_day)}.jsonl").write_text('{"type":"F4_signal"}\n{"type":"F4_signal"}\n', encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps(manifest or {"generated_at": "2026-11-02T00:07:00Z", "poo_tape": "active",
                                                            "poo_marker": "active", "tape_newest_mtime": "2026-11-02T00:06:30Z"}))
    (d / "marker" / "marker_state.json").write_text(json.dumps(state or {"void_days": []}))
    return d


DAYS = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]


def _day_ms(day):
    import datetime as dt
    y, m, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_s76_fork_numbers_are_the_row_arithmetic(tmp_path):
    rd = _load()
    day = "2026-11-01"
    rows = [_row("F4:BTC", _day_ms(day), -9.0, reason="stop"), _row("F4:BTC", _day_ms(day), +21.0, reason="gate"),
            _row("C1:BTC", _day_ms(day), -48.0)]
    r = rd.read(_tree(tmp_path, {day: rows}), day, [day], 6)
    f = r["forks"]["F4:BTC"]
    assert f["n"] == 2 and f["mean_net_bps"] == pytest.approx(6.0) and f["sum_net_bps"] == pytest.approx(12.0)
    assert f["stop_first_share"] == pytest.approx(0.5)
    assert f["mean_gross_bps"] == pytest.approx(6.0 + 18.64)
    assert r["forks"]["C1:BTC"]["n"] == 1 and r["episodes"] == 3
    assert r["k"] == 5 and r["signals"] == {"F4_signal": 2}


def test_s77_pass_line_is_the_frozen_markers(tmp_path):
    rd = _load()
    # five consecutive days, F4:BTC +10 and +12 (two episodes a day, low variance), C1:BTC -40 each day
    rows_by_day = {d: [_row("F4:BTC", _day_ms(d), 10.0), _row("F4:BTC", _day_ms(d), 12.0), _row("C1:BTC", _day_ms(d), -40.0)]
                   for d in DAYS}
    r5 = rd.read(_tree(tmp_path / "a", rows_by_day), DAYS[-1], DAYS, 6)
    p = r5["pass_line"]["F4:BTC"]
    assert p["run_days"] == 5 and p["k"] == 5 and p["two_sigma_clears"] and p["candidate"] is True
    # four days only: not a candidate
    r4 = rd.read(_tree(tmp_path / "b", {d: rows_by_day[d] for d in DAYS[1:]}), DAYS[-1], DAYS[1:], 6)
    assert r4["pass_line"]["F4:BTC"]["run_days"] == 4 and r4["pass_line"]["F4:BTC"]["candidate"] is False
    # a day that beats C0 but not C1 breaks the run
    broken = dict(rows_by_day)
    broken[DAYS[2]] = [_row("F4:BTC", _day_ms(DAYS[2]), 1.0), _row("C1:BTC", _day_ms(DAYS[2]), 5.0)]
    rb = rd.read(_tree(tmp_path / "c", broken), DAYS[-1], DAYS, 6)
    assert rb["pass_line"]["F4:BTC"]["run_days"] == 2 and rb["pass_line"]["F4:BTC"]["candidate"] is False
    # one episode in total never passes
    r1 = rd.read(_tree(tmp_path / "d", {DAYS[0]: [_row("F4:BTC", _day_ms(DAYS[0]), 50.0)]}), DAYS[0], [DAYS[0]], 6)
    assert r1["pass_line"]["F4:BTC"]["two_sigma_clears"] is False and r1["pass_line"]["F4:BTC"]["candidate"] is False
    # C1 forks are controls, never candidates
    assert not any(k.startswith("C1:") for k in r5["pass_line"])


def test_s78_every_file_read_is_pinned(tmp_path):
    rd = _load()
    day = "2026-11-01"
    d = _tree(tmp_path, {day: [_row("F4:ETH", _day_ms(day), -3.0)]})
    r = rd.read(d, day, [day], 6)
    expect = {f"marks_{day}.jsonl": d / "marker" / f"marks_{day}.jsonl", f"signals_{day}.jsonl": d / "marker" / f"signals_{day}.jsonl",
              "manifest.json": d / "manifest.json", "marker_state.json": d / "marker" / "marker_state.json"}
    assert set(r["pins"]) == set(expect)
    for name, p in expect.items():
        assert r["pins"][name] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", r["marker_sha256"])
    md = rd.markdown(r)
    assert r["pins"]["manifest.json"] in md and "F4:ETH" in md


def test_s79_reader_is_offline_deterministic_and_does_not_import_forward():
    src = _READER.read_text(encoding="utf-8")
    for banned in ("urllib", "socket", "requests", "http.client", "time.time", "datetime.now", "utcnow", "import random", "from random", "forward.py", "import forward"):
        assert banned not in src.replace('Does not import forward.py', ''), banned


def test_s80_in_sample_and_deleted_families_are_excluded(tmp_path):
    rd = _load()
    day = "2026-11-01"
    rows = [_row("F4:SOL", _day_ms(day), -5.0), _row("F4:SOL", _day_ms(day), +99.0, in_sample=True),
            _row("F1:SOL", _day_ms(day), +99.0), _row("F2:SOL", _day_ms(day), +99.0), _row("F3:SOL", _day_ms(day), +99.0)]
    r = rd.read(_tree(tmp_path, {day: rows}), day, [day], 6)
    assert list(r["forks"]) == ["F4:SOL"] and r["forks"]["F4:SOL"]["n"] == 1 and r["episodes"] == 1


def test_void_day_is_reported_from_state(tmp_path):
    rd = _load()
    day = "2026-11-01"
    d = _tree(tmp_path, {day: [_row("F4:ZEC", _day_ms(day), -5.0)]}, state={"void_days": [day], "tick_errors": 0})
    r = rd.read(d, day, [day], 6)
    assert r["health"]["day_void"] is True and r["health"]["void_days"] == [day] and r["health"]["poo_marker"] == "active"
