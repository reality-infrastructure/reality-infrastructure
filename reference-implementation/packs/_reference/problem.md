# The one hard problem (fixture)

Given a table of candidate items, each with a weight and a value, and a
capacity, choose the subset that maximizes total value without exceeding the
capacity. Decision variables: include/exclude per item. Constraints: total
weight ≤ capacity; every item cited by row. Objective: maximize total value.
It stands in for the real domain's constrained allocation; the verifier
recomputes totals, checks feasibility and proves optimality by dynamic
programming, so a wrong proposal is rejected on evidence, not on vibes.
FIXTURE: this problem and its data are synthetic and labeled as such.
