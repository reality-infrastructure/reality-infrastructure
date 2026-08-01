# CONTRACT 4 — THE METHODOLOGY NOTE (planned Days 20–21, opened Day 1)
### The constitution: ~2,500 words, five sections, standards register, limits carrying the weight. Canonical in the repo, rendered on the site, linked to the live views as worked examples. Ship: note published, release tagged, dated. Then the hard stop.

---

OBJECTIVE
Write and publish the canonical methodology note: approximately 2,500 words in exactly five
sections — the verification gap, evidence typing, contradiction preservation, the replay
guarantee, and limits — in standards-document register, with every factual claim checkable,
every external reference real, and the live site's views linked as worked examples. The note is
canonical in the repository, rendered as the site's methodology page from the single source, and
shipped in the final release. This contract completes the 21-day build.

SCOPE
IN:
- METHODOLOGY.md at the repository root: canonical source, 2,000–3,000 words, five sections in
  order under the specified headings (the verification gap; evidence typing (EP); contradiction
  preservation; the replay guarantee; limits, stated plainly), every external claim sourced,
  worked examples with actual masses linked to live rights-state pages, F3 disclosed.
- Site integration: methodology page rendered from the canonical source by the existing
  generator pattern (stdlib only); drift test; anchors tested against docs/.
- CITATION.cff to 1.4.0 / 2026-08-01. README methodology line from placeholder to link.
- Tests: drift, anchor presence, word-count range, suite green.
OUT: the wall extended — everything frozen at v1.3.0 stays frozen (engine, domain core,
adapters, runners, existing site views); the methodology page ADDS, modifying only the index
placeholder line and README line. No market/superlative language. No new dependencies. No
emojis. No changes to NEUTRALITY.md.

PLAN GATE RULINGS (2026-08-01, gate approved):
- All external claims grounded in-session before drafting: Commission AI Office template
  adoption 24 July 2025 (adoption record + independent analyses); C2PA's own explainer language
  ("provenance information alone cannot tell you whether the digital content is true, accurate
  or factual"); The MLC's $424,384,787 February 2021 accrued historical unmatched royalties
  (the MLC's own announcement, 20 DSPs); Denoeux 2008, Artificial Intelligence 172(2–3):234–264
  (confirmed citation). Operator verified the Dolton mass arithmetic, the Denoeux citation, and
  the MLC figure independently before approving.
- md->html path: stdlib line renderer for exactly the note's constructs; note formatting
  constrained to the renderer, not the reverse. Drift test: fresh render byte-compared against
  the committed page.
- Anchors: the full parked list from the C3 archive, verified against docs/.
- Title: "Verifiable Records of Contested Claims: Methodology". One-liner approved.
- Live URL confirmed by operator: 
  https://reality-infrastructure.github.io/reality-infrastructure/
- THE READ: the operator delegated the C4-P1 acceptance read to the session with four criteria
  (numbers against the site pages; superlative hunt with a correct count of zero; hostile read
  of section 5; section 1 survivable by its subjects). Performed and recorded in PROGRESS.md
  before P2.

CONSTRAINTS
1. Standards register throughout; the reader is assumed intelligent and skeptical.
2. Every factual claim checkable; a wrong mass in the constitution is a P0 defect.
3. The signature principle, claimed-not-true, and not-a-detector appear verbatim-consistent
   with the README (drift-checked).
4. Counsel flags framed as open questions for qualified counsel, never as legal conclusions.
5. F3 disclosure in Section 5 is mandatory.
6. Word count is a discipline, not a target to pad toward.
7. Suite green at every commit; wall diff at DONE.

ACCEPTANCE
- METHODOLOGY.md: five sections in order; word count in range; references complete; zero
  unsourced external claims; zero market/superlative language.
- Read approval recorded in PROGRESS.md before P2.
- Methodology page renders from the canonical source; drift test passes; anchors resolve;
  file:// works; double-build byte-identity passes.
- CITATION.cff at 1.4.0 / 2026-08-01 and parses.
- Wall diff vs v1.3.0 empty except the permitted index-placeholder and README lines.
- Suite green (594 + new).

DEPLOY
Commit and push per phase. After operator approval of the final state, the operator runs the
closeout: tag v1.4.0 and a GitHub Release — the operator tags, not the session.

DONE
Report: phases with commits; final word count; references; anchors; drift and byte-identity
results; wall diff; CITATION.cff state; claims cut for want of grounding; archive path. Final
line: the build state at hard stop.

STOP CONDITIONS
- Ungroundable external claims: flag or cut; never approximate.
- Markdown-dependency pressure: simplify the note instead; failing that, stop.
- Sections that cannot be filled honestly: write the smaller true thing and flag.
- Red tests at session end: record, end cleanly.
- After this contract closes and the operator tags v1.4.0: THE BUILD IS COMPLETE. No further
  contracts open under CF-024.

---

# DONE REPORT (2026-08-01)

Contract 4 — planned for Days 20-21 — closed on Day 1. The build is
complete.

## Phases, with commit hashes

- C4-P1 the draft and the recorded read: 7e3bf05
- C4-P2 site integration, README, CITATION, tests: 6c7318a
- C4-P3 closeout (this commit): archive, wall proof, hard stop

## Final word count

2,084 words (canonical source, code spans and link URLs excluded;
acceptance range 2,000-3,000; not padded toward the target per
Constraint 6). Enforced by test.

## References shipped in the note

1. Denoeux 2008, Artificial Intelligence 172(2-3):234-264 (the
   cautious rule).
2. RFC 9162, Certificate Transparency Version 2.0.
3. EU AI Act Article 53 (public text).
4. European Commission template adoption, 24 July 2025 (adoption
   record + Open Future independent analysis).
5. C2PA and Content Credentials Explainer (spec.c2pa.org).
6. The MLC, $424 million historical unmatched royalties announcement,
   February 2021.

## Anchors used (all six resolve in docs/, test-enforced)

index, rights-state/song-x.html,
rights-state/parcel-29024080530000.html, provenance/parcels.html,
evidence/index.html, disclosure/index.html — the complete parked list
from the C3 archive.

## Drift and byte-identity results

- Drift: fresh render of METHODOLOGY.md byte-equals the committed
  docs/methodology/index.html (test).
- Principles drift: the signature principle, claimed-not-true,
  not-a-detector, and no-laundering sentences verbatim-present in
  both the note and README (test).
- Double-build byte-identity of the full site: passing (existing
  acceptance test, unchanged).
- Lossless rendering: every prose line of the canonical source
  appears in the rendered page (test).

## Wall diff vs v1.3.0

Hard-frozen list (ri_core, schema/policy/pipeline/replay, adapters,
both runners, existing site view renderers views/disclosure/corpus/
html): EMPTY. Permitted deltas only: site/build.py +8/-2 (the index
placeholder line replaced by the methodology link; the additive
render call), README (two lines under Technical documentation),
CITATION.cff (version/date), plus the new files (METHODOLOGY.md,
site/methodology.py, docs/methodology/, tests).

## CITATION.cff

version: 1.4.0, date-released: 2026-08-01; abstract unchanged (no
factual correction was needed); structure parses (test).

## Claims cut for want of grounding

None. All external claims were grounded in-session at the gate before
drafting (the contract's cut-or-flag rule was satisfied by flagging
zero and grounding four). One deliberate non-claim, recorded at the
gate: no characterization of Art. 53 compliance quality or industry
behavior beyond the instrument's own structure.

## Archive path

reference-implementation/contracts/completed/C4-methodology-note.md
(this file).

## The build state at hard stop

Four contracts closed and archived (C1 event layer, C2 second domain,
C3 four views, C4 methodology note). 607 tests passing in 20.49s.
Live site: https://reality-infrastructure.github.io/reality-infrastructure/
serving the four views and the methodology page, generated
deterministically from replayable run artifacts. Dated artifacts:
v1.0.0 (2026-07-31, the stake), v1.1.0, v1.2.0, v1.3.0 (2026-08-01),
and v1.4.0 pending the operator's closeout tag and Release. The
21-day plan closed in two calendar days. After v1.4.0: no further
contracts open under CF-024.
