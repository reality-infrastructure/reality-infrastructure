# planner — skills (fixture)

## Mission
Decide the data: which agent runs on which input next, so the week's record
covers what the crank says is weak and nothing is run twice for nothing.

## Definition of good output
Every item names a worker, specialist or orchestrator of this pack with an
object input it accepts; no duplicates; at most `max_runs` items; `why` says
what the batch is meant to show.

## Good
`{"batch": [{"agent": "checker", "input": {"sheet_id": "S2"}}], "why": "S2 has no run this week", "confidence": 0.8}`

## Bad
An agent that does not exist; the same input twice; a batch over the cap.
