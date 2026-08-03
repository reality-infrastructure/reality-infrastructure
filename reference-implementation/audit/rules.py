"""Frozen audit constants — the PREREGISTRATION.md values as code, test-pinned.

Every value here was pre-registered (audit/PREREGISTRATION.md, committed before
audit/engine.py existed). Changing any value requires a dated amendment in
PREREGISTRATION.md §9; the pinning tests fail otherwise by design.
"""
from __future__ import annotations

import re

# --- §2 closed verdict vocabulary -----------------------------------------
SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNSUPPORTED_NO_RECORD = "UNSUPPORTED_NO_RECORD"
AMBIGUOUS = "AMBIGUOUS"
NOT_CHECKABLE = "NOT_CHECKABLE"
VERDICTS = (SUPPORTED, CONTRADICTED, UNSUPPORTED_NO_RECORD, AMBIGUOUS, NOT_CHECKABLE)

NOT_CHECKABLE_REASONS = (
    "pin-format",
    "county-mismatch",
    "no-county-checkable-claim",
    "status-semantics-unresolved",
    "fetch-failed",
)

ABSENCE_FRAMING = "no machine-readable record found in the queried datasets"
COVERAGE_CAVEAT = (
    "Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-"
    "derived; exempt conveyances (tax deeds, government/land-bank deeds) may be "
    "structurally absent, and assessor rolls lag. Absence of a record is therefore "
    "reported as exactly that — never as \"not sold\" or \"not owned\"."
)

# --- §3 status -> claim-class map (all 24 observed values; else = STOP S2) --
DISPOSED = "DISPOSED"
HELD = "HELD"
CLAIM_UNCLEAR = "CLAIM_UNCLEAR"
NO_CLAIM = "NO_CLAIM"

STATUS_CLASS = {
    "Sold": DISPOSED,
    "Associated Parcel - Sold": DISPOSED,
    "Secured Inventory - Active": HELD,
    "Secured Inventory - Banked": HELD,
    "Listed": HELD,
    "Under Contract": HELD,
    "Demolition Phase": HELD,
    "In House Renovation Phase": HELD,
    "Deed Recorded": CLAIM_UNCLEAR,
    "Deed Issued": CLAIM_UNCLEAR,
    "Assigned": CLAIM_UNCLEAR,
    "To Be Secured": CLAIM_UNCLEAR,
    "Offer Pending": CLAIM_UNCLEAR,
    "Prospecting - Declined": NO_CLAIM,
    "Prospecting - Inspection Complete/Muni Evidence Needed": NO_CLAIM,
    "Prospecting - Hold for Review": NO_CLAIM,
    "Prospecting - Evidence Captured": NO_CLAIM,
    "Prospecting - Windshield Survey Requested": NO_CLAIM,
    "Acquisition Underway": NO_CLAIM,
    "Acquisition Method Failure": NO_CLAIM,
    "Case Dismissed": NO_CLAIM,
    "Associated Parcel - Inventory": NO_CLAIM,
    "Associated Parcel - Pre Inventory": NO_CLAIM,
    "Test Parcel": NO_CLAIM,
}

# --- §4 client aliases and normalization ----------------------------------
CLIENT_ALIAS_PATTERNS = (
    "SOUTH SUBURBAN LAND BANK",
    "SO SUBURBAN LAND BANK",
    "S SUBURBAN LAND BANK",
    "SOUTH SUBURBAN LAND BK",
    "SSLBDA",
)
NEAR_MISS_PATTERNS = ("LAND BANK", "LAND BK", "LANDBANK", "SSLBDA")

_PUNCT_RE = re.compile(r"[.,']")
_WS_RE = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Pilot-mirroring normalization: upper, & -> AND, / -> space, strip .,' ,
    collapse ws.

    '/' -> space is PREREGISTRATION.md §9 amendment A2 (2026-08-02, finding F1):
    county field-separator artifacts (LAND/BK) must normalize equal to their
    spaced forms (LAND BK) so the near-miss net can see them.
    """
    s = (name or "").upper().replace("&", " AND ").replace("/", " ")
    s = _PUNCT_RE.sub("", s)
    return _WS_RE.sub(" ", s).strip()


def client_match(name: str) -> bool:
    n = normalize(name)
    return any(p in n for p in CLIENT_ALIAS_PATTERNS)


def near_miss(name: str) -> bool:
    """A party string that looks land-bank-like but matches no attested alias.

    Forces AMBIGUOUS (PREREGISTRATION.md §4) — never silently matched.
    """
    n = normalize(name)
    return any(p in n for p in NEAR_MISS_PATTERNS) and not client_match(name)


# --- §5 window ------------------------------------------------------------
WINDOW_DAYS = 366

# --- §1 pinned source facts (verified by extract_crm.py; mismatch = STOP) --
CRM_SHA256 = "8d42089d14a03dfceb285a09f22147486f4c5d3279de6f2b833d4d3d46737067"
CRM_BYTES = 2104717
CRM_FEATURES = 740
CHECKABLE_COUNT = 694

# --- §7 fetch plan constants ----------------------------------------------
BATCH_SIZE = 50
FETCH_SPACING_SECONDS = 2
FETCH_RETRIES = 3
FETCH_FAIL_STOP_FRACTION = 0.05

# --- known answer (§6) ----------------------------------------------------
KNOWN_ANSWER_PIN14 = "29024080530000"
KNOWN_ANSWER_VERDICT = CONTRADICTED
