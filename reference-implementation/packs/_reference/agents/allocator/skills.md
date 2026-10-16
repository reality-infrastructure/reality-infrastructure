# allocator — skills (fixture)

## Mission
Propose the subset of `candidates` with the greatest total value whose total
weight fits the capacity in the input. Explain the choice.

## Definition of good output
`selected` lists row ids; `items` copies each selected row's weight and value
with a citation per field (`table:candidates:<id>`); `total_weight` and
`total_value` are the sums. The verifier recomputes the sums, checks the
capacity, and checks optimality: a feasible but suboptimal proposal is
rejected with the attainable value named.

## Good
capacity 20 → selected [c4, c5], total_weight 20, total_value 110.

## Bad
capacity 20 → selected [c1, c5] (80; 110 attainable); any total that does
not equal the sum of the cited rows.
