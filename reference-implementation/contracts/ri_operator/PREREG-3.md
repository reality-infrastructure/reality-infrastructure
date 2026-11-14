# PREREG: RI-OPERATOR-3

```
FROZEN at the commit that adds this file, before foresight.py, its events, its command
or its tests exist. Later changes are dated amendments below.
```

## Sources, hashed at copy time

- `~/hyperliquid/atlas/foresight.py`
  sha256 `709c27c3406029c1eb2c19c925d4032b2fa5e89d22583b0e41a0dbd9567d5332` (rules only; no code copied)
- `~/hyperliquid/.claude/commands/hype-foresight.md`
  sha256 `dce7777c6c526b819c9eb30a3452daf5ad27b98a081f6d77ce5585c1e7d3d3b1`

## Constants, taken from the source and not tuned

- Interval level: 80 percent. Penalty rate outside the interval: 2 / 0.2 = 10 per unit.
- Width of an 80 percent interval in standard deviations: 2.5631031.
- Like windows needed before the record is a rival: 5.
- A belief is flagged REVISE at 3 or more scored interval forecasts with mean bias beyond
  one standard deviation in one direction; TOO NARROW at 5 or more with under half held.

## Closed vocabulary

- Cause of a miss: `variance`, `model`, `overfit`, `execution`, `ops`, `regime`, `data`.
- Mechanical authors, allowed to write inside a window because they use only records that
  end before it: `baseline`, `persistence`. Every other author is held to the pen-down rule.
- Comparison operators for a probability: `>`, `>=`, `<`, `<=`.

## Known answers, declared before the build

1. A forecast by author `desk` written at a time inside its own window is refused.
2. A review with any cause other than `variance`, on a sheet where every interval held,
   is refused unless forced with outside evidence.
3. A second version of a belief is refused when fewer than three scored forecasts cite it.
4. A second forecast with the same sheet, author and metric is refused.
5. Interval 10 / 20 / 30 with actual 35 scores: held false, error 15, interval score 70
   (width 20 plus 10 times 5), bias 15 × 2.5631031 / 20 = 1.9223 to four places.

If any behaves otherwise: STOP and report.

## The first real sheet, declared before it is written

Subject `support-outsourcing`, window 2026-11-15T00:00Z to 2026-11-21T00:00Z, written on
2026-11-14 before the window opens. Metrics, each read from tier-one on or after
2026-11-21 by the command recorded with the settlement: rows marked sent in the prospect
file; replies in its log; signed clients. The numbers on the sheet are the agent's and are
written to the ledger, not here.

## Amendments

(none)
