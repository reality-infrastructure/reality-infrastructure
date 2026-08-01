"""Site build command (C3-P1 scaffolding; views land in P2-P3).

Usage (the ONE documented build command):
    python -m rights_events.site.build [--out DIR]

DIR defaults to <repo root>/docs — the GitHub Pages source. Steps:
1. Re-run the two existing runners IN-PROCESS with their existing
   flags (permitted use; the runners are frozen at v1.2.0), writing
   the run artifacts into DIR/evidence/.
2. Write SHA256SUMS.txt over the artifacts (sorted).
3. Emit style.css, the site index, and the evidence/verification page.
Determinism: output bytes are a function of the run artifacts alone —
no timestamps, no clock, sorted iteration everywhere. Building twice
into two directories yields byte-identical trees (tested).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from rights_events import parcels as parcels_runner
from rights_events import song_x as song_x_runner
from rights_events.site.html import (
    REPO_URL,
    esc,
    limits_block,
    page,
)
from rights_events.site.views import (
    load_run,
    render_provenance,
    render_rights_state_index,
    render_subject,
    subject_page_name,
)

_REPO_ROOT = Path(__file__).parents[3]

STYLE_CSS = """\
:root {
  --ink: #1a1a1a;
  --muted: #555555;
  --rule: #c9c9c9;
  --paper: #ffffff;
  --shade: #f4f4f2;
  --accent: #23425f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.55;
}
header, main, footer {
  max-width: 60rem;
  margin: 0 auto;
  padding: 0.75rem 1.25rem;
}
header { border-bottom: 3px double var(--rule); }
footer {
  border-top: 1px solid var(--rule);
  color: var(--muted);
  font-size: 0.9rem;
}
h1 { font-size: 1.6rem; margin: 0.5rem 0; }
h2 { font-size: 1.25rem; margin-top: 2rem; border-bottom: 1px solid var(--rule); padding-bottom: 0.25rem; }
h3 { font-size: 1.05rem; }
a { color: var(--accent); }
nav[aria-label="Breadcrumb"] { font-size: 0.9rem; color: var(--muted); }
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.95rem;
  font-family: ui-monospace, Consolas, "Courier New", monospace;
}
caption { text-align: left; font-style: italic; color: var(--muted); padding: 0.4rem 0; }
th, td {
  border: 1px solid var(--rule);
  padding: 0.35rem 0.5rem;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}
th { background: var(--shade); font-weight: 600; }
tbody tr:nth-child(even) { background: var(--shade); }
code, pre {
  font-family: ui-monospace, Consolas, "Courier New", monospace;
  background: var(--shade);
  font-size: 0.9rem;
}
pre { padding: 0.75rem; overflow-x: auto; border: 1px solid var(--rule); }
details { margin: 0.25rem 0; }
details summary { cursor: pointer; color: var(--accent); }
.limits { border: 1px solid var(--rule); background: var(--shade); padding: 0.25rem 1rem 0.75rem; }
.contested { font-weight: 600; }
.label-block, .caption-block {
  font-size: 1.05rem;
  font-weight: 600;
  border: 2px solid var(--ink);
  padding: 0.75rem 1rem;
  margin: 1rem 0;
  background: var(--shade);
}
.panels { display: flex; flex-wrap: wrap; gap: 1.5rem; }
.panel { flex: 1 1 24rem; border: 1px solid var(--rule); padding: 0 1rem 1rem; }
.mass-table td.num { text-align: right; }
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _index_html(evidence_files: list[str]) -> str:
    files = "".join(
        f'      <li><a href="evidence/{esc(name)}" download>'
        f"{esc(name)}</a></li>\n" for name in evidence_files)
    body = (
        "  <p>This site renders the run artifacts of the Reality "
        "Infrastructure reference implementation into four public "
        "views. Every fact shown is read from an append-only Merkle "
        "log and traces to a logged event; nothing is computed for "
        "display. The repository remains the proof; this site makes "
        "it legible.</p>\n"
        "  <h2>The four views</h2>\n"
        "  <ol>\n"
        '    <li><a href="provenance/song-x.html">Provenance '
        'explorer</a> — the event logs, event by event, with '
        'inclusion proofs (<a href="provenance/song-x.html">Song X'
        '</a>, <a href="provenance/parcels.html">Cook County parcels'
        "</a>).</li>\n"
        '    <li><a href="rights-state/index.html">Rights-state</a> '
        "— the belief object per subject: who claims what, what is "
        "contested, and by how much.</li>\n"
        '    <li><a href="evidence/index.html">Evidence export</a> — '
        "the frozen run artifacts, their checksums, and exactly how "
        "to verify them offline.</li>\n"
        "    <li>Derived disclosure — a disclosure document generated "
        "from the log beside the same facts as drafted prose. (Built "
        "in phase C3-P3.)</li>\n"
        "  </ol>\n"
        "  <h2>Downloads</h2>\n"
        "  <ul>\n" + files +
        '    <li><a href="evidence/SHA256SUMS.txt">SHA256SUMS.txt'
        "</a></li>\n"
        "  </ul>\n"
        + limits_block() +
        "  <h2>Project</h2>\n"
        "  <ul>\n"
        f'    <li><a href="{REPO_URL}" rel="noopener">Repository'
        "</a></li>\n"
        f'    <li><a href="{REPO_URL}/blob/main/NEUTRALITY.md" '
        'rel="noopener">Neutrality covenant</a></li>\n'
        f'    <li><a href="{REPO_URL}/blob/main/CITATION.cff" '
        'rel="noopener">Citation</a></li>\n'
        "    <li>Methodology note — placeholder; Contract 4 fills "
        "this.</li>\n"
        "  </ul>\n"
    )
    return page("Reality Infrastructure — the four views", body,
                "style.css")


def _evidence_html(sums: list[tuple[str, str]]) -> str:
    rows = "".join(
        "      <tr>"
        f'<td><a href="{esc(name)}" download>{esc(name)}</a></td>'
        f"<td><code>{esc(digest)}</code></td></tr>\n"
        for name, digest in sums)
    body = (
        "  <p>Each file below is a frozen run artifact: an "
        "append-only Merkle event log and a belief log, canonically "
        "serialized. They are the same bytes the tests verify; "
        "downloading them and verifying offline requires only the "
        "public repository.</p>\n"
        "  <table>\n"
        "    <caption>Artifacts and SHA-256 checksums</caption>\n"
        "    <thead><tr><th scope=\"col\">File</th>"
        "<th scope=\"col\">SHA-256</th></tr></thead>\n"
        "    <tbody>\n" + rows + "    </tbody>\n"
        "  </table>\n"
        "  <h2>How to verify</h2>\n"
        "  <pre>git clone " + esc(REPO_URL) + "\n"
        "cd reality-infrastructure/reference-implementation\n"
        "python -m rights_events.replay --run PATH/TO/song_x_run.ri "
        "--subject work:song-x\n"
        "python -m rights_events.replay --run PATH/TO/parcels_run.ri "
        "--subject parcel:29024080530000</pre>\n"
        "  <h2>What each check proves</h2>\n"
        "  <ul>\n"
        "    <li>byte-identity — the belief object reconstructed from "
        "the logged events is byte-identical to the stored one; the "
        "conclusion follows from the record, not from anyone's "
        "word.</li>\n"
        "    <li>event log root — the rebuilt Merkle root matches the "
        "root recorded inside the belief object; the event set cannot "
        "have been silently rewritten.</li>\n"
        "    <li>belief inclusion and event inclusions — RFC 9162 "
        "inclusion proofs bind each displayed fact to the log.</li>\n"
        "    <li>tamper exit — altering any signed event or any "
        "stored belief makes the same command exit nonzero.</li>\n"
        "  </ul>\n"
        + limits_block()
    )
    return page("Evidence export and verification", body, "../style.css",
                crumbs='<a href="../index.html">Index</a> / Evidence')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.site.build",
        description="Build the static site from the run artifacts.")
    parser.add_argument("--out", default=str(_REPO_ROOT / "docs"),
                        help="output directory (default: <repo>/docs)")
    args = parser.parse_args(argv)
    out = Path(args.out)
    evidence = out / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)

    # 1. Re-run the frozen runners with their existing flags.
    if song_x_runner.main(
            ["--out", str(evidence / "song_x_run.ri")]) != 0:
        print("BUILD FAILED: song_x runner nonzero")
        return 1
    if parcels_runner.main(
            ["--out", str(evidence / "parcels_run.ri")]) != 0:
        print("BUILD FAILED: parcels runner nonzero")
        return 1

    # 2. Checksums (sorted by filename).
    artifacts = sorted(p.name for p in evidence.glob("*.ri"))
    sums = [(name, _sha256(evidence / name)) for name in artifacts]
    _write(evidence / "SHA256SUMS.txt",
           "".join(f"{digest}  {name}\n" for name, digest in sums))

    # 3. Load the artifacts back (read-only; signatures re-verify).
    runs = [
        load_run("song-x", "Song X (SYNTHETIC fixture)",
                 evidence / "song_x_run.ri"),
        load_run("parcels", "Cook County parcels (real records)",
                 evidence / "parcels_run.ri"),
    ]

    # 4. Pages.
    _write(out / "style.css", STYLE_CSS)
    _write(out / "index.html", _index_html(artifacts))
    _write(evidence / "index.html", _evidence_html(sums))
    for run in runs:
        _write(out / "provenance" / f"{run.slug}.html",
               render_provenance(run))
        for subject in sorted({b["subject"] for _i, b in run.beliefs}):
            _write(out / "rights-state" / subject_page_name(subject),
                   render_subject(run, subject))
    _write(out / "rights-state" / "index.html",
           render_rights_state_index(runs))

    print(f"site built: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
