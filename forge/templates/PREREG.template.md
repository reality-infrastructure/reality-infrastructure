# {{CONTRACT_ID}} PRE-REGISTRATION — {{ONE_LINE_TITLE}}

<!-- Pre-registration skeleton, extracted from the shipped instrument
     reference-implementation/audit/PREREGISTRATION.md (M-RI-14; the lighter
     precursor is pilot/ep_typing_preregistration.md). The discipline: metric,
     threshold, and decision rule are written and COMMITTED before any data is
     touched — the git ordering is the proof (M-RI-14-crm-reality-audit.md:57,
     proven at :95-96: prereg commit strictly precedes engine code). -->

```
status: FROZEN at commit. Written and committed BEFORE any engine code exists and
        BEFORE any data is fetched. Post-data changes only as dated amendments in
        §7 — never silent edits. Rule values are mirrored in code and test-pinned
        so silent edits fail the suite (audit/PREREGISTRATION.md:2-9, :4-5).
contract: {{path to CONTRACT.md}}
date: {{YYYY-MM-DD}}
```

## 1. Hypothesis

{{What claim is being tested, in one falsifiable sentence.}}

## 2. Input universe (measured this pass from the source — not remembered)

<!-- Pattern: audit/PREREGISTRATION.md:11-25. Pin the input before reading it. -->

- Source: {{path or URL}} — bytes: {{n}} · sha256: {{hash}}
- Records: {{n}} · {{key field}} distinct: {{n}} · null/empty: {{n}}
- {{Anomalies found while measuring: REPORTED here, not resolved here.}}
- **Checkable universe: {{n}}** ({{inclusion rule}}); the rest classify
  {{excluded-verdict}} with closed reason codes.

## 3. Metric, closed vocabulary, and threshold

<!-- Pattern: audit/PREREGISTRATION.md:27-39. The output vocabulary is closed —
     no additions without a §7 amendment. -->

- Metric: {{what is measured, exactly}}
- Verdict vocabulary (closed): {{TERM_1}} · {{TERM_2}} · {{...}}
- Threshold / decision rule: {{value + comparison, declared here}}
- Predicted counts: UNKNOWN and declared so — no rate is guessed
  (audit/PREREGISTRATION.md:60-62).
- Absence framing (MUST): absence of a record is reported as "no
  machine-readable record found in the queried datasets" — never as a claim
  about the world (audit/PREREGISTRATION.md:34-39).

## 4. Decision rules (govern the engine, written before it)

<!-- Pattern: audit/PREREGISTRATION.md:78-113. Numbered branches, each naming
     its verdict and its citation requirement. -->

- R1 {{condition}} → {{verdict}} (cite {{record fields}}).
- R2 {{condition}} → {{verdict}}.
- {{...}} Every verdict record carries citations: (source, record identifier,
  record date, retrieval date); absence verdicts carry the attested queries.

## 5. Known-answer commitment

<!-- Pattern: audit/PREREGISTRATION.md:115-120. -->

Input {{known input}} MUST classify {{known verdict}} from the frozen inputs.
If the rules as written yield anything else, that is a STOP-and-report finding —
the rules are not tuned to pass.

## 6. STOP conditions (halt and report; the halt is the deliverable)

<!-- Pattern: audit/PREREGISTRATION.md:134-141. -->

S1 source sha256 differs from §2 pin · S2 any input value outside §3's closed
sets · S3 {{integrity condition}} · S4 {{schema-drift condition}} ·
S5 known-answer commitment fails.

## 7. AMENDMENTS (dated, append-only; empty at freeze)

<!-- Pattern: audit/PREREGISTRATION.md:143-231. Each amendment is dated, names
     what changed and why, states BEFORE/AFTER, and re-pins any deliberately
     broken hash in the same commit (:182-186). Never edit §§1-6 in place. -->
