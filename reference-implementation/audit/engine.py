"""Pure verdict classifier — implements PREREGISTRATION.md §5 exactly.

No network, no wall clock: every date in the output comes from the snapshot bytes
(record dates and retrieval blocks). Deterministic: sorted iteration everywhere.
Rules D1–D5 / H1–H5 and the NEAR-MISS override were pre-registered before this file
existed; changing behavior requires a dated amendment in PREREGISTRATION.md §9.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from audit import pins, rules


# --------------------------------------------------------------------------
# snapshot loading (bytes only)
# --------------------------------------------------------------------------

def load_snapshots(snapdir: str | Path) -> dict:
    """Load the five audit snapshots; returns {source_id: snapshot_dict}."""
    snapdir = Path(snapdir)
    out = {}
    for name in ("crm_inventory", "ccao_parcel_sales", "cc_assessor",
                 "tax_agency", "tax_agency_scavenger"):
        out[name] = json.loads((snapdir / f"{name}.json").read_text(encoding="utf-8"))
    return out


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _year(s) -> int | None:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _index_by_pin14(records: list[dict]) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for r in records:
        pin = str(r.get("pin", "")).replace("-", "")
        idx.setdefault(pin, []).append(r)
    return idx


# --------------------------------------------------------------------------
# citations
# --------------------------------------------------------------------------

def _cite_deed(r: dict, retrieved: str) -> dict:
    return {
        "source_id": "ccao_parcel_sales", "dataset_id": "wvhk-k5uv",
        "record": r.get("doc_no"), "date_field": "sale_date",
        "date": (r.get("sale_date") or "")[:10] or None,
        "parties": f"{r.get('seller_name')} -> {r.get('buyer_name')}",
        "retrieved": retrieved,
    }


def _cite_assessor(r: dict, retrieved: str) -> dict:
    return {
        "source_id": "cc_assessor", "dataset_id": "3723-97qp",
        "record": r.get("row_id"), "date_field": "year",
        "date": str(r.get("year")),
        "parties": (f"owner={r.get('owner_address_name')} "
                    f"mail={r.get('mail_address_name')}"),
        "retrieved": retrieved,
    }


def _cite_absence(retrieved: str) -> dict:
    return {
        "source_id": "attested-queries", "dataset_id": "wvhk-k5uv,3723-97qp",
        "record": None, "date_field": None, "date": None,
        "parties": rules.ABSENCE_FRAMING, "retrieved": retrieved,
    }


# --------------------------------------------------------------------------
# per-parcel classification
# --------------------------------------------------------------------------

def _party_strings(deeds: list[dict], assessor: list[dict]) -> list[str]:
    out = []
    for r in deeds:
        out.extend([r.get("seller_name") or "", r.get("buyer_name") or ""])
    for r in assessor:
        out.extend([r.get("owner_address_name") or "",
                    r.get("mail_address_name") or ""])
    return [s for s in out if s]


def classify(crm: dict, deeds: list[dict], assessor: list[dict],
             tax: list[dict], scav: list[dict], retrieved: str) -> dict:
    """One CRM record -> one verdict record (PREREGISTRATION.md §5)."""
    ppn = crm["USER_ppn"]
    status = crm["USER_disp_status"]
    cls = rules.STATUS_CLASS[status]
    v = {
        "pin": ppn,
        "pin14": pins.to14(ppn) if crm["cook_format"] else None,
        "status": status, "claim_class": cls,
        "claim_date": crm.get("USER_date_disposed"),
        "verdict": None, "reason": None, "rule": None,
        "citations": [], "near_miss_strings": [],
        "tax_sale_rows": len(tax), "scavenger_rows": len(scav),
    }

    # NOT_CHECKABLE gates, in fixed order
    if not crm["cook_format"]:
        v.update(verdict=rules.NOT_CHECKABLE, reason="pin-format")
        return v
    if not crm["checkable"]:
        v.update(verdict=rules.NOT_CHECKABLE, reason="county-mismatch")
        return v
    if cls == rules.CLAIM_UNCLEAR:
        v.update(verdict=rules.NOT_CHECKABLE, reason="status-semantics-unresolved")
        return v
    if cls == rules.NO_CLAIM:
        v.update(verdict=rules.NOT_CHECKABLE, reason="no-county-checkable-claim")
        return v

    dated = [r for r in deeds if _parse_date(r.get("sale_date"))]
    seller_client = [r for r in deeds if rules.client_match(r.get("seller_name"))]
    buyer_client = [r for r in deeds if rules.client_match(r.get("buyer_name"))]
    assessor_client = [r for r in assessor
                       if rules.client_match(r.get("owner_address_name"))
                       or rules.client_match(r.get("mail_address_name"))]
    client_present = bool(seller_client or buyer_client or assessor_client)

    if cls == rules.DISPOSED:
        d = _parse_date(crm.get("USER_date_disposed"))
        if d is not None:
            lo, hi = (d - timedelta(days=rules.WINDOW_DAYS),
                      d + timedelta(days=rules.WINDOW_DAYS))
            in_window = [r for r in dated
                         if lo <= _parse_date(r["sale_date"]) <= hi]
            iw_seller_client = [r for r in in_window
                                if rules.client_match(r.get("seller_name"))]
            iw_any_client = [r for r in in_window
                             if rules.client_match(r.get("seller_name"))
                             or rules.client_match(r.get("buyer_name"))]
            if iw_seller_client:
                v.update(verdict=rules.SUPPORTED, rule="D1",
                         citations=[_cite_deed(r, retrieved)
                                    for r in iw_seller_client])
            elif in_window and not iw_any_client and not client_present:
                cites = [_cite_deed(r, retrieved) for r in in_window]
                cites += [_cite_assessor(r, retrieved)
                          for r in _assessor_chain_summary(assessor)]
                v.update(verdict=rules.CONTRADICTED, rule="D3", citations=cites)
            elif not in_window and not client_present:
                v.update(verdict=rules.UNSUPPORTED_NO_RECORD, rule="D4",
                         citations=[_cite_absence(retrieved)])
            else:
                v.update(verdict=rules.AMBIGUOUS, rule="D5",
                         citations=[_cite_deed(r, retrieved)
                                    for r in in_window + seller_client
                                    + buyer_client]
                         + [_cite_assessor(r, retrieved)
                            for r in assessor_client])
        else:
            if seller_client:
                v.update(verdict=rules.AMBIGUOUS, rule="D-nodate",
                         citations=[_cite_deed(r, retrieved)
                                    for r in seller_client])
            elif client_present:
                v.update(verdict=rules.AMBIGUOUS, rule="D-nodate",
                         citations=[_cite_deed(r, retrieved) for r in buyer_client]
                         + [_cite_assessor(r, retrieved)
                            for r in assessor_client])
            else:
                v.update(verdict=rules.UNSUPPORTED_NO_RECORD, rule="D-nodate",
                         citations=[_cite_absence(retrieved)])

    else:  # HELD
        years = sorted({y for y in (_year(r.get("year")) for r in assessor)
                        if y is not None})
        max_year = years[-1] if years else None
        h1 = [r for r in assessor_client if _year(r.get("year")) == max_year]
        latest_client_deed = None
        client_deeds_dated = sorted(
            (r for r in seller_client + buyer_client
             if _parse_date(r.get("sale_date"))),
            key=lambda r: (_parse_date(r["sale_date"]), str(r.get("doc_no"))))
        if client_deeds_dated:
            latest_client_deed = client_deeds_dated[-1]
        undated_seller_client = [r for r in seller_client
                                 if not _parse_date(r.get("sale_date"))]
        if h1:
            v.update(verdict=rules.SUPPORTED, rule="H1",
                     citations=[_cite_assessor(r, retrieved) for r in h1])
        elif (buyer_client and not undated_seller_client
              and (latest_client_deed is None
                   or not rules.client_match(
                       latest_client_deed.get("seller_name")))):
            v.update(verdict=rules.SUPPORTED, rule="H2",
                     citations=[_cite_deed(r, retrieved) for r in buyer_client])
        elif (latest_client_deed is not None
              and rules.client_match(latest_client_deed.get("seller_name"))):
            v.update(verdict=rules.CONTRADICTED, rule="H3",
                     citations=[_cite_deed(latest_client_deed, retrieved)]
                     + [_cite_assessor(r, retrieved)
                        for r in _assessor_chain_summary(assessor)])
        elif not client_present:
            v.update(verdict=rules.UNSUPPORTED_NO_RECORD, rule="H4",
                     citations=[_cite_absence(retrieved)])
        else:
            v.update(verdict=rules.AMBIGUOUS, rule="H5",
                     citations=[_cite_deed(r, retrieved)
                                for r in seller_client + buyer_client]
                     + [_cite_assessor(r, retrieved) for r in assessor_client])

    # NEAR-MISS override (§4): unlisted land-bank-like strings force AMBIGUOUS
    nm = sorted({s for s in _party_strings(deeds, assessor) if rules.near_miss(s)})
    if nm:
        v["near_miss_strings"] = nm
        v["rule"] = f"{v['rule']}+NEAR-MISS"
        v["verdict"] = rules.AMBIGUOUS
    return v


def _assessor_chain_summary(assessor: list[dict]) -> list[dict]:
    """First and last assessor row per distinct owner name — a compact chain."""
    seen: dict[str, list[dict]] = {}
    for r in sorted(assessor, key=lambda r: (_year(r.get("year")) or 0,
                                             str(r.get("row_id")))):
        key = rules.normalize(r.get("owner_address_name") or "")
        seen.setdefault(key, []).append(r)
    out = []
    for key in sorted(seen):
        rows = seen[key]
        out.append(rows[0])
        if len(rows) > 1:
            out.append(rows[-1])
    return out


# --------------------------------------------------------------------------
# batch entry point
# --------------------------------------------------------------------------

def classify_all(snaps: dict) -> list[dict]:
    """Classify every CRM record. Deterministic order (sorted by USER_ppn)."""
    deeds_idx = _index_by_pin14(snaps["ccao_parcel_sales"]["records"])
    assr_idx = _index_by_pin14(snaps["cc_assessor"]["records"])
    tax_idx = _index_by_pin14(snaps["tax_agency"]["records"])
    scav_idx = _index_by_pin14(snaps["tax_agency_scavenger"]["records"])
    retrieved = snaps["ccao_parcel_sales"]["retrieval"]["retrieved_date"]
    out = []
    for crm in sorted(snaps["crm_inventory"]["records"],
                      key=lambda r: r["USER_ppn"]):
        p14 = pins.to14(crm["USER_ppn"]) if crm["cook_format"] else ""
        out.append(classify(
            crm, deeds_idx.get(p14, []), assr_idx.get(p14, []),
            tax_idx.get(p14, []), scav_idx.get(p14, []), retrieved))
    return out
