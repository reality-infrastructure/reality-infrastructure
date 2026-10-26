"""P9c gates (PREREG A8): the chain's `fee` already includes `builderFee`. The R11 rule
double-counted it on every LIVE leg; the committed captures stand as computed (R42) and
the corrected figures are asserted here from the pinned chain payloads themselves.
"""

from __future__ import annotations

import json
from decimal import Decimal

from rights_events import agent_record as runner

_FIX = runner._FIXTURE.parent

# day -> (open fills payload, close fills payload, venue closedPnl, chain fee both legs,
#         realized corrected, R11 fees as the committed captures carry them)
DAYS = {
    "3": ("hl_userFillsByTime_1792823307404.json", "hl_userFillsByTime_1792824335531.json",
          "-0.0028", "0.021076", "-0.023876", "0.032383"),
    "4": ("hl_userFillsByTime_1792907352982.json", "hl_userFillsByTime_1792919726408.json",
          "-0.05768", "0.020957", "-0.078637", "0.032200"),
    "5": ("hl_userFillsByTime_1792989678024.json", "hl_userFillsByTime_1793002265325.json",
          "-0.04634", "0.020823", "-0.067163", "0.031994"),
}


def _rows(name):
    rows = json.loads((_FIX / name).read_text(encoding="utf-8"))
    assert len(rows) == 1
    return rows


def test_a8_corrected_figures_from_the_pinned_payloads():
    for day, (o, c, closed, fee_chain, realized, r11) in DAYS.items():
        rows = _rows(o) + _rows(c)
        chain = sum(Decimal(r["fee"]) for r in rows)
        builder = sum(Decimal(r["builderFee"]) for r in rows)
        assert chain == Decimal(fee_chain), day
        assert chain + builder == Decimal(r11), day                 # the double count
        assert Decimal(closed) - chain == Decimal(realized), day
        assert all(Decimal(r["fee"]) > Decimal(r["builderFee"]) for r in rows), day   # S39


def test_a8_fee_decomposition_is_the_schedule():
    """Every LIVE row: fee - builderFee = 4.5 bps x 0.96 (the referral's 4 %) of the
    notional, builderFee = 5.0 bps of it, within rounding of the venue's 6 decimals."""
    for day, (o, c, *_rest) in DAYS.items():
        for r in _rows(o) + _rows(c):
            notional = Decimal(r["px"]) * Decimal(r["sz"])
            exch_bps = (Decimal(r["fee"]) - Decimal(r["builderFee"])) / notional * 10000
            builder_bps = Decimal(r["builderFee"]) / notional * 10000
            assert Decimal("4.31") < exch_bps < Decimal("4.33"), (day, exch_bps)
            assert Decimal("4.99") < builder_bps < Decimal("5.01"), (day, builder_bps)


def test_a8_the_day5_open_moved_the_account_by_fee_alone():
    """A8's balance arithmetic: 19.896976 (preflight) - 19.885703 (after the fill, with
    unrealized -0.00084) = the fill's `fee` 0.010433 + 0.00084, not fee + builderFee."""
    row = _rows("hl_userFillsByTime_1792989678024.json")[0]
    diff = Decimal("19.896976") - Decimal("19.885703")
    assert diff == Decimal(row["fee"]) + Decimal("0.00084")
    assert diff != Decimal(row["fee"]) + Decimal(row["builderFee"]) + Decimal("0.00084")


def test_a8_referral_and_fee_schedule_pins():
    ref = json.loads((_FIX / "hl_referral_1792990054144.json").read_text(encoding="utf-8"))
    assert ref["referredBy"]["code"] == "3647SDFHJS924KAS"
    fees = json.loads((_FIX / "hl_userFees_1792990054415.json").read_text(encoding="utf-8"))
    assert fees["feeSchedule"]["cross"] == "0.00045" and fees["feeSchedule"]["add"] == "0.00015"


def test_a8_committed_captures_are_not_regenerated():
    """R42: the Day 3/4/5 captures keep their R11 fee figures byte-for-byte (their pins
    are asserted in their own gate files); the correction lives beside them."""
    for name, r11 in (("capture_LIVE_2026-10-24_pv_e1849abce514440c_close.json", "0.016190"),
                      ("capture_LIVE_2026-10-25_pv_aca51be96df9478c_close.json", "0.016059"),
                      ("capture_LIVE_2026-10-26_pv_e9e6406179d94a4f_close.json", "0.015964")):
        doc = json.loads((_FIX / name).read_text(encoding="utf-8"))
        assert doc["live_fill"]["fee_usd"] == r11
        assert "builder_fee_usd" not in doc["live_fill"]
