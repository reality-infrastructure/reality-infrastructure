"""Pure report emitters: verdict records -> CSV / JSON / markdown text.

No wall clock: every date shown comes from snapshot retrieval blocks or record
fields. All three emitters return strings; run_audit.py writes them.
"""
from __future__ import annotations

import csv
import io
import json

from audit import rules

BANNER = ("CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying "
          "information; prospect-facing derivatives go through the collateral "
          "anonymization process.")

CSV_FIELDS = ["pin", "status", "claim_class", "claim_date", "verdict", "reason",
              "rule", "citation_count", "first_citation", "near_miss_strings",
              "tax_sale_rows", "scavenger_rows"]


def _first_cite(v: dict) -> str:
    if not v["citations"]:
        return ""
    c = v["citations"][0]
    return (f"{c['dataset_id']} {c['record'] or ''} {c['date'] or ''} "
            f"{c['parties'] or ''}").strip()


def to_csv(verdicts: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    for v in verdicts:
        w.writerow({
            "pin": v["pin"], "status": v["status"],
            "claim_class": v["claim_class"], "claim_date": v["claim_date"] or "",
            "verdict": v["verdict"], "reason": v["reason"] or "",
            "rule": v["rule"] or "", "citation_count": len(v["citations"]),
            "first_citation": _first_cite(v),
            "near_miss_strings": "; ".join(v["near_miss_strings"]),
            "tax_sale_rows": v["tax_sale_rows"],
            "scavenger_rows": v["scavenger_rows"],
        })
    return buf.getvalue()


def to_json(verdicts: list[dict], snaps: dict) -> str:
    doc = {
        "banner": BANNER,
        "preregistration": "audit/PREREGISTRATION.md",
        "retrieval": {sid: snaps[sid]["retrieval"]
                      for sid in sorted(snaps) if "retrieval" in snaps[sid]},
        "coverage_caveat": rules.COVERAGE_CAVEAT,
        "verdicts": verdicts,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _tally(verdicts: list[dict]) -> dict[str, int]:
    t = {v: 0 for v in rules.VERDICTS}
    for v in verdicts:
        t[v["verdict"]] += 1
    return t


def to_markdown(verdicts: list[dict], snaps: dict) -> str:
    crm_ret = snaps["crm_inventory"]["retrieval"]
    county_ret = snaps["ccao_parcel_sales"]["retrieval"]
    t = _tally(verdicts)
    eligible = [v for v in verdicts if v["claim_class"] in ("DISPOSED", "HELD")
                and v["verdict"] != rules.NOT_CHECKABLE]
    lines = []
    a = lines.append
    a(f"> **{BANNER}**")
    a("")
    a("# CRM Reality Audit — full-inventory verification against county records")
    a("")
    a(f"CRM inventory snapshot: {crm_ret['retrieved_date']} "
      f"(source sha256 `{crm_ret['source_sha256'][:16]}…`, "
      f"{len(snaps['crm_inventory']['records'])} parcels). County records "
      f"retrieved {county_ret['retrieved_date']} from the four datasets in "
      f"`audit/MANIFEST.md`. Method pre-registered in `audit/PREREGISTRATION.md` "
      f"before any county data was fetched; rules were not altered after data "
      f"was seen.")
    a("")
    a(f"> {rules.COVERAGE_CAVEAT}")
    a("")
    a("## Verdicts")
    a("")
    a("| Verdict | Count |")
    a("|---|---|")
    for name in rules.VERDICTS:
        a(f"| {name} | {t[name]} |")
    a(f"| **Total parcels** | **{len(verdicts)}** |")
    a("")
    a(f"Of {len(verdicts)} parcels, {len(eligible)} carry a county-checkable claim "
      f"(status class DISPOSED or HELD, Cook-format PIN, Cook county label). "
      f"The rest are NOT_CHECKABLE for the reasons broken out below.")
    a("")

    contradicted = [v for v in verdicts if v["verdict"] == rules.CONTRADICTED]
    a(f"## Contradicted claims ({len(contradicted)})")
    a("")
    a("Every entry below means: **the recorded county documents conflict with the "
      "CRM claim as stated**. It does not characterize any person or entity; "
      "records disagree, nothing more. Each row cites the specific records.")
    a("")
    for v in contradicted:
        a(f"### {v['pin']} — CRM: {v['status']}"
          + (f" ({v['claim_date']})" if v["claim_date"] else "") + f" · rule {v['rule']}")
        for c in v["citations"]:
            a(f"- `{c['dataset_id']}` record `{c['record']}` "
              f"[{c['date_field']}={c['date']}] {c['parties']} "
              f"(retrieved {c['retrieved']})")
        a("")

    ambiguous = [v for v in verdicts if v["verdict"] == rules.AMBIGUOUS]
    nm = [v for v in ambiguous if v["near_miss_strings"]]
    a(f"## Ambiguous ({len(ambiguous)}, of which {len(nm)} from unattested "
      f"land-bank-like name variants)")
    a("")
    a("Records exist but neither support nor contradict under the pre-registered "
      "rules — or a party string resembles the client but matches no attested "
      "alias (never silently matched; listed verbatim for attestation):")
    a("")
    variants = sorted({s for v in nm for s in v["near_miss_strings"]})
    for s in variants:
        a(f"- `{s}` ({sum(1 for v in nm if s in v['near_miss_strings'])} parcels)")
    a("")

    unsupported = [v for v in verdicts
                   if v["verdict"] == rules.UNSUPPORTED_NO_RECORD]
    a(f"## Unsupported — no record ({len(unsupported)})")
    a("")
    a(f"For these parcels, {rules.ABSENCE_FRAMING} bearing on the CRM claim. "
      f"See the coverage caveat above: this is a statement about the queried "
      f"datasets, not about the world.")
    a("")

    ncheck = [v for v in verdicts if v["verdict"] == rules.NOT_CHECKABLE]
    a(f"## Not checkable ({len(ncheck)})")
    a("")
    a("| Reason | Count |")
    a("|---|---|")
    for reason in rules.NOT_CHECKABLE_REASONS:
        n = sum(1 for v in ncheck if v["reason"] == reason)
        a(f"| {reason} | {n} |")
    a("")
    a("`status-semantics-unresolved` covers CRM statuses whose county-checkable "
      "meaning we declined to guess (e.g. \"Deed Recorded\" may be a tax deed TO "
      "the client, i.e. an acquisition, not a sale). Confirming their intended "
      "meaning reclassifies them by amendment and re-run.")
    a("")
    a("## Escalation")
    a("")
    a("Any parcel above can be escalated to a full per-parcel title-belief dossier "
      "(deed chain, belief masses, replay attestation) — the instrument that "
      "verified the first contradiction on this inventory.")
    a("")
    return "\n".join(lines)
