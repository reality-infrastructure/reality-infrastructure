"""Tests for ri_core.serialization — canonical deterministic byte encoding.

Covers: round-trip, golden-file byte-identity, cross-process determinism,
type rejection, bool/int dispatch (A3), Decimal canonicalization (A1),
NFC collision detection (A2), version-byte handling, and hypothesis
property-based round-trip over Observation-shaped structures.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ri_core.serialization import SerializationError, decode, encode

GOLDEN_DIR = Path(__file__).parent / "golden" / "serialization"


# ── Golden fixtures (5 + 1 Observation-shaped records) ──────────────

FIXTURES = {
    "obs_simple": {
        "id": "obs-001",
        "source_id": "src-alpha",
        "proposition": "The parcel is occupied",
        "payload": None,
        "ltime": 1,
        "sig": b'\xde\xad\xbe\xef',
    },
    "obs_binary_payload": {
        "id": "obs-002",
        "source_id": "src-beta",
        "proposition": "Document hash verified",
        "payload": b'\x01\x02\x03\x04\x05',
        "ltime": 42,
        "sig": b'\xca\xfe\xba\xbe',
    },
    "obs_nested": {
        "id": "obs-003",
        "source_id": "src-gamma",
        "proposition": "Property assessed",
        "payload": {
            "assessed_value": Decimal("250000"),
            "currency": "USD",
            "components": [
                {"type": "land", "value": Decimal("100000")},
                {"type": "improvement", "value": Decimal("150000")},
            ],
        },
        "ltime": 100,
        "sig": b'\x00\x11\x22\x33',
    },
    "obs_decimal_weights": {
        "id": "obs-004",
        "source_id": "src-delta",
        "proposition": "Source is reliable",
        "payload": {
            "weight_a": Decimal("0.85"),
            "weight_b": Decimal("0.000001"),
        },
        "ltime": 7,
        "sig": b'\xff\x00\xff\x00',
    },
    "obs_minimal": {
        "id": "obs-005",
        "source_id": "src-epsilon",
        "proposition": "Null observation",
        "payload": None,
        "ltime": 0,
        "sig": b'\xaa',
    },
    "obs_tuple_payload": {
        "id": "obs-006",
        "source_id": "src-zeta",
        "proposition": "Coordinates recorded",
        "payload": (Decimal("40.7128"), Decimal("-74.006")),
        "ltime": 999,
        "sig": b'\xab\xcd\xef',
    },
}


# ── Helpers ─────────────────────────────────────────────────────────

def _generate_golden_files():
    """Generate golden .bin files from FIXTURES.  Run once, then freeze."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, fixture in FIXTURES.items():
        path = GOLDEN_DIR / f"{name}.bin"
        path.write_bytes(encode(fixture))
        print(f"  wrote {path}")


# ── Golden-file tests ──────────────────────────────────────────────

class TestGolden:
    """Encoding fixture records must byte-match frozen golden files."""

    @pytest.mark.parametrize("name", sorted(FIXTURES))
    def test_encode_matches_golden(self, name):
        golden_path = GOLDEN_DIR / f"{name}.bin"
        expected = golden_path.read_bytes()
        actual = encode(FIXTURES[name])
        assert actual == expected, (
            f"Golden mismatch for {name}: "
            f"expected {len(expected)} bytes, got {len(actual)}"
        )

    @pytest.mark.parametrize("name", sorted(FIXTURES))
    def test_decode_golden_roundtrip(self, name):
        golden_path = GOLDEN_DIR / f"{name}.bin"
        decoded = decode(golden_path.read_bytes())
        assert decoded == FIXTURES[name]


# ── Round-trip tests ───────────────────────────────────────────────

class TestRoundTrip:
    """decode(encode(x)) == x for every supported type."""

    def test_none(self):
        assert decode(encode(None)) is None

    def test_bool_true(self):
        result = decode(encode(True))
        assert result is True
        assert type(result) is bool

    def test_bool_false(self):
        result = decode(encode(False))
        assert result is False
        assert type(result) is bool

    @pytest.mark.parametrize("v", [0, 1, -1, 42, -42, 10**100])
    def test_int(self, v):
        assert decode(encode(v)) == v
        assert type(decode(encode(v))) is int

    @pytest.mark.parametrize("v", [
        "", "hello", "Unicode: \u00e9\u00f1\u00fc", "emoji: \U0001f600",
    ])
    def test_str(self, v):
        assert decode(encode(v)) == v

    @pytest.mark.parametrize("v", [b"", b"\x00", b"\xde\xad\xbe\xef",
                                    b"\xff" * 100])
    def test_bytes(self, v):
        assert decode(encode(v)) == v

    @pytest.mark.parametrize("v", [
        Decimal("0"), Decimal("1"), Decimal("-1"), Decimal("0.75"),
        Decimal("0.000001"), Decimal("99999999999999999999"),
    ])
    def test_decimal(self, v):
        assert decode(encode(v)) == v

    def test_list(self):
        obj = [1, "two", None, True, False]
        assert decode(encode(obj)) == obj

    def test_tuple(self):
        result = decode(encode((1, "two", None)))
        assert result == (1, "two", None)
        assert isinstance(result, tuple)

    def test_dict(self):
        d = {"z": 1, "a": 2, "m": "hello"}
        assert decode(encode(d)) == d

    def test_nested(self):
        obj = {
            "id": "obs-001",
            "payload": {
                "values": [Decimal("0.5"), Decimal("0.3")],
                "raw": b"\x01\x02",
                "coords": (1, 2, 3),
            },
            "ltime": 42,
        }
        assert decode(encode(obj)) == obj

    def test_empty_containers(self):
        for obj in [[], (), {}, b""]:
            assert decode(encode(obj)) == obj


# ── A3: bool / int dispatch ────────────────────────────────────────

class TestBoolIntDispatch:
    """Amendment A3: type checks must test bool before int."""

    def test_true_encodes_differently_from_one(self):
        assert encode(True) != encode(1)

    def test_false_encodes_differently_from_zero(self):
        assert encode(False) != encode(0)

    def test_true_roundtrip_preserves_type(self):
        assert type(decode(encode(True))) is bool

    def test_false_roundtrip_preserves_type(self):
        assert type(decode(encode(False))) is bool

    def test_one_roundtrip_preserves_type(self):
        assert type(decode(encode(1))) is int

    def test_zero_roundtrip_preserves_type(self):
        assert type(decode(encode(0))) is int


# ── A1: Decimal canonicalization ───────────────────────────────────

class TestDecimalCanonicalization:
    """Amendment A1: canonical Decimal encoding rules."""

    def test_equivalent_forms_identical_bytes(self):
        """Decimal('0.75'), Decimal('0.750'), Decimal('7.5E-1') must
        produce identical encoded bytes."""
        a = encode(Decimal("0.75"))
        b = encode(Decimal("0.750"))
        c = encode(Decimal("7.5E-1"))
        assert a == b == c

    def test_100_renders_as_plain_integer(self):
        """Decimal('100') must encode as '100', not '1E+2'."""
        encoded = encode(Decimal("100"))
        json_part = encoded[1:].decode('utf-8')
        obj = json.loads(json_part)
        assert obj["__v"] == "100"

    def test_negative_zero_normalizes_to_zero(self):
        assert encode(Decimal("-0")) == encode(Decimal("0"))

    def test_reject_nan(self):
        with pytest.raises(TypeError):
            encode(Decimal("NaN"))

    def test_reject_snan(self):
        with pytest.raises(TypeError):
            encode(Decimal("sNaN"))

    def test_reject_infinity(self):
        with pytest.raises(TypeError):
            encode(Decimal("Infinity"))

    def test_reject_negative_infinity(self):
        with pytest.raises(TypeError):
            encode(Decimal("-Infinity"))

    def test_reject_exponent_too_large(self):
        with pytest.raises(TypeError, match="adjusted exponent"):
            encode(Decimal("1E+21"))

    def test_reject_exponent_too_small(self):
        with pytest.raises(TypeError, match="adjusted exponent"):
            encode(Decimal("1E-7"))

    def test_boundary_exponent_minus_six(self):
        """Adjusted exponent -6 is the lower boundary — must succeed."""
        val = Decimal("0.000001")  # 1E-6, adjusted exponent = -6
        result = decode(encode(val))
        assert result == val

    def test_boundary_exponent_twenty(self):
        """Adjusted exponent 20 is the upper boundary — must succeed."""
        val = Decimal("1" + "0" * 20)  # 10^20, adjusted exponent = 20
        result = decode(encode(val))
        assert result == val


# ── A2: NFC collision detection ────────────────────────────────────

class TestNFCCollision:
    """Amendment A2: NFC-colliding dict keys must raise SerializationError."""

    def test_composed_vs_decomposed_e_acute(self):
        """Composed e-acute (U+00E9) vs decomposed (U+0065 U+0301)."""
        composed = "\u00e9"      # é as single code point
        decomposed = "e\u0301"   # e + combining acute accent
        assert composed != decomposed  # distinct Python strings
        with pytest.raises(SerializationError, match="NFC-normalize"):
            encode({composed: 1, decomposed: 2})

    def test_no_collision_for_distinct_nfc_keys(self):
        """Distinct NFC-stable keys must not raise."""
        d = {"\u00e9": 1, "a": 2, "z": 3}
        result = decode(encode(d))
        assert result == {"\u00e9": 1, "a": 2, "z": 3}


# ── Type rejection ─────────────────────────────────────────────────

class TestTypeRejection:
    """Unsupported types raise TypeError, never silent coercion."""

    def test_reject_float(self):
        with pytest.raises(TypeError, match="float"):
            encode(3.14)

    def test_reject_float_in_container(self):
        with pytest.raises(TypeError, match="float"):
            encode({"x": 1.0})

    def test_reject_set(self):
        with pytest.raises(TypeError):
            encode({1, 2, 3})

    def test_reject_custom_object(self):
        with pytest.raises(TypeError):
            encode(object())

    def test_reject_non_string_dict_key(self):
        with pytest.raises(TypeError, match="Dict keys must be str"):
            encode({1: "value"})


# ── Reserved key ───────────────────────────────────────────────────

class TestReservedKey:
    """The key '__t' is reserved for type envelopes."""

    def test_reject_reserved_key(self):
        with pytest.raises(SerializationError, match="reserved"):
            encode({"__t": "something", "data": 1})

    def test_reject_reserved_key_nested(self):
        with pytest.raises(SerializationError, match="reserved"):
            encode({"outer": {"__t": "inner", "x": 1}})


# ── Version byte ──────────────────────────────────────────────────

class TestVersionByte:
    """Format version handling in the first byte."""

    def test_version_one_prefix(self):
        assert encode(42)[0:1] == b'\x01'

    def test_reserved_version_zero(self):
        with pytest.raises(SerializationError, match="reserved"):
            decode(b'\x00{}')

    def test_unknown_version(self):
        with pytest.raises(SerializationError, match="Unsupported format"):
            decode(b'\xff{}')

    def test_empty_data(self):
        with pytest.raises(SerializationError, match="empty"):
            decode(b'')


# ── Dict-ordering determinism ──────────────────────────────────────

class TestDictOrderDeterminism:
    """Dict insertion order must not affect encoded bytes."""

    def test_insertion_order_irrelevant(self):
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"a": 2, "m": 3, "z": 1}
        d3 = {"m": 3, "z": 1, "a": 2}
        assert encode(d1) == encode(d2) == encode(d3)


# ── Cross-process determinism ─────────────────────────────────────

class TestCrossRunDeterminism:
    """Same input encoded in subprocesses with different PYTHONHASHSEED
    values must produce identical bytes."""

    def test_cross_process_determinism(self):
        root = str(Path(__file__).resolve().parent.parent)
        script = (
            "import sys\n"
            f"sys.path.insert(0, {root!r})\n"
            "from ri_core.serialization import encode\n"
            "from decimal import Decimal\n"
            "import base64\n"
            "obj = {\n"
            "    'id': 'obs-001',\n"
            "    'source_id': 'src-alpha',\n"
            "    'proposition': 'The parcel is occupied',\n"
            "    'payload': {'weight': Decimal('0.75'), 'data': [1, 2, 3]},\n"
            "    'ltime': 42,\n"
            "    'sig': b'\\xde\\xad\\xbe\\xef',\n"
            "}\n"
            "print(base64.b64encode(encode(obj)).decode(), end='')\n"
        )

        results = []
        for seed in ["0", "12345", "99999"]:
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env,
            )
            assert proc.returncode == 0, (
                f"Subprocess failed (seed={seed}): {proc.stderr}"
            )
            results.append(proc.stdout)

        assert results[0] == results[1], (
            f"Mismatch between seed=0 and seed=12345"
        )
        assert results[0] == results[2], (
            f"Mismatch between seed=0 and seed=99999"
        )


# ── Hypothesis property-based round-trip ───────────────────────────

# Strategies that generate only valid serializable values.
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-. ',
    ),
    max_size=30,
)

_safe_key = st.text(
    alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-.',
    ),
    min_size=1,
    max_size=15,
).filter(lambda s: s != '__t')

_ri_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10 ** 15), max_value=10 ** 15),
    _safe_text,
    st.binary(max_size=50),
)

_ri_payload = st.one_of(
    st.none(),
    _ri_leaf,
    st.lists(_ri_leaf, max_size=5),
    st.dictionaries(_safe_key, _ri_leaf, max_size=5),
)

_ri_observation = st.fixed_dictionaries({
    'id': _safe_text.filter(lambda s: len(s) > 0),
    'source_id': _safe_text.filter(lambda s: len(s) > 0),
    'proposition': _safe_text.filter(lambda s: len(s) > 0),
    'payload': _ri_payload,
    'ltime': st.integers(min_value=0, max_value=2 ** 53),
    'sig': st.binary(min_size=1, max_size=128),
})


class TestHypothesisRoundTrip:
    """Property-based round-trip over generated Observation-shaped data."""

    @given(obs=_ri_observation)
    @settings(max_examples=200)
    def test_roundtrip_observation(self, obs):
        assert decode(encode(obs)) == obs

    @given(leaf=_ri_leaf)
    @settings(max_examples=200)
    def test_roundtrip_leaf_values(self, leaf):
        assert decode(encode(leaf)) == leaf


# ── Runner for golden-file generation (not a test) ─────────────────

if __name__ == "__main__":
    print("Generating golden files...")
    _generate_golden_files()
    print("Done.")
