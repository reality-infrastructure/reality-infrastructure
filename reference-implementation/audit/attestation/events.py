"""Attestation events — the M-RI-15 input slot (PREREGISTRATION.md §9 amendment A1).

Operator rulings in attestations.yaml enter the audit as first-class,
provenance-carrying input events: (kind, subject verbatim, decision, basis,
attested_by, date). This module parses and validates them; it decides nothing.

Strict exact-format parser, stdlib only (no yaml dependency): the file is the
schema written by the M-RI-14 intake — two sections, quoted scalars, one
decision/basis/date triple per item. Any blank decision or basis, unknown
decision word, malformed date, or deviation from the pinned 13-item inventory
(8 name variants, 5 statuses) refuses the whole file. UNKNOWN ("uncertain") is
a valid ruling; a missing one is not.

The classifier and rules stay frozen: this module only *derives* the sets the
re-run composes at the rules boundary (attested alias strings, attested
not-client strings, status overrides). Matching is by normalized EXACT string
equality — narrower than the §4 substring patterns; a ruling never generalizes
beyond the string the operator saw.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from audit import rules

ATTESTED_BY = "operator"

VARIANT_DECISIONS = ("client-alias", "not-client", "uncertain")
STATUS_DECISIONS = (rules.DISPOSED, rules.HELD, rules.NO_CLAIM, "uncertain")

# Pinned inventory: the seven unattested name variants surfaced by the M-RI-14
# near-miss discipline (attestation-request.md), plus the F1 escaped variant
# attested in M-RI-16 (§9 amendment A2; gate evidence f1-gate-evidence.md).
EXPECTED_VARIANTS = (
    "C.C. LAND BANK AUTH. DO NOT USE(NO PINS)",
    "COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY",
    "LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY",
    "SO SUB LAND BANK",
    "SOUTH SUB LAND BK",
    "SOUTH SUBN LAND BK & DEV AUTH",
    "SUBURBAN LAND BANK &amp;",
    "SO SUB LAND/BK/DEV",
)

# The five unclear statuses are exactly the CLAIM_UNCLEAR keys of the frozen map.
EXPECTED_STATUSES = tuple(sorted(
    s for s, c in rules.STATUS_CLASS.items() if c == rules.CLAIM_UNCLEAR))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ITEM_RE = re.compile(r'^- (variant|status): "(.*)"$')
_FIELD_RE = re.compile(r'^(decision|basis|date): "(.*)"$')

DEFAULT_PATH = Path(__file__).parent / "attestations.yaml"


class AttestationError(ValueError):
    """The attestation file is incomplete or malformed — the re-run refuses."""


def _fail(msg: str) -> None:
    raise AttestationError(f"attestations.yaml: {msg}")


def parse(text: str) -> list[dict]:
    """Parse attestation file text -> list of event dicts (document order)."""
    section = None
    items: list[dict] = []
    current: dict | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "name_variants:":
            section, current = "name-variant", None
            continue
        if line == "statuses:":
            section, current = "status-semantics", None
            continue
        m = _ITEM_RE.match(line)
        if m:
            if section is None:
                _fail(f"line {lineno}: item outside any section")
            key, subject = m.groups()
            expected_key = "variant" if section == "name-variant" else "status"
            if key != expected_key:
                _fail(f"line {lineno}: '{key}:' item in {section} section")
            current = {"kind": section, "subject": subject,
                       "decision": None, "basis": None, "date": None,
                       "attested_by": ATTESTED_BY}
            items.append(current)
            continue
        m = _FIELD_RE.match(line)
        if m:
            if current is None:
                _fail(f"line {lineno}: field before any item")
            field, value = m.groups()
            if current[field] is not None:
                _fail(f"line {lineno}: duplicate '{field}' for "
                      f"{current['subject']!r}")
            current[field] = value
            continue
        _fail(f"line {lineno}: unrecognized line {line!r}")
    return items


def validate(events: list[dict]) -> list[dict]:
    """Refuse blanks, unknown decisions, bad dates, or inventory deviation."""
    variants = [e for e in events if e["kind"] == "name-variant"]
    statuses = [e for e in events if e["kind"] == "status-semantics"]
    if tuple(e["subject"] for e in variants) != EXPECTED_VARIANTS:
        _fail("name-variant inventory deviates from the pinned 7 "
              f"(got {[e['subject'] for e in variants]!r})")
    if tuple(sorted(e["subject"] for e in statuses)) != EXPECTED_STATUSES:
        _fail("status inventory deviates from the pinned 5 "
              f"(got {[e['subject'] for e in statuses]!r})")
    for e in events:
        allowed = (VARIANT_DECISIONS if e["kind"] == "name-variant"
                   else STATUS_DECISIONS)
        if not e["decision"]:
            _fail(f"{e['subject']!r}: blank decision — attestation is never "
                  "assumed; the re-run refuses to run on blanks")
        if e["decision"] not in allowed:
            _fail(f"{e['subject']!r}: decision {e['decision']!r} not in "
                  f"{allowed}")
        if not e["basis"]:
            _fail(f"{e['subject']!r}: blank basis — every ruling carries the "
                  "operator's stated basis")
        if not e["date"] or not _DATE_RE.match(e["date"]):
            _fail(f"{e['subject']!r}: date {e['date']!r} is not YYYY-MM-DD")
    return events


def load_events(path: str | Path = DEFAULT_PATH) -> list[dict]:
    return validate(parse(Path(path).read_text(encoding="utf-8")))


def serialize(events: list[dict]) -> str:
    """Canonical event serialization (JSON lines) — the round-trip surface."""
    return "\n".join(
        json.dumps(e, ensure_ascii=False, sort_keys=True) for e in events) + "\n"


def deserialize(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line]


# --- derived sets consumed by the re-run's boundary composition -------------

def alias_strings(events: list[dict]) -> tuple[str, ...]:
    return tuple(e["subject"] for e in events
                 if e["kind"] == "name-variant"
                 and e["decision"] == "client-alias")


def not_client_strings(events: list[dict]) -> tuple[str, ...]:
    return tuple(e["subject"] for e in events
                 if e["kind"] == "name-variant"
                 and e["decision"] == "not-client")


def status_overrides(events: list[dict]) -> dict[str, str]:
    """Status -> attested claim class, for rulings other than 'uncertain'."""
    return {e["subject"]: e["decision"] for e in events
            if e["kind"] == "status-semantics" and e["decision"] != "uncertain"}
