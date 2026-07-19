"""Canonical deterministic byte encoding for RI records.

Format
------
    VERSION_BYTE + canonical_json_utf8_bytes

Version 1 (byte 0x01)
    Canonical JSON under strict rules:
    - Keys sorted lexicographically by Unicode code points (sort_keys=True)
    - Minimal separators: no whitespace ((',', ':'))
    - ASCII-safe output (ensure_ascii=True) — eliminates platform-dependent
      Unicode handling in the json module
    - NFC collision detection on dict keys (A2) — two keys that
      NFC-normalize to the same string are rejected; keys and values are
      encoded in their original form to preserve exact round-trip
    - No floats — integers and decimal strings only
    - Type envelopes for bytes, Decimal, tuple (two-key dicts with reserved
      keys ``"__t"`` and ``"__v"``)

This module is the bottom of the ri_core dependency DAG: it imports nothing
from ri_core.
"""

from __future__ import annotations

import base64
import json
import unicodedata
from decimal import Decimal


_FORMAT_V1 = b'\x01'
_RESERVED_VERSION_ZERO = b'\x00'


class SerializationError(Exception):
    """Error in serialization or deserialization.

    Raised for format violations, NFC-collision on dict keys, reserved-key
    usage, and unknown format versions.  Type mismatches raise TypeError.
    """


# ---------------------------------------------------------------------------
# Decimal canonicalization (A1)
# ---------------------------------------------------------------------------

def _canonical_decimal_str(d: Decimal) -> str:
    """Return canonical fixed-point string for a Decimal value.

    Rules (amendment A1):
    - Reject NaN, sNaN, Infinity, -Infinity with TypeError.
    - Normalize -0 to "0".
    - Normalize the value (strip trailing coefficient zeros).
    - If adjusted exponent is in [-6, 20], render as plain fixed-point or
      integer string — no exponent notation, no trailing zeros, no '+'.
    - Otherwise reject with TypeError (out-of-range magnitudes have no use
      in RI weights, which live in [0, 1]).
    """
    # NaN / Infinity checks MUST precede arithmetic comparisons (sNaN would
    # raise InvalidOperation on ==).
    if d.is_nan() or d.is_snan():
        raise TypeError(f"Cannot serialize Decimal NaN: {d!r}")
    if d.is_infinite():
        raise TypeError(f"Cannot serialize Decimal Infinity: {d!r}")

    # All zero variants (including -0) → "0"
    if d == 0:
        return "0"

    d = d.normalize()
    adj_exp = d.adjusted()
    if adj_exp < -6 or adj_exp > 20:
        raise TypeError(
            f"Decimal adjusted exponent {adj_exp} outside allowed range "
            f"[-6, 20]: {d!r}"
        )

    sign, digits, exponent = d.as_tuple()
    coeff = ''.join(str(dig) for dig in digits)

    if exponent >= 0:
        # Integer (possibly with trailing zeros from the exponent).
        result = coeff + '0' * exponent
    else:
        decimal_places = -exponent
        if len(coeff) > decimal_places:
            split_at = len(coeff) - decimal_places
            result = coeff[:split_at] + '.' + coeff[split_at:]
        else:
            leading_zeros = decimal_places - len(coeff)
            result = '0.' + '0' * leading_zeros + coeff

    return ('-' + result) if sign else result


# ---------------------------------------------------------------------------
# Python → canonical JSON-compatible form
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    """NFC-normalize a Unicode string."""
    return unicodedata.normalize('NFC', s)


def _to_canonical(obj):  # noqa: C901  (dispatch by type)
    """Transform a Python object into a JSON-compatible canonical form.

    Bool is tested before int (amendment A3).  Unsupported types raise
    TypeError; reserved-key and NFC-collision violations raise
    SerializationError.
    """
    if obj is None:
        return None

    # A3: bool before int (bool is a subclass of int in Python).
    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int):
        return obj

    if isinstance(obj, str):
        return obj

    if isinstance(obj, bytes):
        b64 = base64.urlsafe_b64encode(obj).rstrip(b'=').decode('ascii')
        return {"__t": "bytes", "__v": b64}

    if isinstance(obj, Decimal):
        return {"__t": "decimal", "__v": _canonical_decimal_str(obj)}

    if isinstance(obj, tuple):
        return {"__t": "tuple", "__v": [_to_canonical(item) for item in obj]}

    if isinstance(obj, list):
        return [_to_canonical(item) for item in obj]

    if isinstance(obj, dict):
        # All keys must be strings.
        for key in obj:
            if not isinstance(key, str):
                raise TypeError(
                    f"Dict keys must be str, got {type(key).__name__}: {key!r}"
                )

        # NFC collision detection (amendment A2): if two distinct keys
        # NFC-normalize to the same string, raise — never silently merge.
        # Keys are encoded in their original form to preserve round-trip.
        nfc_seen: dict[str, str] = {}
        for key in obj:
            nfc_key = _nfc(key)
            if nfc_key in nfc_seen:
                raise SerializationError(
                    f"Dict keys {nfc_seen[nfc_key]!r} and {key!r} "
                    f"both NFC-normalize to {nfc_key!r}"
                )
            nfc_seen[nfc_key] = key

        # Reserved key — "__t" is used for type envelopes.
        if "__t" in nfc_seen:
            raise SerializationError(
                "Dict key '__t' is reserved for type envelopes"
            )

        # Build transformed dict.  json.dumps(sort_keys=True) handles
        # ordering; insertion order here is irrelevant.
        return {key: _to_canonical(val) for key, val in obj.items()}

    if isinstance(obj, float):
        raise TypeError(
            f"Cannot serialize float: {obj!r}. Use int or Decimal."
        )

    raise TypeError(
        f"Unsupported type for serialization: {type(obj).__name__}"
    )


# ---------------------------------------------------------------------------
# Canonical JSON-compatible form → Python
# ---------------------------------------------------------------------------

def _from_canonical(obj):
    """Transform a JSON-parsed structure back into Python objects.

    Type envelopes (dicts with exactly keys ``"__t"`` and ``"__v"``) are
    restored to their original Python types.
    """
    if obj is None:
        return None

    # A3: bool before int.
    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int):
        return obj

    if isinstance(obj, str):
        return obj

    if isinstance(obj, list):
        return [_from_canonical(item) for item in obj]

    if isinstance(obj, dict):
        # Type envelope detection: exactly two keys, "__t" and "__v".
        if len(obj) == 2 and "__t" in obj and "__v" in obj:
            tag = obj["__t"]
            val = obj["__v"]
            if tag == "bytes":
                padded = val + '=' * (-len(val) % 4)
                return base64.urlsafe_b64decode(padded)
            if tag == "decimal":
                return Decimal(val)
            if tag == "tuple":
                return tuple(_from_canonical(item) for item in val)
            raise SerializationError(f"Unknown type envelope tag: {tag!r}")
        return {k: _from_canonical(v) for k, v in obj.items()}

    raise SerializationError(
        f"Unexpected JSON-parsed type: {type(obj).__name__}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode(obj) -> bytes:
    """Encode a Python object to canonical deterministic bytes.

    Pure function.  Output is byte-identical regardless of dict insertion
    order, platform, or PYTHONHASHSEED.

    Supported types: None, bool, int, str, bytes, Decimal, tuple, list,
    dict (str keys only).

    Raises:
        TypeError: for float, non-string dict keys, or any unsupported type.
        SerializationError: for reserved key ``"__t"`` in dicts, or NFC
            key collision.
    """
    canonical = _to_canonical(obj)
    json_text = json.dumps(
        canonical,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        allow_nan=False,
    )
    return _FORMAT_V1 + json_text.encode('utf-8')


def decode(data: bytes):
    """Decode canonical deterministic bytes to a Python object.

    Pure function.  Round-trip: ``decode(encode(x)) == x`` for every
    supported type.

    Raises:
        SerializationError: for empty data, reserved version 0x00,
            unsupported version, or malformed content.
    """
    if not data:
        raise SerializationError("Cannot decode empty data")
    version = data[0:1]
    if version == _RESERVED_VERSION_ZERO:
        raise SerializationError("Format version 0x00 is reserved")
    if version != _FORMAT_V1:
        raise SerializationError(
            f"Unsupported format version: 0x{data[0]:02x}"
        )
    json_text = data[1:].decode('utf-8')
    parsed = json.loads(json_text)
    return _from_canonical(parsed)
