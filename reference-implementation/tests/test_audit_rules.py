"""M-RI-14: the pre-registered constants are pinned — a silent edit fails here.

The authoritative text is audit/PREREGISTRATION.md (committed before the engine).
Changing any value below requires a dated amendment there first.
"""
from audit import rules


def test_verdict_vocabulary_closed():
    assert rules.VERDICTS == (
        "SUPPORTED", "CONTRADICTED", "UNSUPPORTED_NO_RECORD", "AMBIGUOUS",
        "NOT_CHECKABLE")


def test_not_checkable_reasons_closed():
    assert rules.NOT_CHECKABLE_REASONS == (
        "pin-format", "county-mismatch", "no-county-checkable-claim",
        "status-semantics-unresolved", "fetch-failed")


def test_status_map_covers_exactly_the_24_registered_values():
    assert len(rules.STATUS_CLASS) == 24
    tallies = {"DISPOSED": 0, "HELD": 0, "CLAIM_UNCLEAR": 0, "NO_CLAIM": 0}
    for cls in rules.STATUS_CLASS.values():
        tallies[cls] += 1
    assert tallies == {
        "DISPOSED": 2, "HELD": 6, "CLAIM_UNCLEAR": 5, "NO_CLAIM": 11}


def test_client_aliases_pinned():
    assert rules.CLIENT_ALIAS_PATTERNS == (
        "SOUTH SUBURBAN LAND BANK", "SO SUBURBAN LAND BANK",
        "S SUBURBAN LAND BANK", "SOUTH SUBURBAN LAND BK", "SSLBDA")
    assert rules.NEAR_MISS_PATTERNS == (
        "LAND BANK", "LAND BK", "LANDBANK", "SSLBDA")


def test_normalization_mirrors_pilot_precedents():
    assert rules.normalize("CSMA BLT, LLC") == "CSMA BLT LLC"
    assert rules.normalize("RICHARD  THORTON") == "RICHARD THORTON"
    assert rules.normalize("STANDARD B&T T") == "STANDARD B AND T T"


def test_client_match_and_near_miss():
    assert rules.client_match("SOUTH SUBURBAN LAND BANK & DEV AUTH")
    assert rules.client_match("SSLBDA")
    # looks land-bank-like, matches no attested alias -> near miss, not a match
    assert not rules.client_match("COOK COUNTY LAND BANK AUTH")
    assert rules.near_miss("COOK COUNTY LAND BANK AUTH")
    # an ordinary bank is neither
    assert not rules.client_match("US BANK TR")
    assert not rules.near_miss("US BANK TR")


def test_source_pins_and_window():
    assert rules.CRM_SHA256 == (
        "8d42089d14a03dfceb285a09f22147486f4c5d3279de6f2b833d4d3d46737067")
    assert rules.CRM_BYTES == 2104717
    assert rules.CRM_FEATURES == 740
    assert rules.CHECKABLE_COUNT == 694
    assert rules.WINDOW_DAYS == 366
    assert rules.KNOWN_ANSWER_PIN14 == "29024080530000"
    assert rules.KNOWN_ANSWER_VERDICT == "CONTRADICTED"
