# collateral/ — usage rules

Prospect-facing material derived from the M-RI-11 real-parcel pilot. Two versions of one
case study exist in this directory. **They are not interchangeable.**

## Which version may be sent to whom

| File | Status | May be sent to |
|---|---|---|
| `case-study-parcel-verification-v1.md` | ANONYMIZED — cleared | Any prospect or second land bank |
| `case-study-parcel-verification-v1.pdf` | ANONYMIZED — cleared | Any prospect or second land bank (rendered from the anonymized markdown only) |
| `case-study-dolton-named-DO-NOT-SEND.md` | **LOCKED** | **No one.** Requires the client's written consent before ANY external use |

## Consent status

As of 2026-07-28: written consent for the named version has **NOT** been obtained. Until
it is, the named file does not leave this repository — no sending, excerpting, quoting,
or rendering (no PDF, no HTML). Only the anonymized version and its PDF may circulate.

## Why the claims-audit appendix is in the named version only

The contract requires every number in the case study to map to a banked repo artifact.
That audit table necessarily contains the parcel's PIN, recorded document numbers, and
record ids — exactly the identifiers the anonymization removes. Putting it in the
anonymized version would defeat the anonymization, so it ships as an appendix in the
named version only; reviewers verify claims against that appendix inside the repo.

## Anonymization rule

The anonymized version must not permit re-identification: no client name, no
municipality, no PIN, no street address, no document numbers, no record ids, no exact
dates or sale price, no exact inventory count, no party names, no dataset ids. The
mechanical check is a forbidden-string grep recorded in the M-RI-12 contract's DONE
report. The re-identification test: a reader with access to the county's open-data
portal must not be able to construct any query from the anonymized text alone that
returns the parcel.

## Build rule (PDF)

The PDF is rendered ONLY from the anonymized markdown, via a print-styled HTML
intermediate in `collateral/build/` (gitignored). The named version is NEVER rendered
to PDF or HTML, in any form.

## Repo-visibility caveat

This repository is private. If it is ever made public, the named file publishes with it —
the named file MUST be removed from history first.

## Commit-message discipline

Commit messages referencing this material never name the client ("case study v1",
nothing more).
