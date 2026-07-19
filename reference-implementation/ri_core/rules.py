"""Versioned verification-rule store, logged as first-class evidence.

Provides:
- RuleStore: append-only versioned store; registration returns encodable
  evidence records for logging in the EvidenceLog
- evaluate: pure function evaluating a declarative predicate AST against
  an Observation-shaped dict
- rule_entity_id: stable entity id convention for provenance integration

Verification rules are DECLARATIVE PREDICATE ASTs, not arbitrary code.
This is a design requirement: rules that are data can be logged as
evidence (I7/C7), serialized, replayed, and counterfactually substituted
(M-RI-08).  exec/eval/pickle are never used.

Operator set (12, closed):
  Value:      field, const
  Comparison: eq, ne, gt, ge, lt, le
  Membership: in
  Boolean:    and, or, not

Type discipline (amendment A1 -- strict categories):
  eq/ne use strict type-category equality: {bool}, {int}, {Decimal},
  {str}, {bytes}, {None}, {list/tuple}, {dict}.  Same category AND
  equal value required.  eq(True, 1) -> False; eq(1, Decimal("1")) -> False.
  Ordering (gt/ge/lt/le): int<->int, Decimal<->Decimal, int<->Decimal,
  str<->str; bool excluded entirely (RuleError).

This module imports ri_core.serialization (for const validation per A2)
and stdlib only.
"""

from __future__ import annotations

from decimal import Decimal

from ri_core.serialization import SerializationError
from ri_core.serialization import encode as _encode


class RuleError(Exception):
    """Error in rule operations.

    Raised for: invalid fn_spec, version discipline violations,
    missing observation fields, type mismatches during evaluation.
    Distinguished from verdict=False: RuleError means 'rule cannot
    evaluate,' not 'rule evaluated and rejected.'
    """


# ---------------------------------------------------------------------------
# Operator set (closed)
# ---------------------------------------------------------------------------

_VALUE_OPS = frozenset({"field", "const"})
_COMPARISON_OPS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
_PREDICATE_OPS = _COMPARISON_OPS | frozenset({"in", "and", "or", "not"})
_ALL_OPS = _VALUE_OPS | _PREDICATE_OPS


# ---------------------------------------------------------------------------
# Validation (registration-time, not lazy)
# ---------------------------------------------------------------------------

def _validate_predicate(node) -> None:
    """Validate a predicate AST node (recursive)."""
    if not isinstance(node, list) or len(node) < 1:
        raise RuleError(
            "fn_spec node must be a non-empty list, "
            f"got {type(node).__name__}")
    op = node[0]
    if not isinstance(op, str):
        raise RuleError(
            f"Operator must be a string, got {type(op).__name__}")

    if op in _COMPARISON_OPS or op == "in":
        if len(node) != 3:
            raise RuleError(
                f"'{op}' requires 2 operands, got {len(node) - 1}")
        _validate_value(node[1])
        _validate_value(node[2])
    elif op in ("and", "or"):
        if len(node) < 2:
            raise RuleError(
                f"'{op}' requires >= 1 operand, got {len(node) - 1}")
        for child in node[1:]:
            _validate_predicate(child)
    elif op == "not":
        if len(node) != 2:
            raise RuleError(
                f"'not' requires 1 operand, got {len(node) - 1}")
        _validate_predicate(node[1])
    elif op in _VALUE_OPS:
        raise RuleError(
            f"'{op}' is a value expression, not a predicate")
    else:
        raise RuleError(f"Unknown operator: {op!r}")


def _validate_value(node) -> None:
    """Validate a value AST node."""
    if not isinstance(node, list) or len(node) < 1:
        raise RuleError(
            "Value node must be a non-empty list, "
            f"got {type(node).__name__}")
    op = node[0]
    if not isinstance(op, str):
        raise RuleError(
            f"Operator must be a string, got {type(op).__name__}")

    if op == "field":
        if len(node) != 2:
            raise RuleError(
                f"'field' requires 1 argument, got {len(node) - 1}")
        if not isinstance(node[1], str):
            raise RuleError(
                f"'field' name must be str, "
                f"got {type(node[1]).__name__}")
    elif op == "const":
        if len(node) != 2:
            raise RuleError(
                f"'const' requires 1 argument, got {len(node) - 1}")
        _validate_const(node[1])
    elif op in _PREDICATE_OPS:
        raise RuleError(
            f"'{op}' is a predicate, not a value expression")
    else:
        raise RuleError(f"Unknown operator: {op!r}")


def _validate_const(value) -> None:
    """Validate a const value by encoding it (amendment A2).

    Uses encode() as the single source of truth for encodability.
    Rejects floats, Decimal NaN/Infinity, and anything else that
    serialization.py cannot handle.
    """
    try:
        _encode(value)
    except (TypeError, SerializationError) as e:
        raise RuleError(f"Invalid const value: {e}") from e


# ---------------------------------------------------------------------------
# Type categories (amendment A1)
# ---------------------------------------------------------------------------

def _type_category(value) -> str:
    """Strict type category for comparison dispatch (A1).

    Categories: {bool}, {int}, {Decimal}, {str}, {bytes},
    {None}, {list/tuple}, {dict}.  Bool checked before int.
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, str):
        return "str"
    if isinstance(value, bytes):
        return "bytes"
    if value is None:
        return "none"
    if isinstance(value, (list, tuple)):
        return "sequence"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _strict_eq(a, b) -> bool:
    """Strict type-category equality (A1).

    True iff same category AND equal value.  Cross-category always False.
    """
    if _type_category(a) != _type_category(b):
        return False
    return a == b


def _check_ordering(left, right, op: str) -> None:
    """Validate types for ordering comparison (A1).

    Permits: int<->int, Decimal<->Decimal, int<->Decimal, str<->str.
    Bool excluded entirely (RuleError).
    """
    cat_l = _type_category(left)
    cat_r = _type_category(right)

    if cat_l == "bool" or cat_r == "bool":
        raise RuleError(
            f"Bool excluded from ordering comparison '{op}'")

    if cat_l == cat_r:
        return

    if {cat_l, cat_r} == {"int", "decimal"}:
        return

    raise RuleError(
        f"Type mismatch in '{op}': {cat_l} vs {cat_r}")


# ---------------------------------------------------------------------------
# Evaluation (pure)
# ---------------------------------------------------------------------------

def _eval_value(node, obs: dict):
    """Evaluate a value expression against an observation."""
    op = node[0]
    if op == "field":
        name = node[1]
        if name not in obs:
            raise RuleError(f"Missing field: {name!r}")
        return obs[name]
    if op == "const":
        return node[1]
    raise RuleError(f"Unknown value operator: {op!r}")


def _eval_predicate(node, obs: dict) -> bool:
    """Evaluate a predicate expression against an observation."""
    op = node[0]

    if op == "eq":
        return _strict_eq(
            _eval_value(node[1], obs), _eval_value(node[2], obs))

    if op == "ne":
        return not _strict_eq(
            _eval_value(node[1], obs), _eval_value(node[2], obs))

    if op in ("gt", "ge", "lt", "le"):
        left = _eval_value(node[1], obs)
        right = _eval_value(node[2], obs)
        _check_ordering(left, right, op)
        try:
            if op == "gt":
                return left > right
            if op == "ge":
                return left >= right
            if op == "lt":
                return left < right
            return left <= right
        except TypeError as e:
            raise RuleError(
                f"Comparison error in '{op}': {e}") from e

    if op == "in":
        val = _eval_value(node[1], obs)
        container = _eval_value(node[2], obs)
        if not isinstance(container, (list, tuple)):
            raise RuleError(
                f"'in' requires a list, got "
                f"{type(container).__name__}")
        return any(_strict_eq(val, item) for item in container)

    if op == "and":
        verdicts = [_eval_predicate(c, obs) for c in node[1:]]
        return all(verdicts)

    if op == "or":
        verdicts = [_eval_predicate(c, obs) for c in node[1:]]
        return any(verdicts)

    if op == "not":
        return not _eval_predicate(node[1], obs)

    raise RuleError(f"Unknown predicate operator: {op!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(rule_spec: dict, observation: dict) -> dict:
    """Evaluate a verification rule against an observation.

    Pure function.  No store access.  Returns an encodable
    VerificationResult dict.

    Args:
        rule_spec: Rule version record (as from register() / get()).
        observation: Observation-shaped dict with at least 'id' and 'ltime'.

    Returns:
        dict with kind, rule_id, version, verdict, observation_id, ltime.

    Raises:
        RuleError: if rule cannot evaluate (missing field, type mismatch,
            malformed observation).
    """
    if "id" not in observation:
        raise RuleError(
            "Observation missing required field: 'id'")
    if "ltime" not in observation:
        raise RuleError(
            "Observation missing required field: 'ltime'")

    verdict = _eval_predicate(rule_spec["fn_spec"], observation)
    return {
        "kind": "verification_result",
        "rule_id": rule_spec["rule_id"],
        "version": rule_spec["version"],
        "verdict": verdict,
        "observation_id": observation["id"],
        "ltime": observation["ltime"],
    }


def rule_entity_id(rule_id: str, version: int) -> str:
    """Stable entity id for provenance integration.

    Returns "rule:{rule_id}:v{version}", matching provenance.py's
    Entity(kind=RULE_VERSION, rule_id=..., rule_version=...).
    """
    return f"rule:{rule_id}:v{version}"


# ---------------------------------------------------------------------------
# Rule Store
# ---------------------------------------------------------------------------

class RuleStore:
    """Append-only versioned verification-rule store.

    Registration validates fn_spec (closed-world, at store time) and
    returns an encodable evidence record suitable for appending to the
    EvidenceLog.  Integration with log.py and provenance.py happens at
    the caller's level (M-RI-07), not here.

    Version discipline: dense ints from 1 per rule_id; no gaps, no
    overwrites, no implicit 'latest.'
    """

    def __init__(self) -> None:
        self._rules: dict[str, dict[int, dict]] = {}

    def register(
        self,
        rule_id: str,
        version: int,
        fn_spec,
        ltime: int,
    ) -> dict:
        """Register a rule version.  Returns encodable evidence record.

        Validates fn_spec at registration time (closed-world).
        """
        if isinstance(version, bool) or not isinstance(version, int):
            raise RuleError(
                f"version must be int, got {type(version).__name__}")
        if version < 1:
            raise RuleError(f"version must be >= 1, got {version}")
        if isinstance(ltime, bool) or not isinstance(ltime, int):
            raise RuleError(
                f"ltime must be int, got {type(ltime).__name__}")

        # Version discipline
        if rule_id in self._rules:
            if version in self._rules[rule_id]:
                raise RuleError(
                    f"Already registered: {rule_id!r} v{version}")
            max_v = max(self._rules[rule_id])
            if version != max_v + 1:
                raise RuleError(
                    f"Version gap: {rule_id!r} v{version} "
                    f"(latest is v{max_v})")
        else:
            if version != 1:
                raise RuleError(
                    f"First version must be 1: {rule_id!r} v{version}")

        # Validate fn_spec (closed-world, at registration)
        _validate_predicate(fn_spec)

        record = {
            "kind": "rule_version",
            "rule_id": rule_id,
            "version": version,
            "fn_spec": fn_spec,
            "ltime": ltime,
        }

        if rule_id not in self._rules:
            self._rules[rule_id] = {}
        self._rules[rule_id][version] = record
        return record

    def get(self, rule_id: str, version: int) -> dict:
        """Get a registered rule version record.

        Raises RuleError if rule_id or version not found.
        """
        if rule_id not in self._rules:
            raise RuleError(f"Unknown rule: {rule_id!r}")
        if version not in self._rules[rule_id]:
            raise RuleError(
                f"Version not found: {rule_id!r} v{version}")
        return self._rules[rule_id][version]

    def latest_version(self, rule_id: str) -> int:
        """Latest registered version number.

        Raises RuleError if rule_id unknown.  Callers MUST use this
        or name a version explicitly -- no implicit 'latest'.
        """
        if rule_id not in self._rules:
            raise RuleError(f"Unknown rule: {rule_id!r}")
        return max(self._rules[rule_id])
