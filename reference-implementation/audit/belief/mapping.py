"""Frozen-snapshot -> adapter-input mapping (PREREGISTRATION §4, §6).

The wall-frozen C2 adapter (rights_events.adapters.cook_parcels) parses
its own fixture formats; this module maps the frozen CF-025 audit
snapshots into those formats for the 44 contested-set parcels, under the
conventions ratified at the 2026-08-04 Plan Gate:

D1  attested-alias canonicalization: a party string matched by the
    composed client predicate (audit.rules.client_match OR normalized
    exact match against an attested client-alias variant from
    attestations.yaml) is canonicalized to CANONICAL_CLIENT before the
    adapter sees it. Verbatim strings are preserved in the run context
    and cited in the determination.
D2  placeholder rule: roll owner strings in PLACEHOLDER_OWNER_STRINGS
    name nobody and produce NO roll observation. NULL stays NULL.
D3  tax-sale rows (annual 55ju-2fs9, scavenger ydgz-vkrp) are NOT
    folded; they are carried as cited per-parcel context.
D4  CRM disposition claims are NOT folded; carried as context.

Mass declarations (PREREGISTRATION §5) are mirrored here and test-pinned
against rights_events.policy.CLAIM_MASS and the frozen preregistration
document, so a silent edit of any of the three fails the suite.

Consumes audit.rules and audit.attestation.events READ-ONLY.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from audit import rules
from audit.attestation import events as attestation_events

ROOT = Path(__file__).resolve().parents[2]

MANIFEST_PATH = (ROOT / "audit" / "out" / "attested-remediated-2026-08-02"
                 / "contested-set-manifest.json")
# Pinned frozen input (PREREGISTRATION §1). Drift = refuse to run.
MANIFEST_SHA256 = (
    "0a9df51fa5d14fdb609a467bc2534939ce0d40f33e1b80eb941c076895ec36fc")

SNAPSHOT_DIR = ROOT / "audit" / "snapshots"
ATTESTATIONS_PATH = ROOT / "audit" / "attestation" / "attestations.yaml"

# --- PREREGISTRATION §5 mass declarations, mirrored (test-pinned) ---------
STATUTORY_CLAIM_MASS = Decimal("0.6")
DISPUTE_CLAIM_MASS = Decimal("0")

# --- PREREGISTRATION §4 conventions (test-pinned) -------------------------
CANONICAL_CLIENT = "SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY"
PLACEHOLDER_OWNER_STRINGS = ("TAXPAYER OF",)
# The attested client-alias variants at freeze; attestations.yaml drifting
# from this tuple is a stop, not a silent re-run.
EXPECTED_ALIAS_VARIANTS = (
    "LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL "
    "AGENCY",
    "SO SUB LAND BANK",
    "SOUTH SUB LAND BK",
    "SOUTH SUBN LAND BK & DEV AUTH",
    "SO SUB LAND/BK/DEV",
)


class BeliefInputError(Exception):
    """A frozen input is missing, malformed, or has drifted from its pin."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BeliefInputError(f"{path}: {exc}") from exc


def load_manifest() -> dict:
    """The pinned contested-set manifest (frozen input, sha-verified)."""
    actual = _sha256(MANIFEST_PATH)
    if actual != MANIFEST_SHA256:
        raise BeliefInputError(
            f"contested-set-manifest.json sha256 {actual} != pinned "
            f"{MANIFEST_SHA256}; the frozen input has drifted — STOP")
    manifest = _load_json(MANIFEST_PATH)
    if len(manifest["parcels"]) != 44:
        raise BeliefInputError(
            f"manifest parcel count {len(manifest['parcels'])} != 44")
    return manifest


def load_alias_norms() -> set[str]:
    """Normalized attested client-alias strings, pinned against drift."""
    events = attestation_events.parse(
        ATTESTATIONS_PATH.read_text(encoding="utf-8"))
    variants = attestation_events.alias_strings(events)
    if tuple(variants) != EXPECTED_ALIAS_VARIANTS:
        raise BeliefInputError(
            f"attestations.yaml client-alias variants {variants!r} differ "
            f"from the preregistered set; a silent attestation change is "
            f"a stop, not a re-run")
    return {rules.normalize(v) for v in variants}


def is_client(name: str | None, alias_norms: set[str]) -> bool:
    """Composed client predicate (PREREGISTRATION §4, ruling D1)."""
    if not name:
        return False
    return rules.client_match(name) or rules.normalize(name) in alias_norms


def canonical_name(name: str | None, alias_norms: set[str]) -> str | None:
    if name is not None and is_client(name, alias_norms):
        return CANONICAL_CLIENT
    return name


def build_inputs(manifest: dict) -> dict:
    """Map the frozen snapshots to adapter inputs for the manifest PINs.

    Returns a dict with the three adapter input row lists (deeds, owners,
    forfeitures — the last empty per ruling D3), the canonicalization log
    (verbatim -> canonical substitutions, ruling D1), the placeholder
    drops (ruling D2), and per-parcel unfolded context (tax, scavenger,
    CRM rows verbatim, with their snapshot retrieval provenance).
    """
    pins14 = [p["pin"].replace("-", "") for p in manifest["parcels"]]
    pin_set = set(pins14)

    deeds_snap = _load_json(SNAPSHOT_DIR / "ccao_parcel_sales.json")
    assessor_snap = _load_json(SNAPSHOT_DIR / "cc_assessor.json")
    tax_snap = _load_json(SNAPSHOT_DIR / "tax_agency.json")
    scav_snap = _load_json(SNAPSHOT_DIR / "tax_agency_scavenger.json")
    crm_snap = _load_json(SNAPSHOT_DIR / "crm_inventory.json")

    roll_retrieved = assessor_snap["retrieval"]["retrieved_date"]
    if not (isinstance(roll_retrieved, str) and len(roll_retrieved) == 10):
        raise BeliefInputError(
            f"cc_assessor retrieval.retrieved_date {roll_retrieved!r} is "
            f"not an ISO date")

    alias_norms = load_alias_norms()
    canonicalizations: list[dict] = []

    def canon(pin: str, channel: str, field: str, value):
        out = canonical_name(value, alias_norms)
        if out != value:
            canonicalizations.append({
                "pin14": pin, "channel": channel, "field": field,
                "verbatim": value, "canonical": out,
            })
        return out

    # Deeds (PREREGISTRATION §6): doc_no -> doc_number, sale_date[:10].
    deed_rows = []
    for row in deeds_snap["records"]:
        if row["pin"] not in pin_set:
            continue
        sale_date = row.get("sale_date")
        if not (isinstance(sale_date, str) and len(sale_date) >= 10):
            raise BeliefInputError(
                f"deed {row.get('doc_no')!r} for {row['pin']} has no "
                f"usable sale_date; an undated deed produces no "
                f"observation and none was expected in this set")
        deed_rows.append({
            "pin": row["pin"],
            "doc_number": row.get("doc_no"),
            "deed_type": row.get("deed_type"),
            "sale_date": sale_date[:10],
            "sale_price": row.get("sale_price"),
            "seller_name": canon(row["pin"], "deeds", "seller_name",
                                 row.get("seller_name")),
            "buyer_name": canon(row["pin"], "deeds", "buyer_name",
                                row.get("buyer_name")),
        })
    deed_rows.sort(key=lambda r: (r["pin"], r["sale_date"],
                                  r["doc_number"] or ""))

    # Roll (PREREGISTRATION §6): max-year row per PIN; D2 placeholder
    # filter; ingested_at = the snapshot's own retrieved_date.
    by_pin: dict[str, list[dict]] = {}
    for row in assessor_snap["records"]:
        if row["pin"] in pin_set:
            by_pin.setdefault(row["pin"], []).append(row)
    owner_rows = []
    placeholder_drops = []
    verbatim_roll: dict[str, dict] = {}
    for pin in sorted(by_pin):
        rows = sorted(by_pin[pin],
                      key=lambda r: (Decimal(str(r["year"])),
                                     r.get("row_id") or ""))
        top = rows[-1]
        owner = top.get("owner_address_name")
        verbatim_roll[pin] = {
            "owner_address_name": owner,
            "year": str(top["year"]),
            "row_id": top.get("row_id"),
        }
        if owner is None or owner.strip() in PLACEHOLDER_OWNER_STRINGS:
            placeholder_drops.append({
                "pin14": pin, "owner_address_name": owner,
                "year": str(top["year"]),
            })
            continue
        owner_rows.append({
            "pin": pin,
            "owner_name": canon(pin, "roll", "owner_name", owner),
            "ingested_at": roll_retrieved,
            "property_address": top.get("prop_address_full"),
            "property_city": top.get("prop_address_city_name"),
            "property_zip": top.get("prop_address_zipcode_1"),
            "township": None,
            "municipality": None,
            "class": None,
        })

    # Unfolded context (rulings D3, D4), verbatim with provenance.
    def rows_for(snap, key_field="pin", hyphenated=True):
        out: dict[str, list[dict]] = {}
        for row in snap["records"]:
            pin = str(row[key_field]).replace("-", "")
            if pin in pin_set:
                out.setdefault(pin, []).append(row)
        return out

    context = {
        "tax_agency": {
            "dataset_id": tax_snap["retrieval"]["dataset_id"],
            "retrieved_date": tax_snap["retrieval"]["retrieved_date"],
            "rows_by_pin14": rows_for(tax_snap),
        },
        "tax_agency_scavenger": {
            "dataset_id": scav_snap["retrieval"]["dataset_id"],
            "retrieved_date": scav_snap["retrieval"]["retrieved_date"],
            "rows_by_pin14": rows_for(scav_snap),
        },
        "crm_inventory": {
            "source_sha256": crm_snap["retrieval"]["source_sha256"],
            "retrieved_date": crm_snap["retrieval"]["retrieved_date"],
            "rows_by_pin14": {
                str(r["USER_ppn"]).replace("-", ""): r
                for r in crm_snap["records"]
                if str(r.get("USER_ppn", "")).replace("-", "") in pin_set
            },
        },
    }

    return {
        "pins14": pins14,
        "deed_rows": deed_rows,
        "owner_rows": owner_rows,
        "forfeiture_rows": [],  # ruling D3: tax-sale channel not folded
        "roll_retrieved_date": roll_retrieved,
        "deeds_dataset_id": deeds_snap["retrieval"]["dataset_id"],
        "assessor_dataset_id": assessor_snap["retrieval"]["dataset_id"],
        "verbatim_roll": verbatim_roll,
        "canonicalizations": canonicalizations,
        "placeholder_drops": placeholder_drops,
        "context": context,
    }
