"""Fixture drift: the sheets table is the world the checker's golden set came from; more than ten rows
means the world moved (a labeled, synthetic stand-in for a regime that shifted)."""

from __future__ import annotations

from engine.drift import drift

STEADY_ROWS = 10


@drift(id="_reference.sheets_grew")
def sheets_grew(dctx) -> dict:
    n = len(dctx.read_table("sheets"))
    return {"shifted": n > STEADY_ROWS, "why": f"sheets has {n} rows; the golden sets were counted on {STEADY_ROWS} or fewer",
            "measured": {"rows": n, "steady_max": STEADY_ROWS}}
