"""Pipeline: schema events -> engine intake -> fold -> belief objects.

Engine boundary (Contract 1, Constraint 1; finding F1 in PROGRESS.md):
- intake reuses ri_core.project.submit() — signature binding, duplicate
  rejection, EP uncertaintyType validation, Merkle log append,
  provenance attribution;
- fusion reuses ri_core.reconcile (BeliefWeights, cautious_fuse);
- logging and proofs reuse ri_core.log (EvidenceLog, inclusion proofs);
- serialization reuses ri_core.serialization.encode/decode.
Revocation is a cross-event relation the engine's projection cannot
express (F1), so the fold between intake and fusion is domain code.
Nothing in the engine is modified.

Contested-question mapping (declared, domain-neutral):
- an event whose claim carries "share_claims" (grant, term_change, or
  chain_assertion) poses the question "ownership_shares"; its
  hypothesis is the canonical share table
  ("shares:partyA=60;partyB=40" — semicolons, because the engine
  forbids commas in frame elements);
- an opt_out event poses "use_reservation" with hypothesis "reserved";
  the frame always includes the declared counter-hypothesis
  "not_reserved" so reservation is a genuine question;
- dispute and revocation events attach to the question their
  prior_event_refs map to; disputes contribute vacuously (policy),
  revocations remove claims (fold rule below);
- all other events are logged as records (trivial single-label frame,
  certainty that the assertion was made) and pose no question here.

The observation payload's own frame/mass is the event's claim label
with mass 1: the record that THIS WAS CLAIMED is certain even though
the claim itself is not.  Question beliefs are never read from payload
masses; the fold rebuilds them from the event and the declared policy.

Revocation fold rule (declared): a claim event E is revoked at as_of
iff some revocation event R with ltime(R) <= as_of lists E.event_id in
prior_event_refs and R.claimant == E.claimant — only the claimant can
withdraw their own claim.  Revoked claims are excluded from fusion but
stay in the log and in the belief object's contributing events.

Frames are built from every mapped claim event in the as_of prefix,
revoked or not, so pre- and post-revocation beliefs share a frame and
are directly comparable.  A one-element frame with no declared
counter-hypothesis is uncontested: its claims carry no discriminating
mass and the belief is vacuous by construction.

The belief object names the ignorance set explicitly (unresolved_set,
unresolved_mass) and reports retained conflict (conflict_mass) — the
unnormalized combination keeps contradiction visible instead of
normalizing it away (plan-gate ruling 2).

Determinism: fixed anchor seed (HMAC keys are a pure function of seed
and name), ingest order sorted by (ltime, event_id), sorted iteration
everywhere, Decimal-only arithmetic, no wall clock anywhere.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog, InclusionProof
from ri_core.project import submit
from ri_core.provenance import ProvenanceGraph
from ri_core.reconcile import BeliefWeights, cautious_fuse
from ri_core.serialization import decode, encode

from rights_events.policy import (
    POLICY_VERSION,
    focal_mass,
    ltime_for,
    uncertainty_type,
)
from rights_events.schema import EventType, RightsEvent


class PipelineError(Exception):
    """Error in pipeline operations.

    Raised for: unknown subject/question folds, commit of an empty
    question, malformed run files, and events that cannot be mapped
    deterministically.
    """


_ANCHOR_ID = "rights-events"
_ANCHOR_SEED = b"rights-events-domain-v1"
_RUN_KIND = "rights_run"
_BELIEF_KIND = "rights_belief"

# Declared counter-hypotheses completing single-sided questions.
_EXTRA_FRAME: dict[str, tuple[str, ...]] = {
    "use_reservation": ("not_reserved",),
}


def _canonical_decimal(value: Decimal) -> str:
    """Plain-form decimal string without exponent or trailing zeros."""
    return format(value.normalize(), "f")


def map_event(event: RightsEvent) -> tuple[str, str] | None:
    """Map an event to (question, hypothesis), or None if it poses none.

    Declared mapping — see the module docstring.  Deterministic pure
    function of the event.
    """
    if event.event_type in (EventType.GRANT, EventType.TERM_CHANGE,
                            EventType.CHAIN_ASSERTION):
        shares = event.claim.get("share_claims")
        if isinstance(shares, dict) and shares:
            parts = ";".join(
                f"{party}={_canonical_decimal(value)}"
                for party, value in sorted(shares.items()))
            return ("ownership_shares", f"shares:{parts}")
    if event.event_type is EventType.OPT_OUT:
        return ("use_reservation", "reserved")
    return None


class RightsPipeline:
    """Event intake, question folds, and belief-object commits.

    One event log (signed observations, one per rights event) and one
    belief log (serialized belief objects); both are engine EvidenceLog
    instances with inclusion proofs.
    """

    def __init__(self) -> None:
        self.authority = LocalAuthority(
            anchor_id=_ANCHOR_ID, seed=_ANCHOR_SEED)
        self.event_log = EvidenceLog()
        self.belief_log = EvidenceLog()
        self.graph = ProvenanceGraph()
        self._issued: set[str] = set()
        self._log_index: dict[str, int] = {}  # event_id -> event log index

    # -- Intake --------------------------------------------------------

    def _identity_for(self, claimant: str) -> Identity:
        if claimant not in self._issued:
            self.authority.issue_identity(claimant)
            self._issued.add(claimant)
        return Identity(identity_id=claimant, anchor_id=_ANCHOR_ID,
                        name=claimant)

    def _observation(self, event: RightsEvent) -> dict:
        mapping = map_event(event)
        question = mapping[0] if mapping else None
        hypothesis = mapping[1] if mapping else None
        claim_label = hypothesis if hypothesis else "recorded"
        if "," in claim_label:
            raise PipelineError(
                f"Hypothesis label may not contain a comma: "
                f"{claim_label!r}")
        subject = event.subject_ids[0]
        unsigned = {
            "kind": "observation",
            "id": event.event_id,
            "source_id": event.claimant,
            "proposition": (f"{subject}|{question}" if question
                            else f"{subject}|record"),
            "payload": {
                "frame": [claim_label],
                "mass": {claim_label: Decimal(1)},
                "uncertaintyType": uncertainty_type(event.ep_type),
                "event": event.to_dict(),
                "question": question,
                "hypothesis": hypothesis,
            },
            "ltime": ltime_for(event.observed_date),
        }
        identity = self._identity_for(event.claimant)
        sig = self.authority.sign(identity, encode(unsigned))
        obs = dict(unsigned)
        obs["sig"] = sig
        return obs

    def ingest(self, events: list[RightsEvent]) -> dict[str, int]:
        """Submit events through the engine in deterministic order.

        Order: (ltime, event_id).  Returns event_id -> log index.
        Duplicate event ids are rejected by the engine (submit()).
        """
        ordered = sorted(
            events, key=lambda e: (ltime_for(e.observed_date), e.event_id))
        indices: dict[str, int] = {}
        for event in ordered:
            obs = self._observation(event)
            idx, _entity = submit(
                obs, self.event_log, self.graph, self.authority)
            indices[event.event_id] = idx
            self._log_index[event.event_id] = idx
        return indices

    # -- Fold ----------------------------------------------------------

    def _decoded_observations(self, size: int) -> list[tuple[int, dict]]:
        out = []
        for idx in range(size):
            entry = decode(self.event_log.entry(idx))
            if isinstance(entry, dict) and entry.get("kind") == "observation":
                out.append((idx, entry))
        return out

    def fold(self, subject: str, question: str, as_of: int,
             at_size: int | None = None) -> dict:
        """Deterministic fold: event-log prefix -> belief object dict.

        Pure function of the log content, the declared policy, as_of,
        and at_size.  at_size anchors the fold to a log prefix (the
        replay CLI passes the belief's recorded event_log_size so a
        commit stays byte-reproducible after the log grows); None means
        the full current log.  See the module docstring for fold rules.
        """
        size = len(self.event_log) if at_size is None else at_size
        if size < 1 or size > len(self.event_log):
            raise PipelineError(
                f"at_size {size} out of range [1, {len(self.event_log)}]")
        observations = [
            (idx, obs) for idx, obs in self._decoded_observations(size)
            if obs["ltime"] <= as_of
        ]

        # event_id -> (question, hypothesis, event, log_index, obs)
        records: dict[str, tuple] = {}
        for idx, obs in observations:
            event = RightsEvent.from_dict(obs["payload"]["event"])
            records[event.event_id] = (
                obs["payload"]["question"], obs["payload"]["hypothesis"],
                event, idx, obs)

        def on_question(event_id: str) -> bool:
            rec = records.get(event_id)
            return (rec is not None and rec[0] == question
                    and subject in rec[2].subject_ids)

        claims: list[tuple] = []
        informational: list[tuple] = []
        revocations: list[tuple] = []
        for event_id in sorted(records):
            q, hyp, event, idx, obs = records[event_id]
            if on_question(event_id):
                claims.append((event_id, hyp, event, idx, obs))
            elif event.event_type is EventType.DISPUTE and any(
                    on_question(r) for r in event.prior_event_refs):
                informational.append((event_id, None, event, idx, obs))
            elif event.event_type is EventType.REVOCATION and any(
                    on_question(r) for r in event.prior_event_refs):
                revocations.append((event_id, None, event, idx, obs))

        if not claims:
            raise PipelineError(
                f"No claim events for subject {subject!r} question "
                f"{question!r} at as_of {as_of}")

        # Revocation fold rule.
        revoked: set[str] = set()
        for _rev_id, _h, rev_event, _idx, _obs in revocations:
            for target in rev_event.prior_event_refs:
                if not on_question(target):
                    continue
                target_event = records[target][2]
                if target_event.claimant == rev_event.claimant:
                    revoked.add(target)

        # Frame: every mapped hypothesis in the prefix, revoked or not,
        # plus declared counter-hypotheses.
        frame_elements = {hyp for _e, hyp, _ev, _i, _o in claims}
        frame_elements.update(_EXTRA_FRAME.get(question, ()))
        frame = frozenset(frame_elements)

        # Beliefs: one simple support per active, non-vacuous claim.
        beliefs = [BeliefWeights.vacuous(frame)]
        contributing: list[dict] = []
        for event_id, hyp, event, idx, obs in claims:
            focal = focal_mass(event)
            singleton = frozenset({hyp})
            if event_id in revoked:
                status = "revoked"
                applied = Decimal(0)
            elif focal == 0 or singleton == frame:
                # Vacuous by policy, or uncontested one-element frame.
                status = "informational"
                applied = Decimal(0)
            else:
                status = "active"
                applied = focal
                beliefs.append(BeliefWeights.from_mass(frame, {
                    singleton: focal,
                    frame: Decimal(1) - focal,
                }))
            contributing.append({
                "event_id": event_id,
                "log_index": idx,
                "event_type": event.event_type.value,
                "ep_type": event.ep_type.value,
                "uncertainty_type": obs["payload"]["uncertaintyType"],
                "hypothesis": hyp,
                "status": status,
                "applied_mass": applied,
            })
        for event_id, _h, event, idx, obs in informational + revocations:
            contributing.append({
                "event_id": event_id,
                "log_index": idx,
                "event_type": event.event_type.value,
                "ep_type": event.ep_type.value,
                "uncertainty_type": obs["payload"]["uncertaintyType"],
                "hypothesis": None,
                "status": ("revocation"
                           if event.event_type is EventType.REVOCATION
                           else "informational"),
                "applied_mass": Decimal(0),
            })
        contributing.sort(key=lambda c: c["log_index"])

        fused = cautious_fuse(*beliefs)
        mass_dict = fused.to_mass_dict()
        omega_key = ",".join(sorted(frame))
        mass = {
            ",".join(sorted(subset)): value
            for subset, value in mass_dict.items()
        }

        return {
            "kind": _BELIEF_KIND,
            "policy_version": POLICY_VERSION,
            "subject": subject,
            "question": question,
            "as_of": as_of,
            "frame": sorted(frame),
            "mass": mass,
            # The ignorance set, named for non-specialists: mass here
            # means "unresolved between all hypotheses in the frame".
            "unresolved_set": omega_key,
            "unresolved_mass": mass[omega_key],
            # Retained conflict (mass on the empty set): evidence that
            # contradicts itself, kept visible, never normalized away.
            "conflict_mass": mass[""],
            "contributing_events": contributing,
            "event_log_size": size,
            "event_log_root": self.event_log.root(size),
        }

    # -- Commit and proofs ----------------------------------------------

    def commit(self, subject: str, question: str, as_of: int
               ) -> tuple[dict, int]:
        """Fold and append the belief object to the belief log.

        Returns (belief_object, belief_log_index).  The appended bytes
        are encode(belief_object) — the replay CLI byte-compares
        against exactly this entry.
        """
        belief = self.fold(subject, question, as_of)
        index = self.belief_log.append(belief)
        return belief, index

    def event_inclusion_proof(self, event_id: str) -> InclusionProof:
        """Inclusion proof for a contributing event in the event log."""
        if event_id not in self._log_index:
            raise PipelineError(f"Unknown event id: {event_id!r}")
        return self.event_log.inclusion_proof(self._log_index[event_id])

    def belief_inclusion_proof(self, index: int) -> InclusionProof:
        """Inclusion proof for a belief object in the belief log."""
        return self.belief_log.inclusion_proof(index)

    # -- Persistence -----------------------------------------------------

    def save(self, run_path: str | Path) -> bytes:
        """Write both logs to one canonical run file.  Returns the bytes."""
        run = {
            "kind": _RUN_KIND,
            "anchor_id": _ANCHOR_ID,
            "event_log": {
                "kind": "log_export",
                "entries": [self.event_log.entry(i)
                            for i in range(len(self.event_log))],
            },
            "belief_log": {
                "kind": "log_export",
                "entries": [self.belief_log.entry(i)
                            for i in range(len(self.belief_log))],
            },
        }
        data = encode(run)
        Path(run_path).write_bytes(data)
        return data

    @staticmethod
    def load(run_path: str | Path) -> "RightsPipeline":
        """Rebuild a pipeline from a run file.

        Observations are re-submitted through the engine (signatures
        re-verify: keys are a pure function of the fixed seed and
        claimant name), so a tampered event fails at intake.  Belief
        entries re-append byte-identically by canonical encoding.
        """
        try:
            run = decode(Path(run_path).read_bytes())
        except Exception as exc:
            raise PipelineError(f"Unreadable run file: {exc}") from exc
        if not isinstance(run, dict) or run.get("kind") != _RUN_KIND:
            raise PipelineError("Run file kind must be 'rights_run'")

        pipeline = RightsPipeline()
        for i, entry in enumerate(run["event_log"]["entries"]):
            try:
                obs = decode(entry)
                event = RightsEvent.from_dict(obs["payload"]["event"])
                pipeline._identity_for(event.claimant)
                idx, _entity = submit(
                    obs, pipeline.event_log, pipeline.graph,
                    pipeline.authority)
            except Exception as exc:
                raise PipelineError(
                    f"Event entry {i} failed intake on load: {exc}"
                ) from exc
            if pipeline.event_log.entry(idx) != entry:
                raise PipelineError(
                    f"Event entry {i} did not round-trip byte-identically")
            pipeline._log_index[event.event_id] = idx
        for i, entry in enumerate(run["belief_log"]["entries"]):
            try:
                idx = pipeline.belief_log.append(decode(entry))
            except Exception as exc:
                raise PipelineError(
                    f"Belief entry {i} failed decode on load: {exc}"
                ) from exc
            if pipeline.belief_log.entry(idx) != entry:
                raise PipelineError(
                    f"Belief entry {i} did not round-trip byte-identically")
        return pipeline
