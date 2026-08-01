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
