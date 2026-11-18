"""Fixture value: an allocation at a larger capacity commits more, so its certified answer is worth more (a labeled,
synthetic stand-in for the size of the decision an output feeds)."""

from __future__ import annotations

from engine.value import value

CAPACITIES = (10, 20, 30, 40, 50, 60)


@value(id="_reference.capacity_at_stake", agent="allocator")
def capacity_at_stake(vctx) -> list[dict]:
    return [{"input": {"capacity": c}, "value": c, "why": f"capacity {c} is the size of the commitment"} for c in CAPACITIES]
