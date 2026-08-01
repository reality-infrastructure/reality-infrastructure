# CONTRACT 3 — THE FOUR VIEWS, PUBLIC (planned Days 14–19, opened Day 1)
### One static site, generated from the real run artifacts: provenance explorer, rights-state query, evidence export, derived disclosure. The compliance argument made visible: an Art. 53-shaped summary generated from the log, beside the same facts as unverifiable prose, captioned "one of these can be replayed."

---

OBJECTIVE
Build a deterministic static-site generator that renders the two real run artifacts (Song X and
the nine-parcel Cook County run) into four public views — provenance explorer, rights-state,
evidence export, derived disclosure — as plain static files served from the repo via GitHub
Pages. Every fact displayed traces to a logged event. The contract is complete when the site
builds reproducibly from the run dirs, the four views render both domains, the derived-disclosure
page shows the generated summary beside the prose version with the replay caption, and the
evidence bundles it links are verifiable offline with the unchanged replay CLI.

SCOPE
IN:
- A generator module reading the run artifacts, emitting static HTML/CSS into `docs/` at the
  repo root (GitHub Pages source). Stdlib-only generation. Hand-written CSS. No JS frameworks;
  minimal vanilla JS only where justified at plan gate.
- VIEW 1 — Provenance explorer: per run, the event log as a table — index, event type, subject,
  claimant, EP type, source_url (linked), observed_date, Merkle root/size; each event expandable
  to inclusion-proof data. Both domains, same rendering — the sameness IS the message.
- VIEW 2 — Rights-state: per subject, the belief object rendered honestly: singleton masses,
  explicit conflict mass, explicit Omega/unresolved mass, contributing events with EP types and
  statuses. Contest shown without editorializing.
- VIEW 3 — Evidence export: downloadable frozen bundles plus a verification page: exact replay
  CLI commands, what each check proves, what verification does NOT prove (limits language
  verbatim from README).
- VIEW 4 — Derived disclosure: two panels side by side. Panel A: a document in the structure of
  the EU AI Act Art. 53 public template, every line GENERATED from logged events with event
  references. Panel B: the same facts as drafted prose, no references. Caption verbatim:
  "One of these can be replayed." Demonstration label at caption weight.
- Site index: what this is (three sentences, README register), the four views, repo /
  NEUTRALITY.md / CITATION.cff links, methodology placeholder (Contract 4).
- Determinism: byte-identical docs/ from the same artifacts; double-build test is acceptance.
- Tests: view rendering, escaping, link integrity, double-build, full suite green.
OUT (wall, extended): ri_core/, schema.py, policy.py, pipeline.py, replay.py, the adapters, both
runners — untouched byte-for-byte from v1.2.0. The site READS artifacts; it never recomputes
beliefs. No server/database/analytics/trackers/external fonts/CDNs (works from file://). No new
dependencies. No methodology prose. No market claims. No screenshots-of-data.

PLAN GATE RULINGS (2026-08-01, gate cleared on all three):
(i) View 4 reservation section: OPTION (B) APPROVED — site/corpus.py composes the SYNTHETIC
    Song X fixture plus the REAL captured reservation fixtures (NYT robots.txt capture, W3C
    TDMRep spec example) through the UNCHANGED pipeline in the runner pattern (use, not
    modification). Requirements: the corpus composition is stated on the disclosure page
    itself; the corpus .ri lands in evidence/ under SHA256SUMS and verifies with the same
    replay commands; corpus.py's docstring states runner-pattern composition, wall untouched.
(ii) Demonstration label wording APPROVED VERBATIM (see the disclosure page), caption-weight
    styling. The template-structure source line stays: structure follows the European
    Commission AI Office Template for the Public Summary of Training Content (adopted
    24 July 2025) as documented in public sources; not the official form. Section mapping
    (General information / List of data sources / Relevant data processing aspects) matches
    the template's three-part structure.
(iii) Overall approved with explicit acceptance of both deviations: run artifacts are single
    canonical .ri FILES (contract's "run dir" corrected), and NO-ZIP packaging (raw .ri +
    SHA256SUMS.txt + verification page — zip timestamps would break the double-build
    byte-identity the contract itself demands). Also ratified: zero JS via details/summary;
    https-only link rendering, all else escaped text; README-drift test on limits language.
    Operator enables Pages (Settings -> Pages -> main /docs) at the C3-P1 flag commit and
    confirms the live URL.

CONSTRAINTS
1. Wall per SCOPE OUT; proof at DONE: scoped `git diff v1.2.0 HEAD --stat` empty.
2. No fabrication extends to site prose; limits language carried verbatim from README.
3. The demonstration label is not fine print — caption weight.
4. Determinism absolute; double-build test is acceptance.
5. All 571 existing tests pass untouched; new tests add only.
6. Accessibility floor: semantic HTML, real tables, alt text, readable contrast.
7. R1 privacy framing carries to the site.
8. No emojis. No marketing register.

ACCEPTANCE
- docs/ builds from one documented command; double-build byte-identity passes.
- All four views render BOTH domains (View 4 scope per gate; Views 1-3 cover Song X + all nine
  parcels).
- Every fixture source_url appears as a working link; every displayed mass matches the run
  artifacts (spot-asserted).
- Evidence bundles download and verify offline with README-documented replay commands; tamper
  exits nonzero.
- View 4: generated-with-references beside prose-without, caption verbatim, label at caption
  weight.
- Site works from file:// with no network.
- Wall diff empty. Suite green (571 + new).
- A stranger given only the URL can state what the log contains, who claims what on Song X and
  the Dolton parcel, what is contested and by how much, and how to verify it.

DEPLOY
Commit and push per phase; generator output committed to docs/ on main. Operator enables Pages
and confirms the live URL. No tags (operator tags at closeout). README gains a Site line once
the URL is confirmed.

DONE
Report: phases with hashes; build command; double-build proof; wall diff; test totals; live URL;
four-view walk-through; View 4 label as shipped; deviations; parked items for Contract 4
(including which anchors the methodology note needs).

STOP CONDITIONS
- THE WALL: any needed change to frozen paths — stop, record, report. Re-running existing
  runners with existing flags is permitted; changing them is not.
- Rendering needs data the artifacts lack and existing flags can't produce: stop, report gap.
- Pages constraints can't fit the evidence: stop, propose alternatives.
- Art. 53 structure not responsibly approximable: stop, request reference material.
- Red tests at session end: record, end cleanly.

---

# DONE REPORT (2026-08-01)

Contract 3 — planned for Days 14-19 — closed on Day 1.

## Phases, with commit hashes

- C3-P1 scaffolding, evidence, determinism: 230c6f8
- C3-P2 provenance explorer + rights-state: 3169569
- C3-P3 derived disclosure + corpus artifact: af9425c
- C3-P4 closeout (wall proof, archive): this commit

## Build command and double-build proof

    python -m rights_events.site.build        (from reference-implementation/)

One command; it re-runs the frozen runners in-process with their
existing flags, builds the disclosure corpus, writes checksums, and
emits every page. Double-build byte-identity is asserted by
tests/test_rights_site.py::TestBuild::test_double_build_byte_identical
(two builds into separate directories, every file byte-compared) —
green in the closing suite. No timestamps, no clock, sorted iteration.

## Zero-change-wall proof (extended list)

    $ git diff v1.2.0 HEAD --stat -- reference-implementation/ri_core \
        reference-implementation/rights_events/schema.py \
        reference-implementation/rights_events/policy.py \
        reference-implementation/rights_events/pipeline.py \
        reference-implementation/rights_events/replay.py \
        reference-implementation/rights_events/adapters \
        reference-implementation/rights_events/song_x.py \
        reference-implementation/rights_events/parcels.py
    (empty output — byte-identical to the v1.2.0 tag)

New code lives only in rights_events/site/ and tests/. The replay CLI
gained no flags; the site reads artifacts through the same load path
the CLI uses, and every displayed mass decodes from stored belief
entries — nothing is recomputed.

## Test totals

594 passed, 19.86s at close (571 inherited untouched + 23 site tests).

## Live URL

PENDING OPERATOR ACTION (flagged at C3-P1): Settings -> Pages ->
Deploy from a branch -> main, /docs. Expected URL
https://reality-infrastructure.github.io/reality-infrastructure/.
The README Site line lands in a follow-up commit once the operator
confirms the URL resolves.

## The four views, walked through

VIEW 1 (provenance/song-x.html, provenance/parcels.html): each run's
event log as one table — index, event id, type, subject, claimant, EP
type, observed date, linked https source — with the Merkle root and
size in the header and a native details/summary expansion per row
showing the full RFC 9162 inclusion proof (leaf hash, audit path,
root). Four events for Song X, fifty-six for the parcels, one
renderer for both: the sameness is the message.

VIEW 2 (rights-state/): an index of ten subjects with plain-text
contested tags, then one page per subject: the mass table (each
competing hypothesis, an explicit conflict row reading "evidence that
contradicts itself, kept visible", an explicit "unresolved (ignorance
set Omega)" row), followed by the contributing events with EP types,
uncertainty types, statuses (active/revoked/revocation/informational)
and applied masses. Song X shows both its pre- and post-revocation
beliefs; the Dolton page shows five competing claims at 0.01536 each
under 0.91296 conflict. Contested pages carry the records-disagree
sentence (R1); no alarm styling anywhere.

VIEW 3 (evidence/): the three run artifacts as downloads (song_x
9489 B, parcels 117552 B, corpus 34572 B) with a SHA-256 table, the
exact replay commands, a plain-language list of what each check
proves (byte-identity, root match, inclusions, tamper exit), and —
quoted verbatim from the README with a drift test — what verification
does not prove.

VIEW 4 (disclosure/): the demonstration label at caption weight, the
corpus-composition statement, and the template-source line; then two
panels. Panel A: the three sections of the EC AI Office
training-content template structure, every line generated from the
corpus log with event references — including real reservation lines
(fourteen NYT robots.txt opt-outs, two TDMRep locations, fused
m(reserved)=0.3 per subject) and a change-management line from the
revocation. Panel B: the same facts as drafted prose, no references.
Between them, verbatim: "One of these can be replayed."

## View 4 label as shipped (approved verbatim at the gate)

DEMONSTRATION ONLY. Generated from labeled fixture data in a public
research repository. The scope includes a SYNTHETIC music-rights
fixture and real captured reservation signals. This is not a
regulatory filing; no provider has submitted it to any authority; no
model was trained on this corpus. Panel A is derived mechanically
from logged events — every line carries its event references. Panel B
states the same facts as drafted prose with none.

## Deviations, with reasons

1. Run artifacts are single canonical .ri files, not "run dirs"
   (accepted at the gate — that is what pipeline.save emits).
2. No-zip evidence packaging: raw .ri + SHA256SUMS.txt + verification
   page (accepted at the gate — zip timestamps would break the
   double-build byte-identity the contract demands).
3. Zero JavaScript outright, not "minimal": details/summary covers
   the only interaction (ratified at the gate).
4. The View 1 table renders the contract's specified columns; claim
   payloads (grantor/grantee text) surface on rights-state pages via
   frame labels rather than in the provenance table — the escaping
   test asserts where the strings actually appear.

## Parked for Contract 4 (methodology note)

Anchors the note will want, all stable: per-event rows
provenance/<run>.html#e<N>; per-subject pages
rights-state/parcel-<PIN>.html and rights-state/song-x.html;
evidence/index.html for the verification procedure;
disclosure/index.html for the derived-vs-drafted argument. Also
parked: the R2 redemption fixture (F3, Contract 2) which would add a
redemption row to the Dolton-area provenance table and a delta to a
rights-state page with zero site changes; rights-state rendering of
use_reservation subjects (the corpus commits them; only Song X and
parcel subjects get pages today); and cross-domain single-log runs.
