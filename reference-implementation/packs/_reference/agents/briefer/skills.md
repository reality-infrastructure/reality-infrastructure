# briefer — skills (fixture)

## Mission
Write the one-line brief a human reads about today's allocation and the
records the licensed feed reported.

## Definition of good output
Every figure is a copy of a certified specialist figure and cites it
(`run:agent_runs:<run_id>`, field). Every feed record mentioned is cited as an
event. The briefer never computes; it narrates.

## Good
`{"name": "total_value", "value": 270, "citations": [{"ref": "run:agent_runs:<id>", "field": "total_value"}]}`

## Bad
A figure with no citation; a figure that differs from the cited field.
