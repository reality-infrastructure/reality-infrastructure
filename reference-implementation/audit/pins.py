"""PIN normalization — pure, stdlib-only, no I/O (PREREGISTRATION.md §1).

Cook County PINs are 14 digits, conventionally hyphenated XX-XX-XXX-XXX-XXXX.
Anything else (including the inventory's Will-County 16-digit six-group PINs and
malformed values) is not checkable against the Cook datasets.
"""
from __future__ import annotations

import re

COOK_HYPHEN_RE = re.compile(r"^\d{2}-\d{2}-\d{3}-\d{3}-\d{4}$")


def is_cook_format(pin: str) -> bool:
    """True iff pin is Cook-format hyphenated (2-2-3-3-4 digit groups)."""
    return bool(COOK_HYPHEN_RE.match(pin or ""))


def to14(pin: str) -> str:
    """Cook hyphenated PIN -> 14-digit form. Raises on non-Cook-format input."""
    if not is_cook_format(pin):
        raise ValueError(f"not a Cook-format PIN: {pin!r}")
    return pin.replace("-", "")


def to_hyphen(pin14: str) -> str:
    """14-digit PIN -> hyphenated Cook form. Raises unless exactly 14 digits."""
    if not (len(pin14) == 14 and pin14.isdigit()):
        raise ValueError(f"not a 14-digit PIN: {pin14!r}")
    return "-".join((pin14[0:2], pin14[2:4], pin14[4:7], pin14[7:10], pin14[10:14]))
