"""Fixture featurizers: the input buckets coverage is measured over (engine.coverage).  The allocator's
capacity falls in a band; the checker's input is its sheet."""

from __future__ import annotations

from engine.coverage import featurize

CAPACITY_BANDS = ((30, "small"), (50, "medium"))


@featurize(id="capacity_band")
def capacity_band(agent: str, run_input: dict) -> str | None:
    if agent not in ("allocator", "briefer") or not isinstance(run_input.get("capacity"), int):
        return None
    for upper, label in CAPACITY_BANDS:
        if run_input["capacity"] < upper:
            return label
    return "large"


@featurize(id="sheet")
def sheet(agent: str, run_input: dict) -> str | None:
    return str(run_input["sheet_id"]) if agent == "checker" and "sheet_id" in run_input else None
