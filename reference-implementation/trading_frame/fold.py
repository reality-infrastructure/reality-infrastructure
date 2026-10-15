"""The pure net_pnl_bucket conflict-mass fold (PATH B).

Pure function of its input event list: no network, no clock, no randomness.
It fuses two simple-support beliefs over the closed frame {GAIN, FLAT, LOSS}
with the Denœux cautious rule (ri_core.reconcile) and retains conflict mass
(mass on the empty set) verbatim — the quantity the frozen pipeline could not
express.

  - venue displayed bucket  -> self_asserted prior (0.30)
  - chain realized bucket    -> cryptographically_signed prior (0.55), where the
    realized net is the Decimal sum over the capture's signed fills of
    (realized_pnl_usdc - fee_usdc). Realized PnL is a chain-measured outcome of
    signed transactions, not an interested party's assertion; the dispute event
    (focal_mass 0 by the frozen dispute-fuses-vacuously rule) is not an input.

Reuses, by import only, the frozen rights_events.schema and
rights_events.policy (CLAIM_MASS); modifies neither.
"""

from __future__ import annotations

from decimal import Decimal

from ri_core.reconcile import BeliefWeights, cautious_fuse

from rights_events.adapters.trader_record import VENUE_CLAIMANT
from rights_events.policy import POLICY_VERSION
from rights_events.policy import CLAIM_MASS
from rights_events.schema import EPType, EventType, RightsEvent

FRAME: frozenset[str] = frozenset({"GAIN", "FLAT", "LOSS"})
QUESTION = "net_pnl_bucket"
_VENUE_MASS = CLAIM_MASS[EPType.SELF_ASSERTED]            # 0.30
_CHAIN_MASS = CLAIM_MASS[EPType.CRYPTOGRAPHICALLY_SIGNED]  # 0.55


class TradingFrameError(Exception):
    """Raised when a capture's events cannot pose the net_pnl_bucket question."""


def _bucket(net: Decimal) -> str:
    if net > 0:
        return "GAIN"
    if net < 0:
        return "LOSS"
    return "FLAT"


def _subset_key(subset: frozenset[str]) -> str:
    return ",".join(sorted(subset))


def _canon(value: Decimal) -> Decimal:
    """Canonical Decimal: drop scale noise so logged bytes are stable."""
    value = value.normalize()
    # normalize() can yield exponent form for integers (e.g. 0E-30 -> 0);
    # force plain zero and strip negative-zero.
    if value == 0:
        return Decimal(0)
    return value


def _venue(events: list[RightsEvent]) -> RightsEvent:
    found = [e for e in events
             if e.claimant == VENUE_CLAIMANT and "displayed_bucket" in e.claim]
    if len(found) != 1:
        raise TradingFrameError(
            f"expected exactly one venue claim (claimant {VENUE_CLAIMANT!r} "
            f"with a displayed_bucket); found {len(found)}")
    return found[0]


def chain_realized(events: list[RightsEvent]) -> tuple[Decimal, str]:
    """Decimal sum of (realized_pnl_usdc - fee_usdc) over fills, and its bucket.

    A fill is a chain_assertion event carrying realized_pnl_usdc (the venue
    claim is excluded: it carries displayed_bucket, not realized_pnl_usdc).
    """
    fills = [e for e in events
             if e.event_type is EventType.CHAIN_ASSERTION
             and "realized_pnl_usdc" in e.claim]
    if not fills:
        raise TradingFrameError("no fills to derive a chain-realized bucket")
    net = Decimal(0)
    for fill in fills:
        net += fill.claim["realized_pnl_usdc"] - fill.claim["fee_usdc"]
    return _canon(net), _bucket(net)


def fold_net_pnl_bucket(events: list[RightsEvent]) -> dict:
    """Fold trader_record events into a net_pnl_bucket belief with conflict mass.

    Pure: folding the same events twice is byte-equal. Returns the belief
    object WITHOUT a log root; the runner adds event_log_size/root before
    logging so the object stays a function of (events, log prefix).
    """
    if not events:
        raise TradingFrameError("no events to fold")
    subjects = {s for e in events for s in e.subject_ids}
    if len(subjects) != 1:
        raise TradingFrameError(
            f"events span {len(subjects)} subjects; expected one")
    subject = next(iter(subjects))

    venue = _venue(events)
    displayed_bucket = venue.claim["displayed_bucket"]
    if displayed_bucket not in FRAME:
        raise TradingFrameError(
            f"displayed_bucket {displayed_bucket!r} not in frame {sorted(FRAME)}")
    chain_net, chain_bucket = chain_realized(events)

    venue_belief = BeliefWeights.from_mass(FRAME, {
        frozenset({displayed_bucket}): _VENUE_MASS,
        FRAME: Decimal(1) - _VENUE_MASS,
    })
    chain_belief = BeliefWeights.from_mass(FRAME, {
        frozenset({chain_bucket}): _CHAIN_MASS,
        FRAME: Decimal(1) - _CHAIN_MASS,
    })
    fused = cautious_fuse(venue_belief, chain_belief)

    mass = {_subset_key(subset): _canon(value)
            for subset, value in fused.to_mass_dict().items()}
    omega_key = _subset_key(FRAME)

    return {
        "kind": "trading_frame_belief",
        "policy_version": POLICY_VERSION,
        "question": QUESTION,
        "subject": subject,
        "frame": sorted(FRAME),
        "mass": mass,
        "conflict_mass": mass[""],
        "unresolved_set": omega_key,
        "unresolved_mass": mass[omega_key],
        "displayed_bucket": displayed_bucket,
        "displayed_mass": mass.get(displayed_bucket, Decimal(0)),
        "chain_bucket": chain_bucket,
        "chain_mass": mass.get(chain_bucket, Decimal(0)),
        "chain_net_pnl_usdc": chain_net,
        "contributing": [
            {"role": "venue_displayed", "claimant": venue.claimant,
             "ep_type": EPType.SELF_ASSERTED.value, "bucket": displayed_bucket,
             "prior_mass": _VENUE_MASS},
            {"role": "chain_realized", "claimant": "chain-realized-sum",
             "ep_type": EPType.CRYPTOGRAPHICALLY_SIGNED.value,
             "bucket": chain_bucket, "prior_mass": _CHAIN_MASS},
        ],
    }
