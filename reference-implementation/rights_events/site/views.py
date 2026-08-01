"""View renderers: provenance explorer (View 1), rights-state (View 2).

Both domains render through the same functions — the sameness is the
message (Contract 3, View 1). All data comes from loaded run
artifacts: events and beliefs are decoded from log entries; inclusion
proofs are read off the loaded Merkle logs. Beliefs are never
recomputed. Masses render in canonical plain form (trailing zeros
trimmed; the underlying artifact bytes stay exact and downloadable).

R1 carries through: names verbatim as recorded, no mailing addresses
anywhere in the artifacts, and every contest is presented as records
disagreeing — never as a characterization of a person or entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ri_core.serialization import decode

from rights_events.pipeline import RightsPipeline
from rights_events.site.html import esc, link_https, page

_PIN_RE = re.compile(r"^\d{14}$")

RECORDS_DISAGREE = (
    "Competing entries on this page mean that the cited records "
    "disagree; resolution requires verification against the "
    "underlying instruments. Nothing here characterizes any person "
    "or entity.")


@dataclass(frozen=True)
class RunData:
    slug: str            # filename stem: "song-x" / "parcels"
    label: str           # display label
    artifact: str        # evidence filename
    pipeline: RightsPipeline
    events: list         # [(log_index, observation_dict, event_dict)]
    beliefs: list        # [(belief_log_index, belief_dict)]


def load_run(slug: str, label: str, artifact_path: Path) -> RunData:
    pipeline = RightsPipeline.load(artifact_path)
    events = []
    for idx in range(len(pipeline.event_log)):
        obs = decode(pipeline.event_log.entry(idx))
        events.append((idx, obs, obs["payload"]["event"]))
    beliefs = []
    for idx in range(len(pipeline.belief_log)):
        beliefs.append((idx, decode(pipeline.belief_log.entry(idx))))
    return RunData(slug=slug, label=label, artifact=artifact_path.name,
                   pipeline=pipeline, events=events, beliefs=beliefs)


def _mass(value: Decimal) -> str:
    return format(value.normalize(), "f")


def subject_page_name(subject: str) -> str:
    """Stable, citable filename per subject."""
    if subject == "work:song-x":
        return "song-x.html"
    if subject.startswith("parcel:"):
        pin = subject.removeprefix("parcel:")
        if not _PIN_RE.match(pin):
            raise ValueError(f"Unexpected subject id: {subject!r}")
        return f"parcel-{pin}.html"
    raise ValueError(f"Unexpected subject id: {subject!r}")


# ---------------------------------------------------------------------------
# View 1 — provenance explorer
# ---------------------------------------------------------------------------

def render_provenance(run: RunData) -> str:
    root_hex = run.pipeline.event_log.root().hex()
    size = len(run.pipeline.event_log)
    rows = []
    for idx, obs, event in run.events:
        proof = run.pipeline.event_log.inclusion_proof(idx)
        path_items = "".join(
            f"<li><code>{esc(h.hex())}</code></li>"
            for h in proof.hashes)
        detail = (
            "<details><summary>inclusion proof</summary><dl>"
            f"<dt>leaf index</dt><dd>{proof.index} of tree size "
            f"{proof.tree_size}</dd>"
            f"<dt>leaf hash</dt><dd><code>{esc(proof.leaf_hash.hex())}"
            "</code></dd>"
            f"<dt>audit path</dt><dd><ol>{path_items}</ol></dd>"
            f"<dt>root</dt><dd><code>{esc(proof.root_hash.hex())}"
            "</code></dd></dl></details>")
        rows.append(
            f'      <tr id="e{idx}">'
            f"<td>{idx}</td>"
            f"<td>{esc(event['event_id'])}</td>"
            f"<td>{esc(event['event_type'])}</td>"
            f"<td>{esc(', '.join(event['subject_ids']))}</td>"
            f"<td>{esc(event['claimant'])}</td>"
            f"<td>{esc(event['ep_type'])}</td>"
            f"<td>{esc(event['observed_date'])}</td>"
            f"<td>{link_https(event['source_url'])}</td>"
            f"<td>{detail}</td>"
            "</tr>\n")
    body = (
        f"  <p>{esc(run.label)}: {size} events in an append-only "
        f"Merkle log. Root <code>{esc(root_hex)}</code>. Every row is "
        "a signed, logged event; expand a row's proof to see the "
        "RFC 9162 inclusion path binding it to the root. The same "
        "table renders every domain this layer carries.</p>\n"
        "  <table>\n"
        f"    <caption>Event log — {esc(run.label)}</caption>\n"
        "    <thead><tr>"
        '<th scope="col">#</th><th scope="col">event id</th>'
        '<th scope="col">type</th><th scope="col">subject</th>'
        '<th scope="col">claimant</th><th scope="col">EP type</th>'
        '<th scope="col">observed</th><th scope="col">source</th>'
        '<th scope="col">proof</th>'
        "</tr></thead>\n"
        "    <tbody>\n" + "".join(rows) + "    </tbody>\n"
        "  </table>\n")
    return page(f"Provenance explorer — {run.label}", body,
                "../style.css",
                crumbs='<a href="../index.html">Index</a> / Provenance')


# ---------------------------------------------------------------------------
# View 2 — rights-state
# ---------------------------------------------------------------------------

def _belief_section(run: RunData, belief: dict) -> str:
    frame = belief["frame"]
    omega_key = belief["unresolved_set"]
    singleton_rows = "".join(
        f'      <tr><td>{esc(hyp)}</td>'
        f'<td class="num">{esc(_mass(belief["mass"][hyp]))}</td>'
        f"<td>competing claim</td></tr>\n"
        for hyp in frame)
    other_rows = "".join(
        f"      <tr><td><code>{esc(key)}</code></td>"
        f'<td class="num">{esc(_mass(value))}</td>'
        f"<td>subset</td></tr>\n"
        for key, value in sorted(belief["mass"].items())
        if key not in ("", omega_key) and key not in frame
        and value != 0)
    contributing = "".join(
        "      <tr>"
        f"<td>{esc(c['event_id'])}</td>"
        f"<td>{esc(c['event_type'])}</td>"
        f"<td>{esc(c['ep_type'])}</td>"
        f"<td>{esc(', '.join(c['uncertainty_type']))}</td>"
        f"<td>{esc(c['status'])}</td>"
        f'<td class="num">{esc(_mass(c["applied_mass"]))}</td>'
        "</tr>\n"
        for c in belief["contributing_events"])
    return (
        f"  <h2>Belief at as_of {belief['as_of']}</h2>\n"
        f"  <p>Question: <code>{esc(belief['question'])}</code>. "
        f"Frame of {len(frame)} hypotheses. Policy "
        f"<code>{esc(belief['policy_version'])}</code>. Event log "
        f"root <code>{esc(belief['event_log_root'].hex())}</code> at "
        f"size {belief['event_log_size']}.</p>\n"
        '  <table class="mass-table">\n'
        "    <caption>Mass assignments</caption>\n"
        '    <thead><tr><th scope="col">set</th>'
        '<th scope="col">mass</th><th scope="col">reading</th>'
        "</tr></thead>\n"
        "    <tbody>\n"
        + singleton_rows + other_rows +
        "      <tr><td>conflict (empty set)</td>"
        f'<td class="num">{esc(_mass(belief["conflict_mass"]))}</td>'
        "<td>evidence that contradicts itself, kept visible</td>"
        "</tr>\n"
        "      <tr><td>unresolved (ignorance set Omega)</td>"
        f'<td class="num">{esc(_mass(belief["unresolved_mass"]))}</td>'
        "<td>mass no evidence discriminates</td></tr>\n"
        "    </tbody>\n"
        "  </table>\n"
        "  <table>\n"
        "    <caption>Contributing events (each provable in the "
        "event log)</caption>\n"
        '    <thead><tr><th scope="col">event</th>'
        '<th scope="col">type</th><th scope="col">EP type</th>'
        '<th scope="col">uncertainty type</th>'
        '<th scope="col">status</th>'
        '<th scope="col">applied mass</th></tr></thead>\n'
        "    <tbody>\n" + contributing + "    </tbody>\n"
        "  </table>\n")


def is_contested(belief: dict) -> bool:
    positive = [h for h in belief["frame"] if belief["mass"][h] > 0]
    return len(positive) >= 2


def render_subject(run: RunData, subject: str) -> str:
    beliefs = [b for _i, b in run.beliefs if b["subject"] == subject]
    contested = any(is_contested(b) for b in beliefs)
    note = (f"  <p class=\"contested\">{esc(RECORDS_DISAGREE)}</p>\n"
            if contested else "")
    sections = "".join(_belief_section(run, b) for b in beliefs)
    prov = f"../provenance/{esc(run.slug)}.html"
    body = (
        note + sections +
        f'  <p><a href="{prov}">Event log for this run</a> · '
        f'<a href="../evidence/index.html">Verify this offline</a>'
        "</p>\n")
    return page(f"Rights-state — {subject}", body,
                "../style.css",
                crumbs='<a href="../index.html">Index</a> / '
                       '<a href="index.html">Rights-state</a> / '
                       f"{esc(subject)}")


def render_rights_state_index(runs: list[RunData]) -> str:
    items = []
    for run in runs:
        subjects = sorted({b["subject"] for _i, b in run.beliefs})
        for subject in subjects:
            beliefs = [b for _i, b in run.beliefs
                       if b["subject"] == subject]
            tag = (" — contested (records disagree)"
                   if any(is_contested(b) for b in beliefs) else "")
            items.append(
                f'    <li><a href="{esc(subject_page_name(subject))}">'
                f"{esc(subject)}</a> [{esc(run.label)}]{esc(tag)}</li>\n")
    body = (
        "  <p>One page per subject: the belief object as stored — "
        "competing claims, explicit conflict mass, explicit "
        "unresolved mass, and the contributing events with their "
        "epistemic types. Contested means at least two hypotheses "
        "carry positive mass: the cited records disagree.</p>\n"
        "  <ul>\n" + "".join(items) + "  </ul>\n")
    return page("Rights-state — subjects", body, "../style.css",
                crumbs='<a href="../index.html">Index</a> / Rights-state')
