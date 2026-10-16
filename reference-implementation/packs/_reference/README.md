# _reference — the blueprint pack (fixture data, labeled)

Four agents, one slot, every engine mechanism exercised:

| agent | role | harnessed job | checks |
|---|---|---|---|
| checker | worker | manual arithmetic QA of a sheet | built-ins + `_reference.flags_consistent` (recomputes every row) |
| allocator | specialist | the knapsack allocation in `problem.md` | verifier `_reference.knapsack_feasible` (feasibility, recompute, DP optimality) |
| briefer | orchestrator | the brief a human reads | cites only certified figures (`cited_values_match`) |
| compactor | worker | rolling summaries of old events | `citations_resolve` on every cited event |

Models are deterministic fixture responders (`fixtures/responders.py`), declared
in `pack.yaml` as `local/<name>`. Faulty variants exist on purpose
(`checker-malformed`, `checker-snoop`, `allocator-infeasible`,
`allocator-misstated`, `allocator-greedy`) so the engine's failure paths are
proven, not assumed.

    python -m engine.validate _reference
    python -m engine.run _reference/checker --input '{"sheet_id": "S1"}'
    python -m engine.run _reference/briefer --input '{"capacity": 50}'
    python -m engine.eval _reference/allocator --models local/allocator-v1,local/allocator-greedy
    python -m engine.replay <run_id>

Everything under `fixtures/` is synthetic. Golden cases carry `fixture: true`.
