"""Declared evidence policy for the rights-event layer.

DECLARED PRIORS, NOT MATH.  Everything in this module is policy: the
reference implementation's declared mapping from evidence-channel EP
types to (i) the engine's closed uncertaintyType vocabulary and (ii) the
mass an uncorroborated event of that channel contributes toward its
claimed hypothesis.  The fusion mathematics (Denoeux cautious rule,
ri_core.reconcile) is untouched by these numbers; they only shape the
input belief functions.

Amendment discipline (plan-gate ruling 3, 2026-08-01): changing any
value in this module is a policy change, not a bug fix.  It requires a
tagged commit and a written rationale, under the same amendment
discipline as NEUTRALITY.md.  Tests pin these values so an untagged
drive-by edit fails the suite.

The declared priors:

  statutory_registry        claim mass 0.6   uncertaintyType ["measured"]
  cryptographically_signed  claim mass 0.55  uncertaintyType ["measured"]
  third_party_attested      claim mass 0.45  uncertaintyType
                                             ["asserted-by-interested-party"]
  self_asserted             claim mass 0.3   uncertaintyType
                                             ["asserted-by-interested-party"]

Rationale for the ordering: a statutory register binds strongest; a
cryptographic signature binds a signer to bytes (the signing event is
measured; the signed content is NOT thereby true — see the C2PA adapter);
a third-party attestation transmits an interested party's claim through
a channel that logs it; a bare self-assertion carries the least.  The
attested and self-asserted channels sit below 0.5 deliberately: an
uncorroborated assertion should never push a contested singleton past
the ignorance mass on its own.

DISPUTE EVENTS FUSE VACUOUSLY (declared rule, same ruling): a dispute
event contributes claim mass 0 — its entire mass sits on the ignorance
set Omega.  A dispute documents that a question is contested; it is not
evidence for either answer, and it must never bias the fused belief.
It still appears in the log and in the belief object's contributing
events.

ltime derivation: the engine orders observations by integer logical
time.  ltime_for() maps observed_date to a proleptic Gregorian ordinal
(date.toordinal) — a pure function of fixture data, no wall clock, so
identical inputs give identical logs on any machine.

This module imports stdlib and rights_events.schema only.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from rights_events.schema import EPType, EventType, RightsEvent

# Version string recorded in every belief object (P3) so a serialized
# belief names the policy that produced it.
POLICY_VERSION = "rights-mass-policy-v1"

# EP channel type -> engine uncertaintyType terms (plan-gate ruling 1).
# Values are tuples here (immutability); the pipeline emits sorted lists.
# Terms must be members of ri_core.project.EP_UNCERTAINTY_VOCAB — pinned
# by test, not imported here, to keep this module engine-independent.
UNCERTAINTY_TYPE_MAP: dict[EPType, tuple[str, ...]] = {
    EPType.STATUTORY_REGISTRY: ("measured",),
    EPType.CRYPTOGRAPHICALLY_SIGNED: ("measured",),
    EPType.THIRD_PARTY_ATTESTED: ("asserted-by-interested-party",),
    EPType.SELF_ASSERTED: ("asserted-by-interested-party",),
}

# EP channel type -> mass toward the event's claimed hypothesis; the
# remainder goes to the ignorance set Omega.  Declared priors — see the
# module docstring for the amendment discipline.
CLAIM_MASS: dict[EPType, Decimal] = {
    EPType.STATUTORY_REGISTRY: Decimal("0.6"),
    EPType.CRYPTOGRAPHICALLY_SIGNED: Decimal("0.55"),
    EPType.THIRD_PARTY_ATTESTED: Decimal("0.45"),
    EPType.SELF_ASSERTED: Decimal("0.3"),
}


def uncertainty_type(ep_type: EPType) -> list[str]:
    """Engine uncertaintyType terms for an EP channel type, sorted list.

    Sorted because CF-020 sets are order-free and sorted form gives
    canonical bytes.
    """
    return sorted(UNCERTAINTY_TYPE_MAP[ep_type])


def focal_mass(event: RightsEvent) -> Decimal:
    """Mass this event contributes toward its claimed hypothesis.

    Dispute events return 0 (the dispute-fuses-vacuously rule); all
    other event types return the declared prior for their EP channel.
    """
    if event.event_type is EventType.DISPUTE:
        return Decimal(0)
    return CLAIM_MASS[event.ep_type]


def ltime_for(observed_date: str) -> int:
    """Deterministic logical time for an observed_date (ISO YYYY-MM-DD).

    Proleptic Gregorian ordinal of the date.  Pure function; the schema
    has already validated canonical form before events reach here.
    """
    return date.fromisoformat(observed_date).toordinal()
