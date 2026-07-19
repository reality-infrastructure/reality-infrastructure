"""PROV-DM-compatible provenance DAG with N[X] how-provenance annotations.

Provides:
- HowProvenance: N[X] polynomial (how-provenance semiring) over identity
  variables, supporting add (alternative derivations), multiply (joint use),
  and canonical serialization
- ProvenanceGraph: append-only PROV-DM graph with typed nodes (Entity,
  Activity, Agent) and four edge types (used, wasGeneratedBy, wasDerivedFrom,
  wasAttributedTo)

How-provenance semantics (GKT 2007): variables are source identity_id strings;
monomials represent joint derivation paths; coefficients count alternative
derivations; "2s^2 + rs" = three derivation paths (two using source s twice,
one using sources r and s jointly).

Why how-provenance, not why-provenance: why-provenance (Boolean/set semiring)
is idempotent (s | s = s), so it collapses multiplicity -- two independent
uses of the same source become indistinguishable from one.  How-provenance
(N[X]) preserves derivation count, which reconcile (M-RI-06) needs for
Sybil-calibration (I2).

This module imports only stdlib.  Polynomials are serialization-compatible
via to_canonical() / from_canonical() (tested against ri_core.serialization).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProvenanceError(Exception):
    """Error in provenance operations.

    Raised for: referencing nonexistent nodes, cycle creation,
    attribution cardinality violations, orphan derived entities.
    """


# ---------------------------------------------------------------------------
# N[X] How-Provenance Polynomial
# ---------------------------------------------------------------------------

# A monomial is a tuple of (variable, exponent) pairs, sorted by variable.
# Example: (("r", 1), ("s", 2)) represents r * s^2.
# The empty monomial () represents the constant 1.
Monomial = tuple[tuple[str, int], ...]


def _merge_monomials(a: Monomial, b: Monomial) -> Monomial:
    """Merge two monomials by summing exponents of shared variables."""
    combined: dict[str, int] = {}
    for var, exp in a:
        combined[var] = combined.get(var, 0) + exp
    for var, exp in b:
        combined[var] = combined.get(var, 0) + exp
    return tuple(sorted(combined.items()))


class HowProvenance:
    """N[X] polynomial over source-identity variables.

    Immutable value type.  All operations return new instances.

    Internal representation: dict mapping Monomial -> int coefficient.
    Invariants maintained automatically:
    - All coefficients >= 1 (zero-coefficient terms dropped)
    - All exponents >= 1
    - Monomial variable pairs sorted by variable name
    """

    __slots__ = ('_terms',)

    def __init__(self, terms: dict[Monomial, int] | None = None) -> None:
        if terms is None:
            self._terms: dict[Monomial, int] = {}
        else:
            cleaned: dict[Monomial, int] = {}
            for mono, coeff in terms.items():
                if coeff < 0:
                    raise ValueError(f"Negative coefficient: {coeff}")
                if coeff > 0:
                    cleaned[mono] = coeff
            self._terms = cleaned

    # -- Constructors --------------------------------------------------

    @staticmethod
    def zero() -> HowProvenance:
        """Additive identity (no derivations)."""
        return HowProvenance()

    @staticmethod
    def one() -> HowProvenance:
        """Multiplicative identity (constant 1)."""
        return HowProvenance({(): 1})

    @staticmethod
    def variable(var: str) -> HowProvenance:
        """Single variable with coefficient 1 and exponent 1."""
        return HowProvenance({((var, 1),): 1})

    # -- Properties ----------------------------------------------------

    @property
    def is_zero(self) -> bool:
        """True iff this polynomial has no terms."""
        return len(self._terms) == 0

    @property
    def terms(self) -> dict[Monomial, int]:
        """Read-only copy of the terms dict."""
        return dict(self._terms)

    # -- Arithmetic ----------------------------------------------------

    def add(self, other: HowProvenance) -> HowProvenance:
        """Polynomial addition (alternative derivations)."""
        result: dict[Monomial, int] = dict(self._terms)
        for mono, coeff in other._terms.items():
            result[mono] = result.get(mono, 0) + coeff
        return HowProvenance(result)

    def multiply(self, other: HowProvenance) -> HowProvenance:
        """Polynomial multiplication (joint use of sources)."""
        if self.is_zero or other.is_zero:
            return HowProvenance.zero()
        result: dict[Monomial, int] = {}
        for mono_a, coeff_a in self._terms.items():
            for mono_b, coeff_b in other._terms.items():
                merged = _merge_monomials(mono_a, mono_b)
                result[merged] = result.get(merged, 0) + coeff_a * coeff_b
        return HowProvenance(result)

    # -- Serialization -------------------------------------------------

    def to_canonical(self) -> list:
        """Canonical form for encode(): sorted list of [monomial, coeff].

        Each monomial is a sorted list of [variable, exponent] pairs.
        The outer list is sorted by monomial (lexicographic on pairs).
        Coefficients and exponents are ints >= 1.
        """
        items = []
        for mono in sorted(self._terms.keys()):
            coeff = self._terms[mono]
            mono_list = [[var, exp] for var, exp in mono]
            items.append([mono_list, coeff])
        return items

    @staticmethod
    def from_canonical(data: list) -> HowProvenance:
        """Reconstruct a polynomial from its canonical form."""
        terms: dict[Monomial, int] = {}
        for item in data:
            mono_list, coeff = item[0], item[1]
            mono = tuple((pair[0], pair[1]) for pair in mono_list)
            terms[mono] = coeff
        return HowProvenance(terms)

    # -- Comparison ----------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HowProvenance):
            return NotImplemented
        return self._terms == other._terms

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._terms.items())))

    def __repr__(self) -> str:
        if not self._terms:
            return "HowProvenance(0)"
        parts = []
        for mono in sorted(self._terms.keys()):
            coeff = self._terms[mono]
            if not mono:
                parts.append(str(coeff))
            else:
                var_parts = []
                for var, exp in mono:
                    var_parts.append(f"{var}^{exp}" if exp != 1 else var)
                term = "*".join(var_parts)
                parts.append(f"{coeff}*{term}" if coeff != 1 else term)
        return f"HowProvenance({' + '.join(parts)})"


# ---------------------------------------------------------------------------
# PROV-DM Node and Edge Types
# ---------------------------------------------------------------------------

class EntityKind(Enum):
    """Kind of provenance entity."""
    EVIDENCE_LEAF = "evidence_leaf"
    DERIVED = "derived"
    RULE_VERSION = "rule_version"


@dataclass(frozen=True)
class Entity:
    """A provenance entity (PROV-DM Entity)."""
    entity_id: str
    kind: EntityKind
    log_index: int | None = None      # evidence_leaf only
    rule_id: str | None = None        # rule_version only
    rule_version: int | None = None   # rule_version only


@dataclass(frozen=True)
class Activity:
    """A provenance activity (PROV-DM Activity)."""
    activity_id: str
    operation: str
    rule_version_id: str | None = None  # entity_id of rule_version used


@dataclass(frozen=True)
class Agent:
    """A provenance agent (PROV-DM Agent), identified by identity_id."""
    agent_id: str  # identity_id string


# ---------------------------------------------------------------------------
# Provenance Graph
# ---------------------------------------------------------------------------

class ProvenanceGraph:
    """Append-only PROV-DM-compatible provenance graph.

    Enforces at insertion:
    - No edges referencing nonexistent nodes (typed error)
    - No wasDerivedFrom cycles (checked at every edge insertion)
    - Attribution cardinality: evidence_leaf gets at most one
      wasAttributedTo (amendment A2)
    - Atomicity: record_generation validates all checks before any
      mutation (amendment A1)

    Enforces at query:
    - evidence_leaf requires attribution for how_provenance (A2)
    - derived entity requires >= 1 generating activity (A3)
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._activities: dict[str, Activity] = {}
        self._agents: dict[str, Agent] = {}
        # used: activity_id -> [entity_id, ...] (duplicates = multiplicity)
        self._used: dict[str, list[str]] = {}
        # wasGeneratedBy: entity_id -> [activity_id, ...]
        self._generated_by: dict[str, list[str]] = {}
        # wasDerivedFrom: entity_id -> [entity_id, ...]
        self._derived_from: dict[str, list[str]] = {}
        # wasAttributedTo: entity_id -> agent_id
        self._attributed_to: dict[str, str] = {}

    # -- Node registration ---------------------------------------------

    def add_entity(self, entity: Entity) -> None:
        """Register an entity.  Raises ProvenanceError on duplicate id."""
        if entity.entity_id in self._entities:
            raise ProvenanceError(
                f"Entity already exists: {entity.entity_id!r}")
        self._entities[entity.entity_id] = entity

    def add_activity(self, activity: Activity) -> None:
        """Register an activity.  Raises ProvenanceError on duplicate id."""
        if activity.activity_id in self._activities:
            raise ProvenanceError(
                f"Activity already exists: {activity.activity_id!r}")
        if activity.rule_version_id is not None:
            if activity.rule_version_id not in self._entities:
                raise ProvenanceError(
                    f"Rule version entity not found: "
                    f"{activity.rule_version_id!r}")
            rv = self._entities[activity.rule_version_id]
            if rv.kind != EntityKind.RULE_VERSION:
                raise ProvenanceError(
                    f"Referenced entity {activity.rule_version_id!r} is "
                    f"{rv.kind.value}, not rule_version")
        self._activities[activity.activity_id] = activity

    def add_agent(self, agent: Agent) -> None:
        """Register an agent.  Raises ProvenanceError on duplicate id."""
        if agent.agent_id in self._agents:
            raise ProvenanceError(
                f"Agent already exists: {agent.agent_id!r}")
        self._agents[agent.agent_id] = agent

    # -- Edge insertion ------------------------------------------------

    def record_used(self, activity_id: str, entity_id: str) -> None:
        """Record that an activity used an entity as input.

        Duplicates are intentional: using the same entity twice in one
        activity produces polynomial multiplicity (s used twice -> s^2).
        """
        if activity_id not in self._activities:
            raise ProvenanceError(
                f"Activity not found: {activity_id!r}")
        if entity_id not in self._entities:
            raise ProvenanceError(
                f"Entity not found: {entity_id!r}")
        if activity_id not in self._used:
            self._used[activity_id] = []
        self._used[activity_id].append(entity_id)

    def record_generation(
        self,
        entity_id: str,
        activity_id: str,
        derived_from: list[str] | None = None,
    ) -> None:
        """Record wasGeneratedBy + optional wasDerivedFrom edges.

        Amendment A1 (Atomicity): ALL checks run before ANY mutation.
        A rejected call leaves the graph byte-identical to before.
        """
        # -- Phase 1: validate -----------------------------------------
        if entity_id not in self._entities:
            raise ProvenanceError(
                f"Entity not found: {entity_id!r}")
        if activity_id not in self._activities:
            raise ProvenanceError(
                f"Activity not found: {activity_id!r}")
        if derived_from is not None:
            for src_id in derived_from:
                if src_id not in self._entities:
                    raise ProvenanceError(
                        f"Entity not found: {src_id!r}")
            for src_id in derived_from:
                if src_id == entity_id:
                    raise ProvenanceError(
                        f"Self-derivation: {entity_id!r} cannot derive "
                        f"from itself")
                if self._would_create_cycle(entity_id, src_id):
                    raise ProvenanceError(
                        f"Cycle detected: {entity_id!r} -> {src_id!r} "
                        f"would create a wasDerivedFrom cycle")

        # -- Phase 2: commit -------------------------------------------
        if entity_id not in self._generated_by:
            self._generated_by[entity_id] = []
        if activity_id not in self._generated_by[entity_id]:
            self._generated_by[entity_id].append(activity_id)
        if derived_from is not None:
            if entity_id not in self._derived_from:
                self._derived_from[entity_id] = []
            for src_id in derived_from:
                if src_id not in self._derived_from[entity_id]:
                    self._derived_from[entity_id].append(src_id)

    def record_attribution(self, entity_id: str, agent_id: str) -> None:
        """Record wasAttributedTo: entity -> agent.

        Amendment A2: a second wasAttributedTo on an evidence_leaf raises
        ProvenanceError.
        """
        if entity_id not in self._entities:
            raise ProvenanceError(
                f"Entity not found: {entity_id!r}")
        if agent_id not in self._agents:
            raise ProvenanceError(
                f"Agent not found: {agent_id!r}")
        entity = self._entities[entity_id]
        if entity.kind == EntityKind.EVIDENCE_LEAF:
            if entity_id in self._attributed_to:
                raise ProvenanceError(
                    f"Evidence leaf {entity_id!r} already attributed to "
                    f"{self._attributed_to[entity_id]!r}; second "
                    f"attribution forbidden (amendment A2)")
        self._attributed_to[entity_id] = agent_id

    # -- Cycle detection -----------------------------------------------

    def _would_create_cycle(self, from_id: str, to_id: str) -> bool:
        """True iff adding wasDerivedFrom(from_id -> to_id) creates a cycle.

        Checks whether to_id can reach from_id via existing wasDerivedFrom.
        Iterative DFS to avoid stack overflow.
        """
        visited: set[str] = set()
        stack = [to_id]
        while stack:
            current = stack.pop()
            if current == from_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            for successor in self._derived_from.get(current, []):
                stack.append(successor)
        return False

    # -- How-provenance computation ------------------------------------

    def how_provenance(self, entity_id: str) -> HowProvenance:
        """Compute N[X] how-provenance polynomial for an entity.

        Traversal semantics (GKT 2007):
        - evidence_leaf -> variable(agent_id) from wasAttributedTo
        - rule_version -> one() (multiplicative identity)
        - derived -> sum over generating activities of product of used inputs

        Raises ProvenanceError if:
        - entity not found
        - evidence_leaf has no wasAttributedTo (amendment A2)
        - derived entity has zero generating activities (amendment A3)
        """
        if entity_id not in self._entities:
            raise ProvenanceError(
                f"Entity not found: {entity_id!r}")
        memo: dict[str, HowProvenance] = {}
        return self._how_dfs(entity_id, memo)

    def _how_dfs(
        self, entity_id: str, memo: dict[str, HowProvenance],
    ) -> HowProvenance:
        """Memoized DFS for how-provenance.  Sorted iteration everywhere."""
        if entity_id in memo:
            return memo[entity_id]
        entity = self._entities[entity_id]

        if entity.kind == EntityKind.EVIDENCE_LEAF:
            if entity_id not in self._attributed_to:
                raise ProvenanceError(
                    f"Evidence leaf {entity_id!r} has no attribution; "
                    f"how_provenance requires wasAttributedTo (A2)")
            result = HowProvenance.variable(self._attributed_to[entity_id])

        elif entity.kind == EntityKind.RULE_VERSION:
            result = HowProvenance.one()

        elif entity.kind == EntityKind.DERIVED:
            activities = self._generated_by.get(entity_id, [])
            if not activities:
                raise ProvenanceError(
                    f"Derived entity {entity_id!r} has no generating "
                    f"activities; how_provenance undefined (A3)")
            result = HowProvenance.zero()
            for act_id in sorted(activities):
                used_ids = self._used.get(act_id, [])
                prod = HowProvenance.one()
                for uid in sorted(used_ids):
                    prod = prod.multiply(self._how_dfs(uid, memo))
                result = result.add(prod)
        else:
            raise ProvenanceError(
                f"Unknown entity kind: {entity.kind}")

        memo[entity_id] = result
        return result

    # -- Query helpers -------------------------------------------------

    def get_entity(self, entity_id: str) -> Entity:
        """Look up an entity by id.  Raises ProvenanceError if missing."""
        if entity_id not in self._entities:
            raise ProvenanceError(
                f"Entity not found: {entity_id!r}")
        return self._entities[entity_id]

    def get_activity(self, activity_id: str) -> Activity:
        """Look up an activity by id.  Raises ProvenanceError if missing."""
        if activity_id not in self._activities:
            raise ProvenanceError(
                f"Activity not found: {activity_id!r}")
        return self._activities[activity_id]

    def get_agent(self, agent_id: str) -> Agent:
        """Look up an agent by id.  Raises ProvenanceError if missing."""
        if agent_id not in self._agents:
            raise ProvenanceError(
                f"Agent not found: {agent_id!r}")
        return self._agents[agent_id]
