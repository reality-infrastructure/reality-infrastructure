"""Fixture outcome: an allocation's stated total_value is a forward claim; fixtures/realized.jsonl is what the world
later paid out at each capacity, and when (a labeled, synthetic stand-in for a decision whose result arrives weeks later)."""

from __future__ import annotations

from engine.outcome import outcome
from engine.runtime import parse_iso


@outcome(id="_reference.realized_value")
def realized_value(octx, run) -> dict | None:
    claim = (run["output"] or {}).get("total_value")
    capacity = run["input"].get("capacity")
    for row in octx.read_table("realized"):
        if row["capacity"] == capacity and parse_iso(row["observed_at"]) <= octx.now:
            hit = row["realized_value"] >= claim
            return {"hit": hit, "claim": claim, "actual": row["realized_value"],
                    "why": f"claimed total_value {claim}; realised {row['realized_value']} at capacity {capacity} ({row['id']})"}
    return None
