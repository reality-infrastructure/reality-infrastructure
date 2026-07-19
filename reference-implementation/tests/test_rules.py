"""Tests for ri_core.rules -- versioned verification-rule store."""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.rules import (
    RuleError,
    RuleStore,
    evaluate,
    rule_entity_id,
)
from ri_core.serialization import encode, decode

GOLDEN_DIR = Path(__file__).parent / "golden" / "rules"

# -- Fixture specs ---------------------------------------------------------

SPEC_V1 = ["and",
    ["ge", ["field", "ltime"], ["const", 1]],
    ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
]

SPEC_V2 = ["ge", ["field", "ltime"], ["const", 1]]

SPEC_TEMP = ["gt", ["field", "temperature"], ["const", 100]]

# -- Fixture observations --------------------------------------------------

OBS_PASS = {
    "id": "obs-1", "source_id": "alice", "ltime": 5,
    "proposition": "sky-blue",
}
OBS_FAIL_SOURCE = {
    "id": "obs-2", "source_id": "charlie", "ltime": 5,
    "proposition": "sky-blue",
}
OBS_FAIL_LTIME = {
    "id": "obs-3", "source_id": "alice", "ltime": 0,
    "proposition": "sky-blue",
}
OBS_MISSING_FIELD = {
    "id": "obs-4", "ltime": 5,
    "proposition": "sky-blue",
}
OBS_TYPE_MISMATCH = {
    "id": "obs-5", "temperature": "hot", "ltime": 1,
}
OBS_BOOL_ORDERING = {
    "id": "obs-6", "temperature": True, "ltime": 1,
}


def _make_rule(spec, rule_id="r", version=1):
    """Helper: build a rule record without a RuleStore."""
    return {
        "kind": "rule_version",
        "rule_id": rule_id,
        "version": version,
        "fn_spec": spec,
        "ltime": 0,
    }


# -- Validation (registration-time) ----------------------------------------

class TestValidation:
    def test_unknown_operator_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="Unknown operator"):
            store.register("r", 1, ["multiply", ["const", 1], ["const", 2]], 0)

    def test_value_op_as_predicate_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="value expression.*not a predicate"):
            store.register("r", 1, ["field", "x"], 0)

    def test_predicate_op_as_value_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="predicate.*not a value"):
            store.register("r", 1,
                ["eq", ["and", ["eq", ["const", 1], ["const", 1]]],
                       ["const", 1]], 0)

    def test_arity_field(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="requires 1 argument"):
            store.register("r", 1, ["eq", ["field"], ["const", 1]], 0)

    def test_arity_comparison(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="requires 2 operands"):
            store.register("r", 1, ["eq", ["const", 1]], 0)

    def test_arity_and(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="requires >= 1 operand"):
            store.register("r", 1, ["and"], 0)

    def test_arity_not(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="requires 1 operand"):
            store.register("r", 1, ["not"], 0)

    def test_field_name_must_be_str(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="must be str"):
            store.register("r", 1,
                ["eq", ["field", 42], ["const", 1]], 0)

    def test_node_must_be_list(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="non-empty list"):
            store.register("r", 1, "not-a-list", 0)

    def test_float_const_raises(self):
        """A2: float const rejected at registration via encode()."""
        store = RuleStore()
        with pytest.raises(RuleError, match="Invalid const"):
            store.register("r", 1,
                ["eq", ["field", "x"], ["const", 1.5]], 0)

    def test_decimal_nan_const_raises(self):
        """A2: Decimal NaN rejected at registration via encode()."""
        store = RuleStore()
        with pytest.raises(RuleError, match="Invalid const"):
            store.register("r", 1,
                ["eq", ["field", "x"], ["const", Decimal("NaN")]], 0)

    def test_valid_spec_accepted(self):
        store = RuleStore()
        record = store.register("r", 1, SPEC_V1, ltime=0)
        assert record["kind"] == "rule_version"


# -- Version discipline ----------------------------------------------------

class TestVersionDiscipline:
    def test_register_v1(self):
        store = RuleStore()
        rec = store.register("r", 1, SPEC_V1, ltime=0)
        assert rec["version"] == 1

    def test_register_v2_after_v1(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        rec = store.register("r", 2, SPEC_V2, ltime=5)
        assert rec["version"] == 2

    def test_register_v2_before_v1_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="First version must be 1"):
            store.register("r", 2, SPEC_V2, ltime=0)

    def test_reregister_v1_raises(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        with pytest.raises(RuleError, match="Already registered"):
            store.register("r", 1, SPEC_V1, ltime=0)

    def test_version_gap_raises(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        with pytest.raises(RuleError, match="Version gap"):
            store.register("r", 3, SPEC_V2, ltime=0)

    def test_latest_version(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        assert store.latest_version("r") == 1
        store.register("r", 2, SPEC_V2, ltime=5)
        assert store.latest_version("r") == 2

    def test_unknown_rule_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="Unknown rule"):
            store.get("missing", 1)

    def test_unknown_rule_latest_raises(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="Unknown rule"):
            store.latest_version("missing")

    def test_version_not_found_raises(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        with pytest.raises(RuleError, match="Version not found"):
            store.get("r", 99)

    def test_version_must_be_int(self):
        store = RuleStore()
        with pytest.raises(RuleError, match="must be int"):
            store.register("r", True, SPEC_V1, ltime=0)

    def test_get_returns_record(self):
        store = RuleStore()
        store.register("r", 1, SPEC_V1, ltime=0)
        rec = store.get("r", 1)
        assert rec["rule_id"] == "r"
        assert rec["fn_spec"] == SPEC_V1


# -- Semantics matrix (6+ observations) ------------------------------------

class TestSemanticsMatrix:
    def test_pass(self):
        """All conditions met -> verdict True."""
        result = evaluate(_make_rule(SPEC_V1), OBS_PASS)
        assert result["verdict"] is True

    def test_fail_wrong_source(self):
        """source_id not in allowed list -> verdict False."""
        result = evaluate(_make_rule(SPEC_V1), OBS_FAIL_SOURCE)
        assert result["verdict"] is False

    def test_fail_low_ltime(self):
        """ltime too low -> verdict False."""
        result = evaluate(_make_rule(SPEC_V1), OBS_FAIL_LTIME)
        assert result["verdict"] is False

    def test_missing_field_raises(self):
        """Rule references source_id, observation lacks it -> RuleError."""
        with pytest.raises(RuleError, match="Missing field"):
            evaluate(_make_rule(SPEC_V1), OBS_MISSING_FIELD)

    def test_type_mismatch_raises(self):
        """gt(str, int) -> RuleError (type mismatch)."""
        with pytest.raises(RuleError, match="[Tt]ype mismatch"):
            evaluate(_make_rule(SPEC_TEMP), OBS_TYPE_MISMATCH)

    def test_bool_ordering_raises(self):
        """A1: gt(True, 100) -> RuleError (bool excluded)."""
        with pytest.raises(RuleError, match="[Bb]ool"):
            evaluate(_make_rule(SPEC_TEMP), OBS_BOOL_ORDERING)

    def test_not_operator(self):
        """not(eq(field, const))."""
        spec = ["not", ["eq", ["field", "source_id"], ["const", "alice"]]]
        result = evaluate(_make_rule(spec), OBS_PASS)
        assert result["verdict"] is False

    def test_or_operator(self):
        """or(eq(source, 'charlie'), eq(source, 'alice'))."""
        spec = ["or",
            ["eq", ["field", "source_id"], ["const", "charlie"]],
            ["eq", ["field", "source_id"], ["const", "alice"]],
        ]
        result = evaluate(_make_rule(spec), OBS_PASS)
        assert result["verdict"] is True


# -- Amendment A1: strict type-category equality ----------------------------

class TestStrictEquality:
    def test_eq_true_one_false(self):
        """A1: eq(True, 1) -> False (different categories)."""
        spec = ["eq", ["field", "v"], ["const", 1]]
        obs = {"id": "x", "v": True, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is False

    def test_eq_int_decimal_false(self):
        """A1: eq(1, Decimal('1')) -> False (different categories)."""
        spec = ["eq", ["field", "v"], ["const", Decimal("1")]]
        obs = {"id": "x", "v": 1, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is False

    def test_in_true_list_of_one_false(self):
        """A1: in(True, [1]) -> False (bool != int)."""
        spec = ["in", ["field", "v"], ["const", [1, 2, 3]]]
        obs = {"id": "x", "v": True, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is False

    def test_gt_true_zero_raises(self):
        """A1: gt(True, 0) -> RuleError (bool excluded from ordering)."""
        spec = ["gt", ["field", "v"], ["const", 0]]
        obs = {"id": "x", "v": True, "ltime": 0}
        with pytest.raises(RuleError, match="[Bb]ool"):
            evaluate(_make_rule(spec), obs)

    def test_ge_decimal_int_true(self):
        """A1: ge(Decimal('2'), 1) -> True (int<->Decimal permitted)."""
        spec = ["ge", ["field", "v"], ["const", 1]]
        obs = {"id": "x", "v": Decimal("2"), "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is True

    def test_eq_none_none_true(self):
        """Same category, same value."""
        spec = ["eq", ["field", "v"], ["const", None]]
        obs = {"id": "x", "v": None, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is True

    def test_ne_true_one_true(self):
        """A1: ne(True, 1) -> True (different categories)."""
        spec = ["ne", ["field", "v"], ["const", 1]]
        obs = {"id": "x", "v": True, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is True

    def test_eq_same_type_true(self):
        """Same category, same value -> True."""
        spec = ["eq", ["field", "v"], ["const", 42]]
        obs = {"id": "x", "v": 42, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is True

    def test_in_member_same_type(self):
        """in with same-type match."""
        spec = ["in", ["field", "v"], ["const", [1, 2, 3]]]
        obs = {"id": "x", "v": 2, "ltime": 0}
        result = evaluate(_make_rule(spec), obs)
        assert result["verdict"] is True

    def test_in_non_list_raises(self):
        """'in' with non-list container -> RuleError."""
        spec = ["in", ["field", "v"], ["const", "not-a-list"]]
        obs = {"id": "x", "v": "a", "ltime": 0}
        with pytest.raises(RuleError, match="requires a list"):
            evaluate(_make_rule(spec), obs)


# -- Amendment A3: observation_id in result ---------------------------------

class TestObservationId:
    def test_observation_id_in_result(self):
        """A3: result contains observation_id."""
        result = evaluate(_make_rule(SPEC_V1), OBS_PASS)
        assert result["observation_id"] == "obs-1"

    def test_missing_observation_id_raises(self):
        """A3: observation without 'id' -> RuleError."""
        obs = {"ltime": 5, "source_id": "alice"}
        with pytest.raises(RuleError, match="missing.*'id'"):
            evaluate(_make_rule(SPEC_V1), obs)

    def test_missing_observation_ltime_raises(self):
        """Observation without 'ltime' -> RuleError."""
        obs = {"id": "x", "source_id": "alice"}
        with pytest.raises(RuleError, match="missing.*'ltime'"):
            evaluate(_make_rule(SPEC_V1), obs)


# -- Rule-version substitution (counterfactual substrate) -------------------

class TestRuleVersionSubstitution:
    def test_v1_rejects_v2_accepts(self):
        """Same observation: v1 rejects (wrong source), v2 accepts."""
        store = RuleStore()
        store.register("src-chk", 1, SPEC_V1, ltime=0)
        store.register("src-chk", 2, SPEC_V2, ltime=5)

        obs = OBS_FAIL_SOURCE  # charlie, ltime=5

        r1 = evaluate(store.get("src-chk", 1), obs)
        assert r1["verdict"] is False

        r2 = evaluate(store.get("src-chk", 2), obs)
        assert r2["verdict"] is True


# -- Boolean connectives (no short-circuit) ---------------------------------

class TestBooleanConnectives:
    def test_and_all_true(self):
        spec = ["and",
            ["eq", ["field", "a"], ["const", 1]],
            ["eq", ["field", "b"], ["const", 2]],
        ]
        obs = {"id": "x", "a": 1, "b": 2, "ltime": 0}
        assert evaluate(_make_rule(spec), obs)["verdict"] is True

    def test_and_one_false(self):
        spec = ["and",
            ["eq", ["field", "a"], ["const", 1]],
            ["eq", ["field", "b"], ["const", 99]],
        ]
        obs = {"id": "x", "a": 1, "b": 2, "ltime": 0}
        assert evaluate(_make_rule(spec), obs)["verdict"] is False

    def test_and_propagates_error(self):
        """No short-circuit: error in second operand surfaces."""
        spec = ["and",
            ["eq", ["field", "a"], ["const", 99]],  # False
            ["gt", ["field", "b"], ["const", 0]],    # b=True -> RuleError
        ]
        obs = {"id": "x", "a": 1, "b": True, "ltime": 0}
        with pytest.raises(RuleError, match="[Bb]ool"):
            evaluate(_make_rule(spec), obs)

    def test_or_all_false(self):
        spec = ["or",
            ["eq", ["field", "a"], ["const", 99]],
            ["eq", ["field", "a"], ["const", 98]],
        ]
        obs = {"id": "x", "a": 1, "ltime": 0}
        assert evaluate(_make_rule(spec), obs)["verdict"] is False

    def test_or_one_true(self):
        spec = ["or",
            ["eq", ["field", "a"], ["const", 99]],
            ["eq", ["field", "a"], ["const", 1]],
        ]
        obs = {"id": "x", "a": 1, "ltime": 0}
        assert evaluate(_make_rule(spec), obs)["verdict"] is True


# -- Evaluate result shape --------------------------------------------------

class TestEvaluateResultShape:
    def test_result_keys(self):
        result = evaluate(_make_rule(SPEC_V2), OBS_PASS)
        assert set(result.keys()) == {
            "kind", "rule_id", "version", "verdict",
            "observation_id", "ltime",
        }
        assert result["kind"] == "verification_result"
        assert result["rule_id"] == "r"
        assert result["version"] == 1
        assert result["ltime"] == 5
        assert result["observation_id"] == "obs-1"

    def test_result_encodable(self):
        """Result round-trips through serialization."""
        result = evaluate(_make_rule(SPEC_V2), OBS_PASS)
        data = encode(result)
        restored = decode(data)
        assert restored == result


# -- Golden files -----------------------------------------------------------

class TestGolden:
    def test_golden_rule_v1(self):
        """v1 evidence record encodes byte-stably."""
        store = RuleStore()
        rec = store.register("source-check", 1, SPEC_V1, ltime=0)
        golden = GOLDEN_DIR / "rule_v1.bin"
        assert encode(rec) == golden.read_bytes()

    def test_golden_rule_v2(self):
        """v2 evidence record encodes byte-stably."""
        store = RuleStore()
        store.register("source-check", 1, SPEC_V1, ltime=0)
        rec = store.register("source-check", 2, SPEC_V2, ltime=5)
        golden = GOLDEN_DIR / "rule_v2.bin"
        assert encode(rec) == golden.read_bytes()


# -- Rule entity id ---------------------------------------------------------

class TestRuleEntityId:
    def test_format(self):
        assert rule_entity_id("threshold", 1) == "rule:threshold:v1"
        assert rule_entity_id("src-chk", 3) == "rule:src-chk:v3"


# -- Cross-process determinism ---------------------------------------------

class TestCrossProcessDeterminism:
    def test_different_hashseed_same_bytes(self):
        """Same spec + obs in two subprocesses -> identical bytes."""
        script = _CROSS_PROCESS_SCRIPT
        results = []
        for seed in ("12345", "99999"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                env=env,
                cwd=str(Path(__file__).parents[1]),
            )
            assert proc.returncode == 0, proc.stderr.decode()
            results.append(proc.stdout)
        assert results[0] == results[1]


_CROSS_PROCESS_SCRIPT = """\
from ri_core.rules import evaluate, RuleStore
from ri_core.serialization import encode
import sys

store = RuleStore()
spec = ["and",
    ["ge", ["field", "ltime"], ["const", 1]],
    ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
]
record = store.register("src-chk", 1, spec, ltime=0)
obs = {"id": "obs-1", "source_id": "alice", "ltime": 5, "prop": "sky"}
result = evaluate(record, obs)
sys.stdout.buffer.write(encode(result))
"""
