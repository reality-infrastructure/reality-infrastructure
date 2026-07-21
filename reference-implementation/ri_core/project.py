"""Projection engine: deterministic fold Log → BeliefState with justification.

Provides:
- submit(): sole mutator — signed observation → EvidenceLog + ProvenanceGraph
- project(): pure deterministic fold — log prefix → BeliefState with
  per-proposition fused beliefs, how-provenance polynomials, and
  machine-checkable justification records

This is the integration layer: imports log, identity, provenance, rules,
reconcile, serialization.  All other ri_core modules are leaves.
"""

from __future__ import annotations

from decimal import Decimal

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.provenance import (
    Activity,
    Agent,
    Entity,
    EntityKind,
    HowProvenance,
    ProvenanceError,
    ProvenanceGraph,
)
from ri_core.reconcile import BeliefWeights, ReconciliationError, cautious_fuse
from ri_core.rules import RuleError, RuleStore
from ri_core.rules import evaluate as _rule_evaluate
from ri_core.serialization import decode as _ser_decode
from ri_core.serialization import encode as _ser_encode


class ProjectionError(Exception):
    """Error in projection operations.

    Raised for: invalid observations, signature failures, frame mismatches,
    rule evaluation errors, duplicate observation ids.
    """


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------

_REQUIRED_OBS_FIELDS = frozenset(
    {"kind", "id", "source_id", "proposition", "payload", "ltime", "sig"}
)


def _parse_payload(payload: dict) -> tuple[frozenset[str], dict[frozenset[str], Decimal]]:
    """Convert payload mass dict (comma-key strings) to frozenset-key dict."""
    frame = frozenset(payload["frame"])
    mass_dict: dict[frozenset[str], Decimal] = {}
    for key, value in payload["mass"].items():
        subset = frozenset() if key == "" else frozenset(key.split(","))
        mass_dict[subset] = value
    return frame, mass_dict


def _unsigned_bytes(obs: dict) -> bytes:
    """Canonical bytes of the unsigned observation (everything except sig)."""
    unsigned = {k: v for k, v in obs.items() if k != "sig"}
    return _ser_encode(unsigned)


# ---------------------------------------------------------------------------
# submit — sole mutator
# ---------------------------------------------------------------------------

def submit(
    observation: dict,
    log: EvidenceLog,
    graph: ProvenanceGraph,
    authority: LocalAuthority,
) -> tuple[int, str]:
    """Submit a signed observation to the evidence log.

    Validates everything before any write (atomicity).
    Returns (log_index, entity_id).
    """
    obs = observation

    # -- Phase 1: validate (reads only, no mutations) --

    missing = _REQUIRED_OBS_FIELDS - set(obs.keys())
    if missing:
        raise ProjectionError(
            f"Missing observation fields: {sorted(missing)}")
    if obs["kind"] != "observation":
        raise ProjectionError(
            f"Expected kind='observation', got {obs['kind']!r}")

    if isinstance(obs["ltime"], bool) or not isinstance(obs["ltime"], int):
        raise ProjectionError(
            f"ltime must be int, got {type(obs['ltime']).__name__}")
    if obs["ltime"] < 0:
        raise ProjectionError(f"ltime must be >= 0, got {obs['ltime']}")

    ub = _unsigned_bytes(obs)
    identity = Identity(
        identity_id=obs["source_id"],
        anchor_id=authority.anchor_id,
        name=obs["source_id"],
    )
    if not authority.verify(identity, ub, obs["sig"]):
        raise ProjectionError(
            f"Signature verification failed for observation {obs['id']!r}")

    try:
        frame, mass_dict = _parse_payload(obs["payload"])
        BeliefWeights.from_mass(frame, mass_dict)
    except (ReconciliationError, KeyError, TypeError) as e:
        raise ProjectionError(f"Invalid payload: {e}") from e

    entity_id = f"obs:{obs['id']}"
    try:
        graph.get_entity(entity_id)
        raise ProjectionError(f"Duplicate observation id: {obs['id']!r}")
    except ProvenanceError:
        pass  # not found — good

    # -- Phase 2: writes (cannot fail after validation) --

    log_index = log.append(obs)

    graph.add_entity(Entity(
        entity_id=entity_id,
        kind=EntityKind.EVIDENCE_LEAF,
        log_index=log_index,
    ))

    agent_id = obs["source_id"]
    try:
        graph.add_agent(Agent(agent_id=agent_id))
    except ProvenanceError:
        pass  # already exists

    graph.record_attribution(entity_id, agent_id)

    return (log_index, entity_id)


# ---------------------------------------------------------------------------
# Shared-provenance partitioning
# ---------------------------------------------------------------------------

def _make_identity(source_id: str, anchor_id: str) -> Identity:
    return Identity(identity_id=source_id, anchor_id=anchor_id, name=source_id)


def _partition_classes(
    items: list[tuple[int, dict]],
    authority: LocalAuthority,
) -> list[tuple[str, list[tuple[int, dict]]]]:
    """Partition (log_index, obs) items into shared-provenance classes.

    Returns sorted list of (class_repr, items) where class_repr is the
    lex-smallest source_id in the class.
    """
    anchor_id = authority.anchor_id
    buckets: list[list[tuple[int, dict]]] = []

    for item in items:
        source_id = item[1]["source_id"]
        placed = False
        for bucket in buckets:
            rep_source = bucket[0][1]["source_id"]
            id_a = _make_identity(rep_source, anchor_id)
            id_b = _make_identity(source_id, anchor_id)
            if authority.shared_provenance(id_a, id_b):
                bucket.append(item)
                placed = True
                break
        if not placed:
            buckets.append([item])

    result: list[tuple[str, list[tuple[int, dict]]]] = []
    for bucket in buckets:
        sources = sorted({m[1]["source_id"] for m in bucket})
        class_repr = sources[0]
        sorted_bucket = sorted(bucket, key=lambda m: f"obs:{m[1]['id']}")
        result.append((class_repr, sorted_bucket))

    result.sort(key=lambda x: x[0])
    return result


# ---------------------------------------------------------------------------
# Idempotent graph insertion helpers
# ---------------------------------------------------------------------------

def _try_add_entity(graph: ProvenanceGraph, entity: Entity) -> bool:
    """Add entity if absent.  Returns True if newly added."""
    try:
        graph.get_entity(entity.entity_id)
        return False
    except ProvenanceError:
        graph.add_entity(entity)
        return True


def _try_add_activity(graph: ProvenanceGraph, activity: Activity) -> bool:
    """Add activity if absent.  Returns True if newly added."""
    try:
        graph.get_activity(activity.activity_id)
        return False
    except ProvenanceError:
        graph.add_activity(activity)
        return True


# ---------------------------------------------------------------------------
# project — deterministic fold
# ---------------------------------------------------------------------------

def project(
    log: EvidenceLog,
    graph: ProvenanceGraph,
    authority: LocalAuthority,
    rule_store: RuleStore,
    rule_bindings: dict[str, tuple[str, int]],
    as_of: int,
) -> dict:
    """Deterministic fold: log prefix → BeliefState.

    Processes all observations in the log with ltime <= as_of.
    Groups by proposition, applies rule verification, partitions by
    shared provenance, fuses with cautious_fuse, builds justification.

    Mutates graph idempotently (skip-if-exists for derived entities).
    Returns encodable BeliefState dict.
    """
    if isinstance(as_of, bool) or not isinstance(as_of, int):
        raise ProjectionError(
            f"as_of must be int, got {type(as_of).__name__}")

    log_size = len(log)

    # 1. Collect in-scope observations grouped by proposition
    prop_items: dict[str, list[tuple[int, dict]]] = {}

    for idx in range(log_size):
        entry = _ser_decode(log.entry(idx))
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") != "observation":
            continue
        ltime = entry.get("ltime")
        if isinstance(ltime, bool) or not isinstance(ltime, int):
            continue
        if ltime > as_of:
            continue
        prop = entry["proposition"]
        if prop not in prop_items:
            prop_items[prop] = []
        prop_items[prop].append((idx, entry))

    # 2. Process each proposition (sorted for determinism)
    propositions: dict[str, dict] = {}

    for prop in sorted(prop_items.keys()):
        items = prop_items[prop]
        items.sort(key=lambda it: it[1]["id"])

        rule_info = rule_bindings.get(prop)

        # 2a. Rule verification
        passing: list[tuple[int, dict]] = []
        excluded_list: list[dict] = []
        verdict_list: list[dict] = []

        for log_idx, obs in items:
            if rule_info is not None:
                r_id, r_ver = rule_info
                r_spec = rule_store.get(r_id, r_ver)
                eval_obs = {k: v for k, v in obs.items() if k != "sig"}
                try:
                    vr = _rule_evaluate(r_spec, eval_obs)
                except RuleError as e:
                    raise ProjectionError(
                        f"Rule evaluation error for observation "
                        f"{obs['id']!r}: {e}") from e

                verdict_list.append({
                    "observation_id": obs["id"],
                    "verdict": vr["verdict"],
                })
                if vr["verdict"]:
                    passing.append((log_idx, obs))
                else:
                    excluded_list.append({
                        "entity_id": f"obs:{obs['id']}",
                        "log_index": log_idx,
                        "source_id": obs["source_id"],
                        "reason": "rule_verdict_false",
                        "rule_id": r_id,
                        "rule_version": r_ver,
                    })
            else:
                passing.append((log_idx, obs))

        # 2b. All-excluded (A4): proposition present, belief=None
        if not passing:
            just: dict = {
                "classes": [],
                "excluded": sorted(
                    excluded_list, key=lambda e: e["entity_id"]),
                "how_provenance": HowProvenance.zero().to_canonical(),
            }
            if rule_info is not None:
                just["rule_applied"] = {
                    "rule_id": rule_info[0],
                    "version": rule_info[1],
                    "verdicts": sorted(
                        verdict_list, key=lambda v: v["observation_id"]),
                }
            propositions[prop] = {"belief": None, "justification": just}
            continue

        # 2c. Build beliefs, validate frame consistency
        beliefs: list[BeliefWeights] = []
        frame: frozenset[str] | None = None

        for log_idx, obs in passing:
            obs_frame, obs_mass = _parse_payload(obs["payload"])
            if frame is None:
                frame = obs_frame
            elif obs_frame != frame:
                raise ProjectionError(
                    f"Frame mismatch for proposition {prop!r}: "
                    f"expected {sorted(frame)}, got {sorted(obs_frame)}")
            beliefs.append(BeliefWeights.from_mass(obs_frame, obs_mass))

        # 2d. Partition by provenance class
        classes = _partition_classes(passing, authority)

        # 2e. Fuse all beliefs
        fused = cautious_fuse(*beliefs)

        # 2f. How-provenance polynomial (directly computed)
        how_poly = HowProvenance.zero()
        for class_repr, class_items in classes:
            cp = HowProvenance.one()
            for _, obs in class_items:
                cp = cp.multiply(HowProvenance.variable(obs["source_id"]))
            how_poly = how_poly.add(cp)

        # 2g. Build justification
        classes_just: list[dict] = []
        for class_repr, class_items in classes:
            classes_just.append({
                "class_repr": class_repr,
                "observations": [
                    {
                        "entity_id": f"obs:{obs['id']}",
                        "log_index": li,
                        "source_id": obs["source_id"],
                    }
                    for li, obs in class_items
                ],
            })

        just = {
            "classes": classes_just,
            "excluded": sorted(
                excluded_list, key=lambda e: e["entity_id"]),
            "how_provenance": how_poly.to_canonical(),
        }
        if rule_info is not None:
            just["rule_applied"] = {
                "rule_id": rule_info[0],
                "version": rule_info[1],
                "verdicts": sorted(
                    verdict_list, key=lambda v: v["observation_id"]),
            }

        propositions[prop] = {
            "belief": fused.to_dict(),
            "justification": just,
        }

        # 2h. Provenance insertions (idempotent, ids include log_size)
        derived_id = f"belief:{prop}:as_of:{as_of}:size:{log_size}"

        rule_entity_id = None
        if rule_info is not None:
            rule_entity_id = f"rule:{rule_info[0]}:v{rule_info[1]}"
            _try_add_entity(graph, Entity(
                entity_id=rule_entity_id,
                kind=EntityKind.RULE_VERSION,
                rule_id=rule_info[0],
                rule_version=rule_info[1],
            ))

        for class_repr, class_items in classes:
            act_id = (f"project:{prop}:class:{class_repr}"
                      f":as_of:{as_of}:size:{log_size}")
            if _try_add_activity(graph, Activity(
                activity_id=act_id,
                operation="project",
                rule_version_id=rule_entity_id,
            )):
                for li, obs in class_items:
                    graph.record_used(act_id, f"obs:{obs['id']}")

        if _try_add_entity(graph, Entity(
            entity_id=derived_id, kind=EntityKind.DERIVED,
        )):
            for class_repr, class_items in classes:
                act_id = (f"project:{prop}:class:{class_repr}"
                          f":as_of:{as_of}:size:{log_size}")
                ev_ids = [f"obs:{o['id']}" for _, o in class_items]
                graph.record_generation(
                    derived_id, act_id, derived_from=ev_ids)

    return {
        "kind": "belief_state",
        "as_of": as_of,
        "propositions": propositions,
    }
