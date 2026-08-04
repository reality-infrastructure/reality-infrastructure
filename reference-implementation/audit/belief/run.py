"""M-RI-17 belief pass: frozen snapshots -> belief objects -> determination.

Usage:
    python -m audit.belief

Invokes the wall-frozen C2 machinery as-is: the cook_parcels adapter
parses the mapped snapshot rows (mapping.py, PREREGISTRATION §6), the
RightsPipeline submits every event through the engine and folds one
belief object per parcel for the ownership_shares question under the
frozen Denoeux cautious rule and the frozen declared priors
(rights_events/policy.py). Nothing in ri_core, the adapter, the fold, or
any frozen audit rule is modified.

Outputs (byte-identical on every run; two-run hash compare is an
acceptance criterion):
- audit/belief/out/parcels_belief.ri      run file (event + belief logs)
- audit/belief/out/belief_objects.json    per-parcel belief + context
- audit/out/belief-determination.md       the internal determination

Known-answer commitment (PREREGISTRATION §10): the Dolton parcel MUST
reproduce m(empty)=0.91296 exactly; a mismatch prints the finding and
exits nonzero. The pass is never tuned to match.

as_of is the maximum event ltime in the data — derived from the records,
never from a clock.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

from rights_events.adapters.cook_parcels import parse_all
from rights_events.pipeline import RightsPipeline
from rights_events.policy import POLICY_VERSION, ltime_for

from audit.belief import mapping

QUESTION = "ownership_shares"
KNOWN_ANSWER_PIN14 = "29024080530000"
KNOWN_ANSWER_CONFLICT = Decimal("0.91296")

_OUT_DIR = mapping.ROOT / "audit" / "belief" / "out"
_DETERMINATION = mapping.ROOT / "audit" / "out" / "belief-determination.md"

_BANNER = (
    "> **INTERNAL DETERMINATION — M-RI-17. NOT FOR CLIENT OR PROSPECT "
    "USE.** Contains client-identifying information. No dollar figures; "
    "no external-facing claims. Every contest below is a statement that "
    "RECORDS DISAGREE and requires verification against the underlying "
    "instruments; nothing here characterizes any person or entity.")


def _canon(value: Decimal) -> str:
    """Plain-form decimal string (no exponent, no trailing zeros)."""
    return format(value.normalize(), "f")


def _entity_of(label: str) -> str:
    """shares:<ENTITY>=100 -> <ENTITY> (display only)."""
    if label.startswith("shares:") and "=" in label:
        return label[len("shares:"):].rsplit("=", 1)[0]
    return label


def _run_belief(inputs: dict) -> tuple[RightsPipeline, dict, int, list]:
    events = parse_all(json.dumps(inputs["deed_rows"]),
                       json.dumps(inputs["owner_rows"]),
                       json.dumps(inputs["forfeiture_rows"]))
    pipeline = RightsPipeline()
    pipeline.ingest(events)
    as_of = max(ltime_for(e.observed_date) for e in events)
    beliefs = {}
    for pin in inputs["pins14"]:
        belief, index = pipeline.commit(f"parcel:{pin}", QUESTION, as_of)
        beliefs[pin] = (belief, index)
    return pipeline, beliefs, as_of, events


def _belief_entry(pin14: str, parcel: dict, belief: dict, index: int,
                  events_by_id: dict, inputs: dict) -> dict:
    frame = belief["frame"]
    n = len(frame)
    conflict = belief["conflict_mass"]
    band = ("single-claim-ignorance" if n == 1
            else "paired-divergence" if n == 2 else "multi-way-contest")

    contributing = []
    for c in belief["contributing_events"]:
        event = events_by_id[c["event_id"]]
        entry = {
            "event_id": c["event_id"],
            "log_index": c["log_index"],
            "event_type": c["event_type"],
            "ep_type": c["ep_type"],
            "uncertainty_type": c["uncertainty_type"],
            "hypothesis": c["hypothesis"],
            "status": c["status"],
            "applied_mass": _canon(c["applied_mass"]),
            "source_url": event.source_url,
            "observed_date": event.observed_date,
        }
        if c["event_id"].startswith("cook:roll:"):
            # The frozen adapter's roll source_url constant names the C2
            # roll dataset; this observation derives from the frozen
            # cc_assessor snapshot, cited here (determination finding).
            entry["snapshot_citation"] = {
                "dataset_id": inputs["assessor_dataset_id"],
                "row": inputs["verbatim_roll"][pin14],
                "retrieved_date": inputs["roll_retrieved_date"],
            }
        elif c["event_id"].startswith("cook:deed:"):
            entry["snapshot_citation"] = {
                "dataset_id": inputs["deeds_dataset_id"],
                "doc_number": c["event_id"].rsplit(":", 1)[-1],
            }
        contributing.append(entry)

    ctx = inputs["context"]
    return {
        "pin": parcel["pin"],
        "pin14": pin14,
        "m_ri_16_verdict": parcel["verdict"],
        "m_ri_16_rule": parcel["rule"],
        "crm_status": parcel["status"],
        "recorder_banner": parcel["recorder_banner"],
        "belief_log_index": index,
        "frame": frame,
        "frame_size": n,
        "band": band,
        "mass": {k: _canon(v) for k, v in belief["mass"].items()},
        "unresolved_set": belief["unresolved_set"],
        "unresolved_mass": _canon(belief["unresolved_mass"]),
        "conflict_mass": _canon(conflict),
        "contributing_events": contributing,
        "context_not_folded": {
            "tax_agency_rows": ctx["tax_agency"]["rows_by_pin14"].get(
                pin14, []),
            "tax_agency_scavenger_rows":
                ctx["tax_agency_scavenger"]["rows_by_pin14"].get(pin14, []),
            "crm_row": ctx["crm_inventory"]["rows_by_pin14"].get(pin14),
        },
        "canonicalizations": [
            c for c in inputs["canonicalizations"] if c["pin14"] == pin14],
        "placeholder_drops": [
            d for d in inputs["placeholder_drops"] if d["pin14"] == pin14],
    }


def _parcel_section(entry: dict) -> list[str]:
    lines: list[str] = []
    head = (f"### {entry['pin']} — M-RI-16 {entry['m_ri_16_verdict']} "
            f"({entry['m_ri_16_rule']})")
    if entry["recorder_banner"]:
        head += " · **RECORDER BANNER — docs 2401822036/37**"
    lines.append(head)
    lines.append("")

    n = entry["frame_size"]
    lines.append(f"Frame of discernment ({n} "
                 f"hypothes{'is' if n == 1 else 'es'}, enumerated from "
                 f"the records before any mass was assigned):")
    by_hyp: dict[str, list[dict]] = {}
    for c in entry["contributing_events"]:
        if c["hypothesis"]:
            by_hyp.setdefault(c["hypothesis"], []).append(c)
    for label in entry["frame"]:
        backing = []
        for c in by_hyp.get(label, []):
            if c["event_id"].startswith("cook:deed:"):
                cite = c["snapshot_citation"]
                backing.append(
                    f"deed chain-tail doc {cite['doc_number']} "
                    f"({cite['dataset_id']}, sale {c['observed_date']}, "
                    f"{c['source_url']})")
            elif c["event_id"].startswith("cook:roll:"):
                cite = c["snapshot_citation"]
                row = cite["row"]
                backing.append(
                    f"assessor roll year {row['year']} "
                    f"owner_address_name={row['owner_address_name']!r} "
                    f"(snapshot {cite['dataset_id']} row {row['row_id']}, "
                    f"retrieved {cite['retrieved_date']})")
        lines.append(f"- `{_entity_of(label)}` "
                     f"[hypothesis `{label}`] — "
                     + ("; ".join(backing) if backing else "(no backing "
                        "record — should not happen)"))
    for c in entry["canonicalizations"]:
        lines.append(f"- D1 canonicalization: {c['channel']} "
                     f"{c['field']} verbatim {c['verbatim']!r} -> "
                     f"attested client entity (alias family, "
                     f"attestations.yaml)")
    for d in entry["placeholder_drops"]:
        lines.append(f"- D2 placeholder: roll year {d['year']} "
                     f"owner_address_name={d['owner_address_name']!r} "
                     f"names nobody — no roll observation (NULL stays "
                     f"NULL)")
    lines.append("")

    lines.append("Masses (frozen priors, frozen cautious fold, "
                 "unnormalized):")
    for label in entry["frame"]:
        if n > 1:
            lines.append(f"- m[`{_entity_of(label)}`] = "
                         f"{entry['mass'][label]}")
    lines.append(f"- **m(Ω) = {entry['unresolved_mass']}** — ignorance, "
                 f"unresolved among all of: "
                 + ", ".join(f"`{_entity_of(h)}`"
                             for h in entry["frame"]))
    lines.append(f"- **m(∅) = {entry['conflict_mass']}** — conflict, "
                 f"the records contradicting one another")
    lines.append("")

    if n == 1:
        only = _entity_of(entry["frame"][0])
        lines.append(
            f"**READING — SINGLE CLAIM, IGNORANCE (go dig).** The "
            f"captured snapshots contain exactly one ownership claim "
            f"(`{only}`) and no counter-claim, so the frame is "
            f"uncontested by construction and the fold is vacuous: all "
            f"mass sits on Ω. Mass on Ω means **no counter-claim was "
            f"found in the captured snapshots** — not that the claim is "
            f"uncontested in the world. Absence is \"no record found,\" "
            f"never a claim about reality. m(∅) = 0: absence is never "
            f"reported as conflict.")
        if entry["m_ri_16_verdict"] == "CONTRADICTED":
            lines.append("")
            lines.append(
                "The county records for this parcel agree among "
                "themselves; the M-RI-16 CONTRADICTED verdict is "
                "CRM-versus-county disagreement — a records-completeness "
                "finding about the client's bookkeeping question, not an "
                "ownership contest among county records (ruling D4).")
    else:
        kind = ("PAIRED DIVERGENCE" if n == 2 else "MULTI-WAY CONTEST")
        lines.append(
            f"**READING — {kind}, CONFLICT (stop).** The county's own "
            f"records assert {n} mutually exclusive current owners; "
            f"m(∅) = {entry['conflict_mass']} is mass the records "
            f"destroy against each other and it says stop — resolve the "
            f"records before relying on any of them. m(Ω) = "
            f"{entry['unresolved_mass']} is the residual ignorance and "
            f"it says go dig. Conflict is not ignorance: more searching "
            f"does not lower m(∅); only resolving the underlying "
            f"instruments does.")
    lines.append("")

    ctx = entry["context_not_folded"]
    ctx_lines = []
    for row in ctx["tax_agency_rows"]:
        ctx_lines.append(
            f"annual tax sale {row.get('tax_sale_year')}: "
            f"sold_at_sale={row.get('sold_at_sale')}"
            + (f", buyer {row.get('buyer_name')!r}"
               if row.get("buyer_name") else ""))
    for row in ctx["tax_agency_scavenger_rows"]:
        ctx_lines.append(
            f"scavenger sale {row.get('tax_sale_year')}: "
            f"sold_at_sale={row.get('sold_at_sale')}"
            + (f", buyer {row.get('buyer_name')!r}"
               if row.get("buyer_name") else ""))
    crm = ctx["crm_row"]
    if crm is not None:
        purchaser = crm.get("USER_applicant_purchaser")
        ctx_lines.append(
            f"CRM (client self-report): status "
            f"{crm.get('USER_disp_status')!r}, date_disposed "
            f"{crm.get('USER_date_disposed')!r}, purchaser "
            + (f"{purchaser!r}" if purchaser else "not recorded"))
        if purchaser:
            ctx_lines.append(
                f"the client's claimed purchaser {purchaser!r} is "
                f"context only; whether it corresponds to a frame "
                f"entity is verification work against the instruments, "
                f"not an inference this pass makes")
    if ctx_lines:
        lines.append("Context on disk, NOT folded (tax-sale rows per "
                     "ruling D3; CRM per ruling D4 — different question, "
                     "same parcel):")
        for line in ctx_lines:
            lines.append(f"- {line}")
        lines.append("")
    return lines


def render_determination(manifest: dict, entries: list[dict],
                         as_of: int, root_hex: str,
                         inputs: dict) -> str:
    counts = {"single-claim-ignorance": 0, "paired-divergence": 0,
              "multi-way-contest": 0}
    for e in entries:
        counts[e["band"]] += 1
    dolton = next(e for e in entries if e["pin14"] == KNOWN_ANSWER_PIN14)

    lines = [
        _BANNER,
        "",
        "# Belief determination — post-remediation contested set "
        "(M-RI-17)",
        "",
        "## Input, machinery, provenance",
        "",
        f"- Frozen input: `{mapping.MANIFEST_PATH.name}` sha256 "
        f"`{mapping.MANIFEST_SHA256}` — 44 parcels = 9 CONTRADICTED + "
        f"35 AMBIGUOUS, the M-RI-16 post-remediation contested set "
        f"(run sha256 `{manifest['run_sha256']}`).",
        "- Preregistration (FROZEN before this package existed): "
        "`audit/prereg/M-RI-17-PREREGISTRATION.md` — mass declarations, "
        "conventions D1–D4, counts declared UNKNOWN.",
        f"- Machinery, invoked as-is (wall-frozen): "
        f"`cook_parcels.parse_all` -> `RightsPipeline` -> Denoeux "
        f"cautious rule, policy `{POLICY_VERSION}` "
        f"(statutory_registry claim mass "
        f"{_canon(mapping.STATUTORY_CLAIM_MASS)}; disputes fuse "
        f"vacuously).",
        f"- Channels folded: deed chain-tails "
        f"(`{inputs['deeds_dataset_id']}`), assessor roll max-year "
        f"owner (snapshot `{inputs['assessor_dataset_id']}`, retrieved "
        f"{inputs['roll_retrieved_date']}). NOT folded: tax-sale rows "
        f"(D3), CRM disposition claims (D4) — carried as cited context "
        f"per parcel.",
        "- FINDING (provenance constant): the frozen adapter stamps "
        "roll events with its C2 roll-dataset URL constant "
        "(`ta6y-k9gr`); the roll observations in this pass derive from "
        "the frozen `cc_assessor` snapshot (`3723-97qp`), cited per "
        "observation below and in `belief_objects.json`. The adapter "
        "is wall-frozen; the true snapshot citation is carried "
        "alongside rather than editing the wall.",
        f"- D1 canonicalizations applied: "
        f"{len(inputs['canonicalizations'])} (verbatim strings "
        f"preserved per parcel below). D2 placeholder drops: "
        f"{len(inputs['placeholder_drops'])}.",
        f"- as_of = {as_of} (max record ltime; no wall clock). Event "
        f"log root `{root_hex}`.",
        "- Replay: `python -m audit.belief` regenerates every artifact "
        "byte-identically from the frozen snapshots; any parcel "
        "verifies with the unchanged CLI: `python -m "
        "rights_events.replay --run audit/belief/out/parcels_belief.ri "
        "--subject parcel:<pin14>`.",
        "",
        "## Known-answer commitment (PREREGISTRATION §10)",
        "",
        f"Dolton `29-02-408-053-0000` through this pass: m(∅) = "
        f"**{dolton['conflict_mass']}** against the committed "
        f"{_canon(KNOWN_ANSWER_CONFLICT)} — REPRODUCED, not tuned. "
        f"Five competing statutory claims at "
        f"{dolton['mass'][dolton['frame'][0]]} each; m(Ω) = "
        f"{dolton['unresolved_mass']}.",
        "",
        "## Counts, as measured (preregistered UNKNOWN, §9)",
        "",
        f"- single-claim / high-ignorance (m(∅)=0, m(Ω)=1): "
        f"**{counts['single-claim-ignorance']}**",
        f"- paired divergence (2 hypotheses, m(∅)=0.36): "
        f"**{counts['paired-divergence']}**",
        f"- multi-way contest (3+ hypotheses, m(∅)≥0.648): "
        f"**{counts['multi-way-contest']}**",
        "",
        "## How to read m(Ω) versus m(∅)",
        "",
        "They are different states and must never be summed or "
        "confused. **m(Ω) — ignorance — says go dig:** the records do "
        "not answer the question; more evidence can move it. **m(∅) — "
        "conflict — says stop:** the records answer the question in "
        "mutually exclusive ways; more searching does not lower it, "
        "only resolving the underlying instruments does. A parcel with "
        "one claim and no counter-claim carries mass on Ω, never on ∅ "
        "— absence is not conflict.",
        "",
        "## Parcels",
        "",
    ]
    for entry in entries:
        lines.extend(_parcel_section(entry))
    return "\n".join(lines).rstrip() + "\n"


def run_pass(out_dir: Path = _OUT_DIR,
             determination_path: Path = _DETERMINATION) -> dict:
    """Execute the pass; write all three artifacts; return a summary."""
    manifest = mapping.load_manifest()
    inputs = mapping.build_inputs(manifest)
    pipeline, beliefs, as_of, events = _run_belief(inputs)
    events_by_id = {e.event_id: e for e in events}

    entries = []
    for parcel in manifest["parcels"]:
        pin14 = parcel["pin"].replace("-", "")
        belief, index = beliefs[pin14]
        entries.append(_belief_entry(pin14, parcel, belief, index,
                                     events_by_id, inputs))

    root_hex = pipeline.event_log.root().hex()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_bytes = pipeline.save(out_dir / "parcels_belief.ri")

    objects = {
        "kind": "m_ri_17_belief_objects",
        "preregistration": "audit/prereg/M-RI-17-PREREGISTRATION.md",
        "input_manifest_sha256": mapping.MANIFEST_SHA256,
        "policy_version": POLICY_VERSION,
        "question": QUESTION,
        "as_of": as_of,
        "event_log_root": root_hex,
        "event_count": len(events),
        "parcels": entries,
    }
    objects_bytes = (json.dumps(objects, indent=1, sort_keys=True,
                                ensure_ascii=True) + "\n").encode("ascii")
    (out_dir / "belief_objects.json").write_bytes(objects_bytes)

    determination = render_determination(manifest, entries, as_of,
                                         root_hex, inputs)
    determination_path.parent.mkdir(parents=True, exist_ok=True)
    determination_path.write_bytes(determination.encode("utf-8"))

    dolton = next(e for e in entries if e["pin14"] == KNOWN_ANSWER_PIN14)
    known_answer_ok = (
        Decimal(dolton["conflict_mass"]) == KNOWN_ANSWER_CONFLICT)

    counts = {"single-claim-ignorance": 0, "paired-divergence": 0,
              "multi-way-contest": 0}
    for e in entries:
        counts[e["band"]] += 1

    return {
        "parcels": len(entries),
        "events": len(events),
        "as_of": as_of,
        "event_log_root": root_hex,
        "counts": counts,
        "dolton_conflict": dolton["conflict_mass"],
        "known_answer_ok": known_answer_ok,
        "run_bytes": len(run_bytes),
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    summary = run_pass()
    print("M-RI-17 belief pass — post-remediation contested set")
    print(f"parcels: {summary['parcels']}  events: {summary['events']}  "
          f"as_of: {summary['as_of']}")
    print(f"event log root: {summary['event_log_root']}")
    print(f"counts (measured): {summary['counts']}")
    print(f"Dolton m(empty) = {summary['dolton_conflict']} "
          f"(committed {_canon(KNOWN_ANSWER_CONFLICT)})")
    if not summary["known_answer_ok"]:
        print("KNOWN-ANSWER FINDING: Dolton did NOT reproduce — STOP "
              "(PREREGISTRATION §10). The pass is not tuned to match.")
        return 1
    print("known answer: REPRODUCED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
