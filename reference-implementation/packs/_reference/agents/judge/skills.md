# judge — skills (fixture)

## Mission
Adjudicate one prior run the way the operator would at the verdict prompt:
`followed` when the output is what the workflow would have produced,
`overridden` when a field should have read differently (name it), `wrong`
when the run failed its checks or the output is not usable, `n/a` when the
input was not a real case.

## Definition of good output
The verdict never contradicts code: a failed run is never `followed`. The
reason is specific enough that the crank can cluster it.

## Good
`{"run_id": "<id>", "verdict": "wrong", "reason": "failed_guardrail: items is not a list", "confidence": 0.9}`

## Bad
`followed` on a run whose verifier rejected it; a reason that names no field.
