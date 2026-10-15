"""trading_frame — a sibling domain layer on ri_core (PATH B).

It expresses the `net_pnl_bucket` Dempster-Shafer conflict-mass fold that the
frozen `rights_events.pipeline.map_event` declines (Gate-0 finding, see
contracts/trader_record/CONTRACT.md). It is built directly on `ri_core`
(reconcile, log, project, serialization) — the same move `rights_events` made —
and reuses, by import only, the frozen `rights_events.schema`,
`rights_events.policy` (EP mass priors), and the pure PATH A adapter
`rights_events.adapters.trader_record`. It modifies no frozen module and never
routes a trading question through `rights_events.pipeline`.
"""

from trading_frame.fold import (
    FRAME,
    TradingFrameError,
    chain_realized,
    fold_net_pnl_bucket,
)

__all__ = [
    "FRAME",
    "TradingFrameError",
    "chain_realized",
    "fold_net_pnl_bucket",
]
