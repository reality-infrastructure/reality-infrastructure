"""Judgement: every candidate is judged inside Reality Infrastructure.

Each check on a candidate (guardrail, verifier) and the model's own stated
confidence become signed observations on an RI evidence log, one proposition
per candidate over the frame {accept, reject}.  ``ri_core.project`` fuses them
under the cautious rule.  The fused belief is persisted on the trace with the
log export and Merkle root, so ``engine.replay`` can rebuild it byte for byte.

Why it is load-bearing and not decorative:
- deterministic checks are EP-typed ``measured``; the model's confidence is
  ``asserted-by-interested-party`` and discounted (config/judgement.yaml);
- when a confident model fails a check, the fusion retains conflict mass
  m(empty) instead of averaging it away.  That number is the engine's
  calibration signal, reported by the crank per agent and per model.
The accept/reject DECISION stays deterministic (all guardrails pass and the
verifier certifies).  The belief is the auditable record of how the decision
was supported, and it is what a stranger can recompute.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.project import project, submit
from ri_core.provenance import ProvenanceGraph
from ri_core.reconcile import BeliefWeights
from ri_core.replay import export_log, replay
from ri_core.rules import RuleStore
from ri_core.serialization import encode

from engine.config import EngineConfig
from engine.errors import EngineError

_Q4 = Decimal("0.0001")


def _seed(pack_name: str, version: int) -> bytes:
    return hashlib.sha256(f"harness-judgement:v{version}:{pack_name}".encode("utf-8")).digest()


def _subset_key(subset: frozenset[str]) -> str:
    return ",".join(sorted(subset))


@dataclass(frozen=True)
class BeliefSummary:
    accept: Decimal
    reject: Decimal
    conflict: Decimal
    unresolved: Decimal

    def as_dict(self) -> dict:
        def s(d: Decimal) -> str:
            n = d.normalize()
            return "0" if n == 0 else format(n, "f")
        return {"accept": s(self.accept), "reject": s(self.reject),
                "conflict": s(self.conflict), "unresolved": s(self.unresolved)}


def summarize_belief(belief_dict: dict) -> BeliefSummary:
    frame = frozenset(belief_dict["frame"])
    weights = {}
    for key, w in belief_dict["weights"].items():
        subset = frozenset() if key == "" else frozenset(key.split(","))
        weights[subset] = Decimal(str(w))
    bw = BeliefWeights.from_weights(frame, weights)
    masses = bw.to_mass_dict()
    return BeliefSummary(
        accept=masses[frozenset({"accept"})],
        reject=masses[frozenset({"reject"})],
        conflict=masses[frozenset()],
        unresolved=masses[frame],
    )


class Judgement:
    """One judgement log per run; one proposition per candidate."""

    def __init__(self, config: EngineConfig, pack_name: str, run_id: str) -> None:
        self._cfg = config.judgement
        self._config_hash = config.judgement_hash
        self._pack = pack_name
        self._run_id = run_id
        version = int(self._cfg.get("version", 1))
        self._version = version
        self._authority = LocalAuthority(anchor_id=f"harness:{pack_name}", seed=_seed(pack_name, version))
        self._log = EvidenceLog()
        self._graph = ProvenanceGraph()
        self._identities: dict[str, Identity] = {}
        self._ltime = 0
        self._frame = tuple(self._cfg["frame"])
        if set(self._frame) != {"accept", "reject"}:
            raise EngineError("config/judgement.yaml frame must be exactly [accept, reject]")
        self._omega = _subset_key(frozenset(self._frame))
        self._candidates: list[str] = []

    # -- identities -----------------------------------------------------------

    def _identity(self, source_id: str) -> Identity:
        ident = self._identities.get(source_id)
        if ident is None:
            ident = self._authority.issue_identity(source_id)
            self._identities[source_id] = ident
        return ident

    # -- observations ---------------------------------------------------------------

    def _observe(self, candidate_key: str, source_id: str, mass: dict[str, Decimal],
                 uncertainty_type: list[str]) -> None:
        if candidate_key not in self._candidates:
            self._candidates.append(candidate_key)
        ident = self._identity(source_id)
        self._ltime += 1
        obs = {
            "kind": "observation",
            "id": f"{self._run_id}:{candidate_key}:{source_id}",
            "source_id": source_id,
            "proposition": f"candidate:{candidate_key}",
            "payload": {"frame": list(self._frame), "mass": mass, "uncertaintyType": uncertainty_type},
            "ltime": self._ltime,
        }
        unsigned = encode({k: v for k, v in obs.items() if k != "sig"})
        obs["sig"] = self._authority.sign(ident, unsigned)
        submit(obs, self._log, self._graph, self._authority)

    def observe_check(self, candidate_key: str, kind: str, check_id: str, passed: bool) -> None:
        """A deterministic check (guardrail or verifier) voted on a candidate."""
        weights = self._cfg["sources"][kind]
        w = Decimal(str(weights["pass" if passed else "fail"]))
        if not (Decimal(0) < w < Decimal(1)):
            raise EngineError(f"judgement weight for {kind}.{'pass' if passed else 'fail'} must be in (0,1)")
        target = "accept" if passed else "reject"
        self._observe(candidate_key, f"{kind}:{check_id}",
                      {target: w, self._omega: Decimal(1) - w},
                      list(self._cfg["sources"]["check_uncertainty_type"]))

    def observe_model_confidence(self, candidate_key: str, model_string: str, confidence) -> None:
        """The model's own stated confidence, discounted as an interested-party assertion."""
        src = self._cfg["sources"]["model_confidence"]
        discount = Decimal(str(src["discount"]))
        c = None
        if isinstance(confidence, (int, float, Decimal)) and not isinstance(confidence, bool):
            c = Decimal(str(confidence))
            if not (Decimal(0) <= c <= Decimal(1)):
                c = None
        if c is None:
            mass = {self._omega: Decimal(1)}
        else:
            m = (c * discount).quantize(_Q4, rounding=ROUND_HALF_EVEN)
            if m >= Decimal(1):
                m = Decimal(1) - _Q4
            mass = {"accept": m, self._omega: Decimal(1) - m} if m > 0 else {self._omega: Decimal(1)}
        self._observe(candidate_key, f"model:{model_string}", mass, list(src["uncertainty_type"]))

    # -- projection + export -------------------------------------------------------

    def project(self) -> dict:
        return project(self._log, self._graph, self._authority, RuleStore(), {}, as_of=self._ltime)

    def summaries(self, belief_state: dict | None = None) -> dict[str, dict]:
        state = belief_state or self.project()
        out = {}
        for key in self._candidates:
            prop = state["propositions"].get(f"candidate:{key}")
            if prop is not None:
                out[key] = summarize_belief(prop["belief"]).as_dict()
        return out

    def export(self) -> dict:
        """JSON-storable record: log export, root, as_of, canonical belief bytes, summaries."""
        state = self.project()
        exported = export_log(self._log)
        return {
            "version": self._version,
            "config_hash": self._config_hash,
            "anchor_id": self._authority.anchor_id,
            "as_of": self._ltime,
            "root": self._log.root().hex(),
            "entries": [base64.b64encode(e).decode("ascii") for e in exported["entries"]],
            "belief_state_b64": base64.b64encode(encode(state)).decode("ascii"),
            "summaries": self.summaries(state),
        }


def replay_judgement(stored: dict, pack_name: str) -> dict:
    """Rebuild the stored judgement from its log export and prove byte-identity.

    Returns ``{"root": ..., "byte_identical": bool, "summaries": ...}``.
    Raises ReplayError (from ri_core) on root mismatch or tampered entries.
    """
    authority = LocalAuthority(anchor_id=stored["anchor_id"],
                               seed=_seed(pack_name, int(stored["version"])))
    export = {"kind": "log_export",
              "entries": [base64.b64decode(e) for e in stored["entries"]]}
    # Replay re-verifies every signature: the identities must be re-issued in
    # the same order under the same seed, which the entries themselves dictate.
    seen: set[str] = set()
    from ri_core.serialization import decode
    for raw in export["entries"]:
        obj = decode(raw)
        sid = obj.get("source_id")
        if isinstance(sid, str) and sid not in seen:
            authority.issue_identity(sid)
            seen.add(sid)
    state = replay(export, authority, {}, int(stored["as_of"]), bytes.fromhex(stored["root"]))
    rebuilt = base64.b64encode(encode(state)).decode("ascii")
    summaries = {}
    for prop_name, prop in state["propositions"].items():
        summaries[prop_name.removeprefix("candidate:")] = summarize_belief(prop["belief"]).as_dict()
    return {"root": stored["root"], "byte_identical": rebuilt == stored["belief_state_b64"],
            "summaries": summaries}
