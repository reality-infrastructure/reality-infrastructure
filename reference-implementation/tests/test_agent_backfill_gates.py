"""Gates on the ablation history (PREREG A13 R70, A13.3, P11c): the pinned 15-minute candles
and hourly funding for the six declared coins are the bytes the manifest names, contiguous
over the 52 days the venue serves, and the summaries are pure. Offline, no network."""
from __future__ import annotations

import hashlib
import importlib.util
import json

import pytest

from rights_events import agent_record as runner

_FIX = runner._FIXTURE.parent
MANIFEST = _FIX / "backfill_MANIFEST_1793293240584.json"
DECLARED_DAY8 = ["BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR"]
CANDLES_SERVED = 4993            # what the venue served for 52 requested days of 15m (R70: ~5 000)
FUNDING_PRINTS = 1248            # 52 days x 24 hourly prints
MIN_SPAN_DAYS = 51.9


@pytest.fixture(scope="module")
def bf():
    spec = importlib.util.spec_from_file_location("agent_record_backfill_hl", _FIX / "backfill_hl.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_covers_exactly_the_declared_set(manifest):
    assert sorted(manifest["coins"]) == sorted(DECLARED_DAY8)
    assert manifest["requested"] == {"interval": "15m", "days": 52,
                                     "startTime": manifest["fetched_ms"] - 52 * 86_400_000,
                                     "endTime": manifest["fetched_ms"]}


@pytest.mark.parametrize("coin", DECLARED_DAY8)
def test_candles_pinned_contiguous_and_summarised_from_the_bytes(bf, manifest, coin):
    c = manifest["coins"][coin]["candles"]
    raw = (_FIX / c["file"]).read_bytes()
    assert len(raw) == c["bytes"] and hashlib.sha256(raw).hexdigest() == c["sha256"]
    s = bf.candle_summary(raw, "15m")
    assert s == {k: c[k] for k in s}
    assert s["n"] == CANDLES_SERVED and s["gaps"] == 0 and s["coin_mismatch"] == 0
    assert s["interval_ok"] and s["span_days"] >= MIN_SPAN_DAYS
    assert json.loads(raw)[0]["s"] == coin


@pytest.mark.parametrize("coin", DECLARED_DAY8)
def test_funding_pinned_hourly_and_summarised_from_the_bytes(bf, manifest, coin):
    f = manifest["coins"][coin]["funding"]
    pages = []
    for item in f["files"]:
        raw = (_FIX / item["file"]).read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        pages.append(raw)
    s = bf.funding_summary(pages)
    assert s == {k: f[k] for k in s}
    assert s["n"] == FUNDING_PRINTS and s["gaps"] == 0 and s["dupes"] == 0 and s["coin_mismatch"] == 0
    assert s["span_days"] >= MIN_SPAN_DAYS
    assert json.loads(pages[0])[0]["coin"] == coin


def test_candle_summary_counts_a_skipped_candle_as_a_gap(bf):
    rows = [{"t": 0, "T": 899_999, "s": "X", "i": "15m"},
            {"t": 900_000, "T": 1_799_999, "s": "X", "i": "15m"},
            {"t": 2_700_000, "T": 3_599_999, "s": "X", "i": "15m"}]     # the 1 800 000 candle missing
    s = bf.candle_summary(json.dumps(rows).encode(), "15m")
    assert s["n"] == 3 and s["gaps"] == 1 and s["interval_ok"]
    assert bf.candle_summary(b"[]", "15m")["n"] == 0


def test_funding_summary_tolerates_ms_jitter_but_not_a_missing_hour(bf):
    h = 3_600_000
    rows = [{"coin": "X", "time": 43}, {"coin": "X", "time": h + 29}, {"coin": "X", "time": 3 * h + 51}]
    s = bf.funding_summary([json.dumps(rows).encode()])
    assert s["n"] == 3 and s["gaps"] == 1 and s["dupes"] == 0
    dup = bf.funding_summary([json.dumps(rows[:2]).encode(), json.dumps(rows[1:2]).encode()])
    assert dup["dupes"] == 1


def test_backfill_tool_observes_only(bf):
    """The tool posts only the two read-only info queries; no exchange endpoint, no gdex."""
    import re
    src = (_FIX / "backfill_hl.py").read_text(encoding="utf-8")
    assert bf.HL_INFO_URL.endswith("/info") and "/exchange" not in src and "gdex" not in src.lower()
    assert set(re.findall(r'"type": "(\w+)"', src)) == {"candleSnapshot", "fundingHistory"}
