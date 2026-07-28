# M-RI-12 — Case study: real-parcel verification dossier, prospect-facing (COMPLETED 2026-07-28)

Contract text as issued (pasted 2026-07-27; never placed in CURRENT.md — archived here
verbatim), followed by the approved Plan Gate rulings and the DONE report.

---

TASK — Case study: real-parcel verification dossier, prospect-facing (M-RI-12; docs-only)

OBJECTIVE
Ship collateral/case-study-dolton-v1.md (ANONYMIZED, usable with any second land bank or
prospect immediately) and collateral/case-study-dolton-named-DO-NOT-SEND.md (named version,
locked pending SSLBDA consent) — a 1–2 page case study of the M-RI-11 result written for a
land-bank executive director or municipal official, every claim traceable to repo artifacts.

CONTEXT
- pilot/dolton_dossier.py golden transcript (M-RI-11): the source of every number
- research/stage-1-prior-art/: beachhead framing; ALTA/Milliman fraud-claim figure
  ($206,976 avg refinance fraud/forgery claim, Nov 2025 study) — usable as market context
- contracts/completed/M-RI-11-real-parcel-dossier.md: process record
- AUDIENCE: a land-bank ED who has never heard of belief functions. Zero jargon in the
  body; one small "how it works" sidebar maximum.
- SENSITIVITY RULE (non-negotiable): the CRM error belongs to the client. The anonymized
  version must not permit re-identification; the named version does not leave the repo.

SCOPE
IN:
- collateral/case-study-dolton-v1.md (anonymized)
- collateral/case-study-dolton-named-DO-NOT-SEND.md (identical structure, real names,
  header warning: "LOCKED — requires SSLBDA written consent before any external use")
- collateral/README.md (usage rules: which version may be sent to whom, consent status)
OUT (explicitly forbidden this contract):
- No code, no ri_core/tests/docs changes, no ROADMAP change, no edits to any existing file
- No claims not present in banked artifacts; no invented testimonials or outcomes
- No language presenting the work as a title opinion, title search, or legal service
- Named version: never referenced in the anonymized version, README, or commit message in
  a way that discloses the client name (commit message says "case study v1", nothing more)

PLAN GATE
Before writing, state:
(a) ANONYMIZATION MAP — the load-bearing item. Exactly what transforms: SSLBDA → "a
    Cook County land bank"; Nigel/individuals → roles only; PIN + address → "a residential
    parcel in a south-suburban municipality"; "Dolton" → removed from the anonymized body
    AND filename check — flag that the proposed filename contains "dolton" and propose
    collateral/case-study-parcel-verification-v1.md instead; CRM feature id → "the
    inventory record"; deed doc number → KEPT or REDACTED (argue it: public record, but
    it re-identifies the parcel in seconds — recommend redact to "the 2017 recorded
    deed"); 740 features → "an inventory of ~700 parcels" (exact count is identifying).
    State the re-identification test you'll apply: could a reader with Socrata access
    find the parcel from the anonymized text alone? Must be NO.
(b) STRUCTURE (~1.5 pages): proposed sections — recommend: THE SITUATION (land banks act
    on inventory records; wrong records cost real money — ALTA figure as context);
    WHAT WE DID (one parcel, four public+internal sources, pre-registered confidence,
    every step reproducible); WHAT WE FOUND (the CRM says sold; the county record chain
    shows a conveyance by another party at that exact window; conflict quantified at 40%,
    traced to two specific records); WHY THIS IS DIFFERENT (a normal pipeline averages or
    picks a winner; this system holds the conflict, names the records, and shows the
    resolution — the counterfactual: correct one record, conflict falls to zero);
    WHAT IT MEANS FOR YOU (every parcel in your inventory can carry this dossier;
    scoping conversation CTA); sidebar (plain-language: evidence log, conflict mass,
    replayability); footer (informational-analysis disclaimer + "figures from a
    reproducible, test-enforced transcript").
(c) CLAIMS AUDIT: the table mapping every number and factual claim in the case study to
    its artifact (golden transcript line, MANIFEST, Stage-1 file, ALTA citation) —
    ships as an appendix in the NAMED version only (the anonymized version's audit table
    would leak identifiers; state this reasoning in collateral/README.md).
(d) VOICE + CTA: first-person-plural Registry Signal voice; the CTA wording ("we can run
    this against any parcel you name — the first one is how this case study happened");
    no pricing in v1.

ACCEPTANCE CRITERIA
- [ ] Both files + README exist; anonymized version contains no instance of: SSLBDA,
      South Suburban, Nigel, Dolton, the PIN, the address, the deed doc number, the CRM
      feature id, or the exact inventory count (grep proof pasted)
- [ ] All numbers in both versions match the golden transcript / banked artifacts exactly
      (0.40 conflict, 0.8 counterfactual, source counts)
- [ ] Named version header carries the LOCKED warning; README states the consent rule
- [ ] Disclaimer present in both; no title-opinion language (grep for "title opinion"
      confirms it appears only inside the disclaimer)
- [ ] `pytest -q` still green (415 — nothing touched); git diff shows only the three new
      files; committed "M-RI-12: case study v1" and pushed; push confirmation pasted

STOP CONDITIONS
Halt and report — do not proceed — if: any claim needed for the narrative lacks a banked
artifact; anonymization cannot survive the re-identification test without gutting the
story; or push fails.

---

## Plan Gate approval (2026-07-28) — rulings and amendment

R1: Anonymized filename = collateral/case-study-parcel-verification-v1.md. Named file
keeps its contract name with the LOCKED header.

R2: "south suburban" never appears in the anonymized version; parcel phrase = "a
residential parcel in the land bank's service area." "south suburban" (case-insensitive)
and "Woodlawn" added to the forbidden-string grep list.

AMENDMENT A1 (PDF deliverable — anonymized version ONLY):
1. Also produce collateral/case-study-parcel-verification-v1.pdf — print-styled HTML
   intermediate in collateral/build/ (gitignored), rendered via Edge headless. Letter,
   ~0.75in margins, system font stack, Registry Signal wordmark as styled text, boxed
   sidebar, footer disclaimer on the page.
2. PDF hygiene: HTML title "Parcel Verification Case Study — The Registry Signal"; no
   client-identifying strings in HTML/metadata/filenames; full forbidden-string grep on
   the HTML source is the content proof.
3. Copy the final PDF to Downloads; report size + sha256 of both copies (must match).
4. NEVER render the named version to PDF or HTML.
5. Commit the .md files, README, and repo PDF ("M-RI-12: case study v1"); .gitignore
   collateral/build/. Push.

---

## DONE report

**1. PLANNED** — Plan Gate presented 2026-07-27 (anonymization map incl. deed-doc-number
REDACT recommendation and the filename flag; structure; claims-audit placement; voice/CTA).
Approved 2026-07-28 with rulings R1, R2 and amendment A1 above.

**2. IMPLEMENTED** — Shipped:
- `collateral/case-study-parcel-verification-v1.md` (anonymized, per R1 filename)
- `collateral/case-study-dolton-named-DO-NOT-SEND.md` (identical structure, real
  identifiers, LOCKED header, claims-audit appendix)
- `collateral/README.md` (send rules, consent status NOT OBTAINED as of 2026-07-28,
  audit-placement reasoning, build rule, repo-visibility caveat; written without naming
  the client)
- `collateral/case-study-parcel-verification-v1.pdf` (rendered ONLY from the anonymized
  HTML intermediate `collateral/build/case-study-parcel-verification-v1.html`, gitignored;
  Edge headless `--headless --disable-gpu --no-pdf-header-footer --print-to-pdf`; HTML
  title "Parcel Verification Case Study — The Registry Signal"; 2 pages, boxed sidebar,
  footer disclaimer). Named version was never rendered to HTML or PDF.
- `.gitignore`: added `collateral/build/`

**3. TESTED** — Acceptance checklist:

- [x] Both files + README exist; forbidden-string grep over the anonymized markdown AND
      the HTML source, case-insensitive, ZERO hits for every pattern:
      SSLBDA, south[ -]suburban (R2), Nigel, Dolton, Woodlawn (R2), 29024080530000,
      29-02-408-053-0000, 2902408053, 14347, 1717247010, 258, 740, THORTON, CSMA,
      FIRSTKEY, "FIRST KEY", wvhk, 3723, 97qp, 65000, "65,000", 60419, 2017-01, 2017-06,
      97219177, "feature id". Re-identification test: the anonymized residue ("Cook
      County land bank", "a 2017 deed", "roughly 700 records") supports no Socrata query
      returning the parcel — PASS.
- [x] Numbers match banked artifacts exactly: 40% conflict (golden §5 m(∅)=0.4000),
      counterfactual 40%→0% with not_conveyed 0.8000 (§7), 4 sources / tax 0 rows (§1),
      6 sale rows 2000–2017 (§2), roll years 1999–2026 (§1–2), 17 spellings → 10 parties
      (§2), 740→"roughly 700" (MANIFEST; exact count named version only), ALTA $206,976 /
      ~7x / >40% Nov 2025 Milliman (research/stage-1-prior-art/stage-1-adversarial-verdict.md).
      Full claim→artifact table: named version appendix.
- [x] Named header carries the LOCKED warning ("LOCKED — requires SSLBDA written consent
      before any external use"); README states the consent rule and status.
- [x] Disclaimer present in both versions and the PDF; grep "title opinion" (case-
      insensitive): exactly 1 hit per file, each on the disclaimer line
      (anonymized :95, named :106, HTML :162); 0 hits elsewhere.
- [x] `pytest -q`: **415 passed in 79.19s** (nothing touched — docs-only). Staged diff =
      the three .md files + PDF + one .gitignore line, nothing else. Committed
      `921f045` "M-RI-12: case study v1"; pushed: `c54cfc5..921f045 main -> main`.
- [x] A1.3: PDF copied to `C:\Users\newce\Downloads\case-study-parcel-verification-v1.pdf`;
      both copies 59,212 bytes, sha256
      `a59ac36e7faf77182ec0fcb10a109f00e39acb977219e7b5b5217911f79e0c5f` (identical).

**4. COMMITTED** — `921f045` "M-RI-12: case study v1" (5 files, 283 insertions).

**5. PUSHED** — `c54cfc5..921f045 main -> main` (origin). This archive file is the
follow-up commit, per M-RI-11 precedent.
