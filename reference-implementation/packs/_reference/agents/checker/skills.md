# checker — skills (fixture)

## Mission
Recompute every row of the requested sheet and flag the rows whose claimed
total does not match the expression.

## Definition of good output
One item per row of the sheet, no row missing, no row from another sheet.
`claimed` is copied from the row and cites it (`table:sheets:<id>`, field
`claimed`). `recomputed` comes from the arithmetic tool. `flag` is true iff
claimed ≠ recomputed. After the sheet is done, one `_reference.sheet_checked`
event records which rows were flagged.

## Good
`{"row_id": "S1-2", "claimed": 41, "recomputed": 42, "flag": true, "citations": [{"ref": "table:sheets:S1-2", "field": "claimed"}]}`

## Bad
A row with `flag: false` where claimed and recomputed differ; an item without
a citation; a sheet with a row skipped.
