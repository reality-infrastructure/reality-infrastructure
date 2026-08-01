# Reality Infrastructure

A reference implementation for computing justified beliefs over contested records.

Most record systems assume their inputs agree. Real registries do not: two writers claim different splits on the same song; two deeds claim the same parcel; a licensor grants what an opt-out signal revokes. Existing infrastructure handles this by silently overwriting one claim with another, or by refusing to record the conflict at all. This engine takes the opposite position: contradiction is a first-class state, and the job of the record is to preserve it, type it, and make every conclusion drawn from it reconstructable by a stranger.

## What it does

Evidence in → typed beliefs out, with proof.

- **Ingestion** — heterogeneous evidence about claims: contracts, registry records, cryptographically signed assertions, machine-readable opt-out signals.
- **Epistemic typing (EP)** — every item is classified by its epistemic character: self-asserted, third-party attested, cryptographically signed, or statutory registry. A signature authenticates a signer, never a claim; the type system keeps that distinction load-bearing.
- **Cautious fusion** — evidence is combined under the Denœux cautious rule (Dempster–Shafer theory). Conflicting claims do not average into a false middle and do not resolve into a false winner; mass on the unresolved hypothesis is a valid, reportable, useful answer.
- **Transparency logging** — every event (grant, revocation, opt-out, term change, dispute, assertion) is committed to an append-only Merkle log in the style of RFC 9162 Certificate Transparency. Inclusion proofs make the record tamper-evident; nothing can be silently rewritten.
- **Byte-identical replay** — any belief the system has ever computed can be reconstructed deterministically from the log and verified by an independent party. The replay, not the operator's word, is the proof.

## What it is for

Any domain where claims conflict and the conflict matters:

- **Rights state** — who holds what claim on this work or this parcel today, and where is it contested. The fusion output as a queryable answer.
- **Provenance** — what was claimed, by whom, when, with what epistemic character, cryptographically bound to an append-only record.
- **Evidence** — a frozen, replayable belief object with chain of custody, exportable for proceedings where the other side must be able to check the math.
- **Compliance derivation** — disclosure documents generated from the log rather than drafted as narrative, so that the disclosure inherits the record's verifiability.

The engine is domain-general. Current worked instances include music rights events (split-sheet conflicts, licensing grants, consent revocation, machine-readable opt-outs) and land-records events (recorder filings, lien claims, tax-sale records). The log does not know which domain it is in; that is the point.

## What it does not do

Stated plainly, because the limits are part of the methodology:

- It proves what was claimed, not what is true. Garbage claims, faithfully logged, are still garbage — they are simply garbage with provenance, which is what makes them auditable.
- It is not a detector. It cannot determine whether a work was used to train a model, whether a signature's holder is honest, or whether a filed deed is forged. It fuses and preserves evidence produced by other instruments; it does not generate that evidence.
- Fusion does not launder weak evidence into strong evidence. The typed uncertainty is carried through to the output, not hidden by it.
- Evidentiary weight in any legal proceeding is a question for counsel and courts, not for this README.

## Status

Version 1.0.0, released 2026-07-31. 425 passing tests across 13 milestones. Reference implementation — the maintainer's role is the methodology and the code, not operation of a canonical production log.

## Governance

This project is governed by a neutrality covenant committed to this repository: [NEUTRALITY.md](NEUTRALITY.md). It defines, in advance of any commercial contact, which funding and revenue the project accepts and which it refuses. The covenant is part of the artifact.

## Citation

See [CITATION.cff](CITATION.cff). GitHub renders a "Cite this repository" button from it.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Technical documentation

- **/research** — IMMUTABLE artifacts: the four-stage research record (adversarial verdict,
  emergence analysis, independent derivation, Specification v0.1) and future papers.
  Never edited; corrections become new dated files.
- **/reference-implementation** — executable code conforming to the frozen SPEC.md.
  Governed by CLAUDE.md + closed contracts in /contracts. Evolves independently of research.
- **/benchmarks** — the Sybil-calibration ablation corpus and conformance benchmarks (future).
- **/experiments** — dated, disposable investigations; may be deleted.
- **/playground** — scratch. Never referenced by anything.

Roles: Research Claude (chat) owns necessity/prior-art/theorems/spec revision.
Claude Code owns implementation and treats SPEC.md as source of truth.

### Rights-event layer

- **/reference-implementation/rights_events** — first domain layer over the engine: a
  domain-neutral rights-event schema (six event types, four epistemic-provenance channel
  types), four evidence adapters (works-registration samples, C2PA manifest stores,
  TDMRep/robots.txt opt-out signals, split-conflict registration records), a pipeline that
  fuses events per contested question through the engine's cautious rule, and Merkle-logged
  belief objects with inclusion proofs.
- Replay CLI: from `reference-implementation/`, `python -m rights_events.replay --run
  RUN_FILE --subject SUBJECT` reconstructs a logged belief object and verifies byte-identity
  and inclusion proofs; `python -m rights_events.song_x` runs the layer's end-to-end
  acceptance case (a SYNTHETIC split-conflict fixture) and writes a run file.
- The identical layer, unchanged, runs a second domain: `python -m rights_events.parcels`
  folds real Cook County land records (recorded deeds, assessor roll, tax-sale results)
  into belief objects structurally identical to the music case's, verified by the same
  replay CLI with the same commands.
