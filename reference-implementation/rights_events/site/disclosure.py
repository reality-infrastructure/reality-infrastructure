"""View 4 — derived disclosure (Contract 3, plan-gate rulings (i)+(ii)).

Two panels. Panel A: a document in the structure of the European
Commission AI Office Template for the Public Summary of Training
Content (adopted 24 July 2025) — three sections: General information,
List of data sources, Relevant data processing aspects — where every
line is generated from the corpus run artifact and carries its event
references. Panel B: the same facts as drafted prose with no
references. Caption, verbatim: "One of these can be replayed."

The demonstration label (operator-approved wording, caption-weight
styling) and the corpus-composition statement render on the page
itself, not only in a manifest.
"""

from __future__ import annotations

from rights_events.site.html import esc, link_https, page
from rights_events.site.views import RunData, _mass

CAPTION = "One of these can be replayed."

LABEL = (
    "DEMONSTRATION ONLY. Generated from labeled fixture data in a "
    "public research repository. The scope includes a SYNTHETIC "
    "music-rights fixture and real captured reservation signals. This "
    "is not a regulatory filing; no provider has submitted it to any "
    "authority; no model was trained on this corpus. Panel A is "
    "derived mechanically from logged events — every line carries its "
    "event references. Panel B states the same facts as drafted prose "
    "with none.")

SOURCE_LINE = (
    "Structure follows the European Commission AI Office Template for "
    "the Public Summary of Training Content (adopted 24 July 2025) as "
    "documented in public sources; this page is not the official "
    "form.")

COMPOSITION = (
    "Corpus composition: the SYNTHETIC Song X split-conflict fixture "
    "(no real work, writer, or society) plus REAL captured "
    "reservation signals — the www.nytimes.com robots.txt capture of "
    "2026-08-01 and the W3C TDMRep Final Community Group Report "
    "example. Fixture provenance is recorded in the repository's "
    "fixture manifests.")


def _refs(event_ids: list[str]) -> str:
    ids = ", ".join(f"<code>{esc(e)}</code>" for e in sorted(event_ids))
    return f' <span class="refs">[events: {ids}]</span>'


def _line(text: str, event_ids: list[str]) -> str:
    return f"      <li>{esc(text)}{_refs(event_ids)}</li>\n"


def render_disclosure(corpus: RunData) -> str:
    events = [(idx, ev) for idx, _obs, ev in corpus.events]
    root_hex = corpus.pipeline.event_log.root().hex()
    total = len(events)

    by_type: dict[str, list[dict]] = {}
    by_ep: dict[str, list[dict]] = {}
    for _idx, ev in events:
        by_type.setdefault(ev["event_type"], []).append(ev)
        by_ep.setdefault(ev["ep_type"], []).append(ev)

    opt_outs = by_type.get("opt_out", [])
    revocations = by_type.get("revocation", [])
    hosts = sorted({ev["subject_ids"][0] for ev in opt_outs})

    # -- Panel A: generated, every line referenced -----------------------
    sec1 = (
        "    <h3>1. General information</h3>\n"
        "    <ul>\n"
        + _line(f"Scope: a demonstration corpus of {total} logged "
                f"rights events under Merkle root {root_hex} "
                f"(size {total}); no provider, no model.",
                [ev["event_id"] for _i, ev in events])
        + _line("Modality: text — registry records and "
                "machine-readable reservation signals.",
                [ev["event_id"] for _i, ev in events])
        + _line(f"Content types: {len(by_type.get('chain_assertion', []))} "
                f"registration assertions, "
                f"{len(by_type.get('dispute', []))} dispute record, "
                f"{len(revocations)} revocation, "
                f"{len(opt_outs)} reservation signals.",
                [ev["event_id"] for evs in by_type.values()
                 for ev in evs])
        + "    </ul>\n")

    source_items = []
    for ep in sorted(by_ep):
        evs = by_ep[ep]
        urls = sorted({ev["source_url"] for ev in evs})
        url_html = "; ".join(link_https(u) for u in urls)
        source_items.append(
            f"      <li>{esc(ep)}: {len(evs)} events from "
            f"{len(urls)} source(s) — {url_html}."
            + _refs([ev["event_id"] for ev in evs]) + "</li>\n")
    sec2 = (
        "    <h3>2. List of data sources</h3>\n"
        "    <p>Grouped by epistemic-provenance channel; each source "
        "URL below resolves to the cited record or its format "
        "documentation.</p>\n"
        "    <ul>\n" + "".join(source_items) + "    </ul>\n")

    reservation_items = []
    for host in hosts:
        host_events = [ev for ev in opt_outs
                       if ev["subject_ids"][0] == host]
        mechanisms = sorted({ev["claim"]["mechanism"]
                             for ev in host_events})
        reservation_items.append(_line(
            f"{host.removeprefix('web:')}: {len(host_events)} "
            f"machine-readable reservation signals "
            f"({', '.join(mechanisms)}), recorded as opt_out events; "
            "the fused reservation status is committed in this "
            "corpus artifact.",
            [ev["event_id"] for ev in host_events]))
    reservation_beliefs = [
        b for _i, b in corpus.beliefs
        if b["question"] == "use_reservation"]
    for b in reservation_beliefs:
        reservation_items.append(_line(
            f"Reservation status for {b['subject']}: "
            f"m(reserved) = {_mass(b['mass']['reserved'])}, "
            f"unresolved = {_mass(b['unresolved_mass'])} "
            f"(as_of {b['as_of']}).",
            [c["event_id"] for c in b["contributing_events"]]))
    change_items = [_line(
        f"Change management: {len(revocations)} revocation recorded; "
        "the post-revocation belief excludes the revoked claim while "
        "both events remain in the log.",
        [ev["event_id"] for ev in revocations])] if revocations else []
    sec3 = (
        "    <h3>3. Relevant data processing aspects</h3>\n"
        "    <ul>\n" + "".join(reservation_items)
        + "".join(change_items) + "    </ul>\n")

    panel_a = (
        '  <section class="panel">\n'
        "    <h2>Panel A — generated from the log</h2>\n"
        + sec1 + sec2 + sec3 +
        "  </section>\n")

    # -- Panel B: the same facts, drafted prose, no references -----------
    panel_b = (
        '  <section class="panel">\n'
        "    <h2>Panel B — the same facts as drafted prose</h2>\n"
        "    <p>The corpus consists of music-rights registration "
        "records concerning one work, including two registrations "
        "filed with collecting societies, a documented disagreement "
        "between them, and a later withdrawal of one registration. "
        "It also includes publicly available machine-readable "
        "reservation signals from a major news publisher's robots.txt "
        "file and from the example in the W3C TDM Reservation "
        "Protocol specification. Reservation signals were recorded "
        "and reflected in the corpus. All sources are text. The "
        "process respected applicable opt-outs and kept the record "
        "of the withdrawn registration.</p>\n"
        "  </section>\n")

    replay_cmds = (
        "  <h2>Verify</h2>\n"
        "  <pre>python -m rights_events.replay --run "
        "../evidence/corpus_run.ri --subject work:song-x\n"
        "python -m rights_events.replay --run ../evidence/corpus_run.ri "
        "--subject web:www.nytimes.com --question use_reservation</pre>\n"
        '  <p><a href="../evidence/corpus_run.ri" download>Download '
        "the corpus artifact</a> · "
        '<a href="../evidence/index.html">Verification page</a></p>\n')

    body = (
        f'  <p class="label-block">{esc(LABEL)}</p>\n'
        f"  <p>{esc(COMPOSITION)}</p>\n"
        f"  <p>{esc(SOURCE_LINE)}</p>\n"
        '  <div class="panels">\n'
        + panel_a + panel_b +
        "  </div>\n"
        f'  <p class="caption-block">{esc(CAPTION)}</p>\n'
        + replay_cmds)
    return page("Derived disclosure — generated beside drafted", body,
                "../style.css",
                crumbs='<a href="../index.html">Index</a> / '
                       "Derived disclosure")
