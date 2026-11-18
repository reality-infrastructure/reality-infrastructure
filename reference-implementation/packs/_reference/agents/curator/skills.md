# curator — skills (fixture)

## Mission
Grow the practice set where it teaches something: propose new cases (an input
and the expected output) for the agent the loop names, aimed at inputs the
agent's models disagree on. Code certifies each expected output with the
agent's verifier and measures how often the agent's models fail the case; only
correct cases inside the difficulty band are admitted.

## Definition of good output
Every case has an input no golden or held-out case already has, an expected
output carrying every compared field, and a `why` naming what it tests.

## Good
`{"agent": "allocator", "cases": [{"id": "cap35", "input": {"capacity": 35}, "expected": {"selected": ["c2", "c4"], "total_weight": 35, "total_value": 190}, "why": "ratio-greedy picks c1+c4+c5"}], "why": "...", "confidence": 0.7}`

## Bad
A case already in the set; an expected output that is not the true answer; a
case every model already passes.
