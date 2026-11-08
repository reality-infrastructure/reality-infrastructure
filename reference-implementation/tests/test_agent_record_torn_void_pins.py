"""A26.1 pins gates: the readings of Days 15–17 (2026-11-05 … 11-07) from the files pinned as served.

The known answers of A26, reproduced by the code from the pinned files (R115 alignment, R116 void
days, the Day-15 fork table, the pass line over 11-01 … 11-05 through the frozen marker) and the
ledger's behaviour on the real pins (R117: the as-of-11-07 ledger unchanged; as of 11-08 the two
void days are excluded and 11-05's late pin is read).
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from rights_events import agent_ledger as led

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_VPS = _FIX / "vps"
_READER = _FIX / "ops" / "poo_forward_read.py"

PINS = {
    "marks_2026-11-04_as_read_2026-11-08.jsonl": "e973d78492fc2f0f9facf606eef7a32ae3aa3d655a23175ab6cef70ee3fcc5d2",   # A27 (1): the whole day, 97 rows
    "marks_2026-11-05_as_read_2026-11-08.jsonl": "603bb6e01094f76011adc702fbd0db435af025e973de30a21e92b24e401ec126",
    "marks_2026-11-06_as_read_2026-11-08.jsonl": "f321c94edac37472d4cb1d5101866368a13c46b1b6d5b5d441a5283d38c4cfb4",
    "marks_2026-11-07_as_read_2026-11-08.jsonl": "6e4a56d64e190b2166a97a060ded890899cb66e661f3e8236892be0dbb251ef0",
    "signals_2026-11-05.jsonl": "82ae16e4a2412ec6a22016e0266931170a17b4e8679eca9e1f21b84bf368987c",
    "signals_2026-11-06.jsonl": "6467375eb36f2154efa2e86dfc18cb06575fcbd2153e41e86c7c4c6a7669970a",
}
NEWEST = {"2026-11-01": "marks_2026-11-01_as_read_2026-11-03.jsonl", "2026-11-02": "marks_2026-11-02_as_read_2026-11-04.jsonl",
          "2026-11-03": "marks_2026-11-03_as_read_2026-11-05.jsonl", "2026-11-04": "marks_2026-11-04.jsonl",
          "2026-11-05": "marks_2026-11-05_as_read_2026-11-08.jsonl", "2026-11-06": "marks_2026-11-06_as_read_2026-11-08.jsonl",
          "2026-11-07": "marks_2026-11-07_as_read_2026-11-08.jsonl"}
DAYS = list(NEWEST)


def _load():
    spec = importlib.util.spec_from_file_location("poo_forward_read_pins", _READER)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_pinned_files_as_served(name, sha):
    assert _sha(_VPS / name) == sha


def _record_tree(tmp_path: Path) -> Path:
    """The record's view: the newest pinned reading of every day under the channel's file names."""
    d = tmp_path / "record"
    (d / "marker").mkdir(parents=True)
    for day, name in NEWEST.items():
        shutil.copyfile(_VPS / name, d / "marker" / f"marks_{day}.jsonl")
    for day in ("2026-11-05", "2026-11-06", "2026-11-07"):
        shutil.copyfile(_VPS / f"signals_{day}.jsonl", d / "marker" / f"signals_{day}.jsonl")
    shutil.copyfile(_VPS / "manifest_2026-11-07.json", d / "manifest.json")
    shutil.copyfile(_VPS / "marker_state_2026-11-07.json", d / "marker" / "marker_state.json")
    return d


def test_r115_alignment_known_answers(tmp_path):
    rd = _load()
    rows06, voids06, al06 = rd.read_day_lines(_VPS / NEWEST["2026-11-06"], "marks")
    assert (len(rows06), len(voids06)) == (61, 1) and [t["line"] for t in al06["torn_fragments"]] == [40]
    assert al06["lost_rows"] == 1 and al06["in_flight"] == 0 and al06["lines"] == 62
    assert al06["torn_fragments"][0]["head"].startswith('{"coin":"BTC"')
    rec06 = [r for r in rows06 if r.get("cost_bps") == 19.08811424608106]                 # the whole row behind the fragment, by its own cost field (six rows share its exit tick, two its entry tick)
    assert len(rec06) == 1 and rec06[0]["fork"] == "F4:ETH" and rec06[0]["net_bps"] == pytest.approx(-60.19, abs=0.005)
    rows05, voids05, al05 = rd.read_day_lines(_VPS / NEWEST["2026-11-05"], "marks")
    assert (len(rows05), len(voids05), al05["torn_fragments"], al05["in_flight"]) == (101, 0, [], 0)
    rows07, voids07, al07 = rd.read_day_lines(_VPS / NEWEST["2026-11-07"], "marks")
    assert (len(rows07), len(voids07), al07["torn_fragments"]) == (45, 3, [])
    assert [v["ms"] for v in voids07] == [1794018211588, 1794018588982, 1794018614829]
    s06, _, sal06 = rd.read_day_lines(_VPS / "signals_2026-11-06.jsonl", "signals")
    assert len(sal06["torn_fragments"]) == 15 and sal06["in_flight"] == 0
    types06 = {}
    for s in s06:
        types06[s["type"]] = types06.get(s["type"], 0) + 1
    assert types06 == {"F4_signal": 6390, "poll_failure": 52, "tick_error": 140}
    s07, _, sal07 = rd.read_day_lines(_VPS / "signals_2026-11-07.jsonl", "signals")
    assert [t["line"] for t in sal07["torn_fragments"]] == [41, 120, 204]


def test_r116_void_days_and_the_day_15_reading(tmp_path):
    rd = _load()
    d = _record_tree(tmp_path)
    r = rd.read(d, "2026-11-05", DAYS, 6)
    assert r["void_days_by_row"] == ["2026-11-06", "2026-11-07"]
    assert r["pass_line_days"] == DAYS[:5] and r["episodes"] == 101
    f = r["forks"]
    assert f["F4:SOL"]["n"] == 15 and f["F4:SOL"]["sum_net_bps"] == pytest.approx(143.9, abs=0.05)
    assert f["F4:SOL"]["mean_net_bps"] == pytest.approx(9.59, abs=0.005) and f["F4:SOL"]["stop_first_share"] == pytest.approx(0.8)
    assert f["F4:ZEC"]["n"] == 27 and f["F4:ZEC"]["sum_net_bps"] == pytest.approx(-805.7, abs=0.05)
    assert f["C1:ETH"]["n"] == 1 and f["C1:ETH"]["sum_net_bps"] == pytest.approx(69.0, abs=0.05)
    assert sum(v["sum_net_bps"] for v in f.values()) == pytest.approx(-1958.5, abs=0.05)
    p = r["pass_line"]
    assert {k: v["run_days"] for k, v in p.items()} == {"F4:BTC": 0, "F4:ETH": 0, "F4:HYPE": 0, "F4:NEAR": 0, "F4:SOL": 3, "F4:ZEC": 0}
    assert all(v["k"] == 5 and not v["candidate"] and not v["two_sigma_clears"] for v in p.values())
    assert p["F4:SOL"]["mean_net_bps"] == pytest.approx(3.27, abs=0.005) and p["F4:SOL"]["n_episodes"] == 51
    assert p["F4:ZEC"]["n_episodes"] == 103 and p["F4:NEAR"]["mean_net_bps"] == pytest.approx(20.97, abs=0.005)
    disc = r["void_day_disclosure"]
    assert disc["2026-11-06"]["episodes"] == 61 and disc["2026-11-06"]["sum_net_bps"] == pytest.approx(-2137.5, abs=0.05)
    assert disc["2026-11-07"]["episodes"] == 45 and disc["2026-11-07"]["sum_net_bps"] == pytest.approx(-362.4, abs=0.05)
    assert disc["2026-11-07"]["forks"]["F4:HYPE"] == {"n": 5, "sum_net_bps": pytest.approx(204.4, abs=0.05)}
    # the void days read themselves: disclosed, pinned, and the day marked void by row
    r7 = rd.read(d, "2026-11-07", DAYS, 6)
    assert r7["episodes"] == 45 and r7["health"]["day_void_by_row"] is True and r7["health"]["day_void_by_state"] is False
    assert r7["pass_line"]["F4:SOL"]["run_days"] == 3


def test_r116_r117_the_ledger_on_the_real_pins():
    m07 = led.ledger("2026-11-07")
    assert m07["days"] == ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-07"]      # A17.10's, unchanged
    assert m07["readings"]["2026-11-07"] == "marks_2026-11-07.jsonl" and "2026-11-05" not in m07["readings"]
    assert m07["readings"]["2026-11-04"] == "marks_2026-11-04.jsonl"                 # R117: the 11-08 re-pin is not read as of 11-07
    m08 = led.ledger("2026-11-08")
    assert m08["days"][:5] == DAYS[:5] and "2026-11-06" not in m08["days"] and "2026-11-07" not in m08["days"]
    assert m08["readings"]["2026-11-05"] == NEWEST["2026-11-05"] and m08["readings"]["2026-11-07"] == NEWEST["2026-11-07"]
    assert m08["readings"]["2026-11-04"] == "marks_2026-11-04_as_read_2026-11-08.jsonl"   # A27 (1): the 97-row book from 11-08 on
    assert set(m08["void_days_excluded"]) == {"2026-11-06", "2026-11-07"}
    assert m08["void_days_excluded"]["2026-11-07"] == {"void_marks": 3, "episodes_not_counted": 45}
    sol = next(r for r in m08["forks"] if r["fork"] == "F4:SOL")
    if m08["days"] == DAYS[:5]:                       # until the routine pins 2026-11-08
        # A27 (1) amended this line; A26.1 wrote `assert sol["run_days"] == 3 and sol["episodes"] == 51 and sol["days_alive"] == 5`
        # on the 81-row 11-04 pin; the rule under test did not change, the book did (16 late episodes, 2 of them SOL).
        assert sol["run_days"] == 3 and sol["episodes"] == 53 and sol["days_alive"] == 5
        assert sol["mean_net_bps"] == pytest.approx(3.55, abs=0.005)
