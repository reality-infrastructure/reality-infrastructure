# Ablation Results — M-RI-09

Sybil-calibration ablation experiment. All values are deterministic Decimal
strings computed under `Context(prec=50, ROUND_HALF_EVEN)`, quantized to 30
decimal places.

## Scenario A: Reinforcement

Alice m({a})=0.6, m(Omega)=0.4; adversary m({a})=0.9, m(Omega)=0.1.
Measured quantity: m({a}) — plausibility of the adversary-favored hypothesis.

| k  | Full Stack                           | F1 (Average)                         | F2 (Dempster)                        | F3 (ContentDedup)                    |
|----|--------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|
| 1  | 0.900000000000000000000000000000     | 0.750000000000000000000000000000     | 0.960000000000000000000000000000     | 0.959999999999999999996000000000     |
| 2  | 0.900000000000000000000000000000     | 0.800000000000000000000000000000     | 0.996000000000000000000000000000     | 0.995999999999999999998800000000     |
| 5  | 0.900000000000000000000000000000     | 0.850000000000000000000000000000     | 0.999996000000000000000000000000     | 0.999995999999999999999994000000     |
| 10 | 0.900000000000000000000000000000     | 0.872727272727272727272727272727     | 0.999999999960000000000000000000     | 0.999999999959999999999999999780     |
| 25 | 0.900000000000000000000000000000     | 0.888461538461538461538461538462     | 0.999999999999999999999999960000     | 0.999999999999999999999999960000     |
| 50 | 0.900000000000000000000000000000     | 0.894117647058823529411764705882     | 1.000000000000000000000000000000     | 1.000000000000000000000000000000     |

## Scenario B: Contradiction Erasure

Alice m({a})=0.6, m(Omega)=0.4; adversary m({b})=0.9, m(Omega)=0.1.
Measured quantity: m({b}).

Full stack (all k):
m(emptyset)=0.540000000000000000000000000000,
m({b})=0.360000000000000000000000000000,
m({a})=0.060000000000000000000000000000,
m(Omega)=0.040000000000000000000000000000.

| k  | Full Stack                           | F1 (Average)                         | F2 (Dempster)                        |
|----|--------------------------------------|--------------------------------------|--------------------------------------|
| 1  | 0.360000000000000000000000000000     | 0.450000000000000000000000000000     | 0.782608695652173913043478260870     |
| 2  | 0.360000000000000000000000000000     | 0.600000000000000000000000000000     | 0.975369458128078817733990147783     |
| 5  | 0.360000000000000000000000000000     | 0.750000000000000000000000000000     | 0.999975000374994375084373734394     |
| 10 | 0.360000000000000000000000000000     | 0.818181818181818181818181818182     | 0.999999999750000000037499999994     |
| 25 | 0.360000000000000000000000000000     | 0.865384615384615384615384615385     | 0.999999999999999999999999749999     |
| 50 | 0.360000000000000000000000000000     | 0.882352941176470588235294117647     | 0.999999999999999999999999999999     |

## Level vs Flatness

The full stack (cautious fusion with provenance tracking) is exactly flat across
all k values in both scenarios. The fused belief is byte-identical regardless of
how many provenance-correlated duplicates the adversary injects, including under
trivially varied content (A1 amendment).

All three foils (F1, F2, F3) show strict monotonic increase in k. F2 (Dempster)
and F3 (content-dedup) converge to 1.0 at k=50 due to quantization. F1
(averaging) converges more slowly but is still unbounded as k grows.

In Scenario B, the full stack preserves the contradiction (m(emptyset)=0.54)
while both F1 and F2 erase it: Dempster normalizes conflict mass to zero by
construction, and averaging dilutes it. Neither foil can represent contradiction
as a first-class element.

## Two-Component Variant Matrix

| Variant                              | Bounded? | Correct? | Failure Mode                         |
|--------------------------------------|----------|----------|--------------------------------------|
| Full stack (provenance + cautious + belief) | Yes | Yes | (none — thesis holds)         |
| {provenance + belief} — Dempster     | No       | —        | Belief inflates with k               |
| {reconciliation + belief} — no provenance | Yes | No  | Cannot distinguish Sybil from independent; polynomial shows k degree-1 terms instead of one degree-k monomial |

No two-component sub-composition stays both bounded AND correct. The three-way
coupling of provenance identity, idempotent reconciliation, and conjunctive-weight
belief representation is the minimal composition for Sybil-calibration.
Falsification check NEGATIVE — Stage-2 verdict (weak emergence) survives.
