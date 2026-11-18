"""Tiering of the allocator's inputs (engine.curriculum ``@tier``): a larger capacity is a harder knapsack.

Not registered in pack.yaml by default, so the blueprint's sweeps run untiered; a pack that wants an
easy-first curriculum lists it under ``modules.tiers``.
"""

from engine.curriculum import tier


@tier(agent="allocator")
def allocator_tier(run_input: dict) -> int:
    return 1 if int(run_input.get("capacity", 0)) <= 30 else 2
