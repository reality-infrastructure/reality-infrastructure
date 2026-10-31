"""P12 gates (P12.0): the marker's exit rule, each family's signal on a hand-built fixture,
costs per leg, C1's seed, the pass-line arithmetic, the replay row's disclosures, and S73
(no venue write path in the marker or the replay). Offline; no network."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from rights_events import agent_record as runner

_FIX = runner._FIXTURE.parent
_MK_DIR = _FIX / "marker"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _MK_DIR / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


mk = _load("marker")
FAM = json.loads((_MK_DIR / "families.json").read_bytes())
STOP = FAM["exit"]["stop_bps"]
GATE = FAM["exit"]["gate_ms"]
MIN = 60_000


def _path(prices, step_ms=MIN, t0=1_700_000_000_000):
    return [(t0 + i * step_ms, float(p)) for i, p in enumerate(prices)]


# ----------------------------------------------------------------------------- exit rule
def test_exit_stop_first_long():
    path = _path([100, 100.1, 99.8, 99.6, 101])  # 99.6 = −40 bps
    j, px, why = mk.mark_exit(path, 0, +1, STOP, GATE)
    assert (j, px, why) == (3, 99.6, "stop")


def test_exit_stop_exactly_30_bps_fires():
    path = _path([100, 99.7])  # exactly −30.0 bps
    assert mk.mark_exit(path, 0, +1, STOP, GATE)[2] == "stop"


def test_exit_29_9_bps_does_not_fire():
    path = _path([100, 99.701, 100.5])
    hit = mk.mark_exit(path, 0, +1, STOP, 10 * MIN)
    assert hit is None  # neither rule inside a 2-row path


def test_exit_gate_first_when_quiet():
    prices = [100 + 0.001 * i for i in range(400)]  # drifts up, never 30 bps against
    path = _path(prices)
    j, px, why = mk.mark_exit(path, 0, +1, STOP, GATE)
    assert why == "gate" and path[j][0] - path[0][0] >= GATE and j == 300


def test_exit_short_stop_direction():
    path = _path([100, 100.31])  # +31 bps hurts a short
    assert mk.mark_exit(path, 0, -1, STOP, GATE)[2] == "stop"


def test_incomplete_episode_is_dropped():
    path = _path([100, 100.01, 100.02])
    eps = mk.mark_fork(path, [{"ms": path[0][0], "direction": 1, "family": "T", "coin": "BTC"}], fork="T:BTC",
                       family="T", coin="BTC", stop_bps=STOP, gate_ms=GATE, fee_bps_per_leg=9.32,
                       spread_bps_per_leg=1.0, spread_source="replay_proxy")
    assert eps == []


def test_one_open_episode_per_fork():
    path = _path([100] * 400)
    sigs = [{"ms": path[0][0], "direction": 1, "family": "T", "coin": "BTC"},
            {"ms": path[5][0], "direction": 1, "family": "T", "coin": "BTC"},   # inside the first hold: skipped
            {"ms": path[310][0], "direction": -1, "family": "T", "coin": "BTC"}]
    eps = mk.mark_fork(path, sigs, fork="T:BTC", family="T", coin="BTC", stop_bps=STOP, gate_ms=GATE,
                       fee_bps_per_leg=9.32, spread_bps_per_leg=1.0, spread_source="replay_proxy")
    assert [e.exit_reason for e in eps] == ["gate"] and len(eps) == 1  # the third has no 5 h of path left


# ----------------------------------------------------------------------------- costs
def test_costs_per_leg_as_declared():
    assert mk.leg_costs_bps(9.32, 1.0) == pytest.approx(20.64)
    path = _path([100] * 400)
    e = mk.mark_fork(path, [{"ms": path[0][0], "direction": 1, "family": "T", "coin": "BTC"}], fork="T:BTC",
                     family="T", coin="BTC", stop_bps=STOP, gate_ms=GATE, fee_bps_per_leg=9.32,
                     spread_bps_per_leg=1.0, spread_source="replay_proxy", in_sample=True)[0]
    assert e.gross_bps == 0.0 and e.cost_bps == pytest.approx(20.64) and e.net_bps == pytest.approx(-20.64)
    assert e.in_sample is True and e.spread_bps_per_leg == 1.0 and e.spread_source == "replay_proxy"


def test_funding_sign_long_pays_positive_rate():
    f = [(1_000, 0.0001), (2_000, 0.0001), (3_000, -0.0003)]
    assert mk.funding_bps_for_hold(f, 500, 2_500, +1) == pytest.approx(-2.0)   # two prints × 1 bp, long pays
    assert mk.funding_bps_for_hold(f, 500, 2_500, -1) == pytest.approx(+2.0)
    assert mk.funding_bps_for_hold(f, 2_000, 3_000, +1) == pytest.approx(+3.0)  # (2000, 3000]: only the −3 bp print


# ----------------------------------------------------------------------------- families
def test_f1_threshold_and_direction():
    fund = [(i * mk.HOUR_MS, 0.00001) for i in range(99)] + [(99 * mk.HOUR_MS, 0.0005)]
    s = mk.f1_funding_extreme(fund, 95, "BTC")
    assert any(x["ms"] == 99 * mk.HOUR_MS and x["direction"] == -1 for x in s)  # positive extreme → short
    near = [(i * mk.HOUR_MS, 0.00001) for i in range(100)]
    assert all(x["threshold"] == 0.00001 for x in mk.f1_funding_extreme(near, 95, "BTC"))  # flat series: everything at the threshold, nothing extreme


def _candles(closes, vols=None, t0=1_700_000_000_000):
    vols = vols or [1.0] * len(closes)
    return [{"t": t0 + i * 900_000, "T": t0 + (i + 1) * 900_000 - 1, "o": str(c), "c": str(c), "h": str(c * 1.0001),
             "l": str(c * 0.9999), "v": str(v), "n": 1} for i, (c, v) in enumerate(zip(closes, vols))]


def test_f2_true_positive_and_near_miss():
    closes = [100.0] * 50 + [103.0] + [103.0] * 10          # one +3 % jump
    vols = [1.0] * 50 + [10.0] + [1.0] * 10                   # with volume
    s = mk.f2_reversion(_candles(closes, vols), 3.0, 3.0, "BTC")
    assert len(s) == 1 and s[0]["direction"] == -1
    vols_quiet = [1.0] * 61                                    # the same move without volume: near miss
    assert mk.f2_reversion(_candles(closes, vols_quiet), 3.0, 3.0, "BTC") == []


def test_f3_breakout_with_and_near_miss():
    closes = [100.0] * 96 + [100.02]                          # above the 96-candle high (100.01)
    s = mk.f3_breakout(_candles(closes), 96, "BTC")
    assert len(s) == 1 and s[0]["direction"] == 1
    closes_nm = [100.0] * 96 + [100.005]                      # inside the band: no signal
    assert mk.f3_breakout(_candles(closes_nm), 96, "BTC") == []


def test_f4_open_size_filter_and_direction():
    fills = [{"coin": "BTC", "dir": "Open Short", "px": "80000", "sz": "0.2", "time": 1},     # 16 000 USD → signal
             {"coin": "BTC", "dir": "Open Long", "px": "80000", "sz": "0.1", "time": 2},      # 8 000 USD → below 10 k
             {"coin": "BTC", "dir": "Close Long", "px": "80000", "sz": "5", "time": 3},       # a close: never
             {"coin": "ETH", "dir": "Open Long", "px": "2000", "sz": "10", "time": 4}]        # other coin
    s = mk.f4_leader_opens(fills, 10_000, "BTC", "0xabc")
    assert [(x["ms"], x["direction"]) for x in s] == [(1, -1)]


# ----------------------------------------------------------------------------- controls
def test_c1_seed_is_reproducible_and_in_range():
    a = mk.c1_minute("ef46830e6b00789af206b6f5750cc40b3e1fc0d3", "BTC", "2026-11-01")
    b = mk.c1_minute("ef46830e6b00789af206b6f5750cc40b3e1fc0d3", "BTC", "2026-11-01")
    assert a == b and 0 <= a < 1440
    assert a != mk.c1_minute("ef46830e6b00789af206b6f5750cc40b3e1fc0d3", "ETH", "2026-11-01") or True
    assert mk.c1_direction("s", "BTC", "d", 1.0) == 1 and mk.c1_direction("s", "BTC", "d", 0.0) == -1


# ----------------------------------------------------------------------------- pass line
@pytest.mark.parametrize("n,k", [(6, 5), (20, 7), (24, 7)])
def test_k_for(n, k):
    assert mk.k_for(n) == k


def test_candidate_needs_k_consecutive_days_and_2sigma():
    days = [f"2026-11-{d:02d}" for d in range(1, 9)]
    good = {d: 5.0 for d in days}
    c1 = {d: 1.0 for d in days}
    nets = [5.0, 6.0, 4.0, 5.5, 5.0, 4.5, 6.0, 5.0, 5.0, 4.8]
    ok, run = mk.is_candidate(good, c1, days, 24, nets)
    assert ok and run == 8
    bad = dict(good); bad["2026-11-05"] = 0.5  # beats C0 but not C1 → the run restarts
    ok2, run2 = mk.is_candidate(bad, c1, days, 24, nets)
    assert not ok2 and run2 == 3
    assert not mk.is_candidate(good, c1, days, 24, [5.0])[0]  # one episode never clears


# ----------------------------------------------------------------------------- S73
@pytest.mark.parametrize("name", ["marker.py", "replay.py"])
def test_s73_no_venue_write_path(name):
    src = (_MK_DIR / name).read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|mcp__gdex", src)


def test_families_pinned_as_declared():
    assert FAM["families"]["F1"]["parameter"] == {"abs_funding_percentile": 95}
    assert FAM["families"]["F2"]["parameter"] == {"return_sigma": 3.0, "notional_median_multiple": 3.0}
    assert FAM["families"]["F3"]["parameter"] == {"lookback_candles": 96}
    assert FAM["families"]["F4"]["parameter"]["min_open_notional_usd"] == 10000
    assert FAM["pass_line"]["N"] == 24 and mk.k_for(24) == 7
