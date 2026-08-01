# Verifiable Records of Contested Claims: Methodology

Reality Infrastructure methodology note. Dated 2026-08-01. Version 1.4.0. The canonical source of this note is `METHODOLOGY.md` at the root of [the repository](https://github.com/reality-infrastructure/reality-infrastructure); the site's methodology page is rendered from it. The method described here is implemented in the repository, exercised by its test suite, and demonstrated by [the four views](https://reality-infrastructure.github.io/reality-infrastructure/), which are generated from the implementation's own run artifacts.

## 1. The verification gap

A disclosure regime has a verification gap when the disclosed document cannot be checked, at the level of its content, against the records it summarizes by anyone other than the discloser. The disclosure may be honest. The gap is that nothing in the instrument lets a third party establish that it is.

The public summary of training content required by Article 53(1)(d) of the EU AI Act is the motivating instance. The European Commission's AI Office adopted a template for this summary on 24 July 2025. The template standardizes a document that the provider completes and publishes: identification of the provider and model, a categorized list of data sources, and a description of processing aspects including the handling of text-and-data-mining reservations. The instrument standardizes the format of a self-declaration. It does not provide a mechanism by which a third party can verify the summary's correspondence to the training corpus it describes. That is an observation about the structure of the document class, not about the intentions of any provider or the drafting of the template.

C2PA is the adjacent instance. The C2PA specifications bind signed provenance metadata to digital assets, and the specification's own explainer states the boundary plainly: provenance information alone cannot tell you whether the digital content is true, accurate or factual. A valid C2PA signature establishes that specific metadata was signed by the holder of a specific key and has not been altered since signing. It authenticates a signer and preserves integrity. It does not establish the truth of what was signed.

The record that contested-claim systems fail at scale predates any question about AI. Under the US Music Modernization Act, twenty digital service providers transferred 424,384,787 dollars in accrued historical unmatched royalties to the Mechanical Licensing Collective in February 2021 — mechanical royalties that had accumulated because the ownership of the underlying musical works could not be established from the available records. Conflicting registrations, incomplete chains, and unverifiable claims produced a nine-figure backlog in a mature industry with statutory infrastructure.

What these instances share is a missing primitive: a way to record contested claims such that every conclusion drawn from them can be re-derived and checked by a stranger. The remainder of this note describes one method for supplying that primitive. It describes a method, not a solution to the disputes themselves. The difference the primitive makes is rendered directly on the [derived-disclosure view](https://reality-infrastructure.github.io/reality-infrastructure/disclosure/index.html): a summary in the structure of the Article 53 template, generated from a logged corpus with an event reference on every line, beside the same facts as drafted prose with none.

## 2. Evidence typing (EP)

Every evidence item entering the system carries one of four epistemic-provenance channel types.

- Self-asserted: a party speaks about its own affairs through its own channel. A robots.txt reservation, an operator's inventory record.
- Third-party attested: a party's claim transmitted through a channel that logs it. A registration filed with a collecting society.
- Cryptographically signed: an assertion bound to a signer by a verifiable signature. A C2PA manifest.
- Statutory registry: a record of a register established by law. A recorded deed, an assessor roll entry, a tax-sale result.

The channel type is provenance metadata, and the design requirement is that it survives fusion. Each belief object the system emits lists its contributing events with their channel types and their standing, so a reader can always decompose a conclusion into which kinds of evidence support it. A type system that is consumed during processing and absent from the output would decorate the input and prove nothing about the conclusion.

The boundary between the signed channel and the others is the signature principle, carried unchanged from the repository's own description of the system: "A signature authenticates a signer, never a claim." The system records the signing event — who signed what, when, under which certificate — as a fact with high evidential weight. The truth of the signed content is untouched by that fact, and the implementation's C2PA adapter states this in its own documentation. Standing survives alongside type: when a logged claim is later revoked, the claim and the revocation both remain in the record, and the belief object lists the claim with revoked standing rather than deleting it.

The mapping from channel types to fusion inputs is declared policy, not derived mathematics. The policy module (`reference-implementation/rights_events/policy.py`) assigns each channel a mass toward its claimed hypothesis — 0.6 statutory, 0.55 signed, 0.45 attested, 0.3 self-asserted — and maps channels onto a closed uncertainty vocabulary. The two assertion channels sit deliberately below 0.5 so that a single uncorroborated assertion can never outweigh ignorance on a contested question. Changing these values is a policy change under the repository's amendment discipline: a tagged commit with written rationale. The numbers are inspectable priors, and the method's guarantees do not depend on them being optimal — only on them being declared, fixed, and carried into the replayable record.

## 3. Contradiction preservation

The fusion layer operates on Dempster–Shafer belief structures: mass assigned to subsets of a frame of hypotheses, including the full frame. Mass on the full frame — written Ω, and rendered as "unresolved" throughout the implementation — is ignorance: weight the evidence does not discriminate among hypotheses. It is a first-class answer, not a residual.

Evidence combines under the cautious rule of Denœux (2008): a conjunctive combination that is commutative, associative, and idempotent. Idempotence is the operative property for evidence pipelines, where independence cannot be assumed: the same registry record ingested twice, or fourteen reservation signals published by one site operator, combine to exactly what one of them establishes. Rules that assume distinct evidence double-count under those conditions.

The combination is unnormalized. When evidence conflicts, mass accumulates on the empty set, and the system reports it as conflict rather than normalizing it away. Normalization redistributes conflict onto the surviving hypotheses, which on heavily contested inputs manufactures confidence that the records do not contain. Here the conflict mass is a headline output: it is the measured size of the disagreement in the record.

Registries that maintain a single canonical current value must resolve contested inputs at write time, and the resolution is invisible in the output. This method's output is instead a belief object: every competing hypothesis with its mass, the conflict mass, the unresolved mass, and the contributing events with their types and standing.

Two worked examples run live, one per domain, through identical machinery.

- [Song X](https://reality-infrastructure.github.io/reality-infrastructure/rights-state/song-x.html), a labeled synthetic split-sheet conflict: two third-party-attested registrations assert 60/40 and 50/50 shares. Fusion yields 0.2475 on each registration's hypothesis, 0.2025 conflict, and 0.3025 unresolved — ignorance honestly dominates every singleton, because two uncorroborated attestations cannot settle a contested question. After the second registrant's logged revocation, the fold yields 0.45 on the remaining hypothesis and 0.55 unresolved: the record changed, so the belief changed, and both states replay.
- [Cook County parcel 29-02-408-053-0000](https://reality-infrastructure.github.io/reality-infrastructure/rights-state/parcel-29024080530000.html), real public records: five grantees of record never later divested of record, drawn from statutory sources. Fusion yields 0.01536 on each of the five claims, 0.01024 unresolved, and 0.91296 conflict. Five authentic records naming five different parties is a records problem, and the number states its size. Throughout, competing entries mean that the cited records disagree; nothing in the record or its rendering characterizes any person.

## 4. The replay guarantee

Every event is committed to an append-only Merkle log in the style of RFC 9162 Certificate Transparency: domain-separated leaf and interior hashing, a root that commits to the entire sequence, and an inclusion proof for every entry. The logs behind the live views hold every event shown, and the [provenance explorer](https://reality-infrastructure.github.io/reality-infrastructure/provenance/parcels.html) displays each event's full proof — leaf hash, audit path, root — beside the event itself, for both domains through the same table.

Serialization is canonical and deterministic: one byte encoding with sorted keys, no floating-point values (fixed-point decimal strings), and a format version byte. A belief object's bytes are a pure function of the logged events and the declared policy — no wall-clock reads, no ordering luck, no locale.

Together these yield the verification primitive: byte-identical replay. A stranger downloads a run artifact from the [evidence page](https://reality-infrastructure.github.io/reality-infrastructure/evidence/index.html), which lists each artifact with its SHA-256 checksum, clones the repository, and runs the documented command (`python -m rights_events.replay --run ARTIFACT --subject SUBJECT`). The tool rebuilds the logs, re-verifies every event, re-derives the belief object from the events and the policy, and compares the result byte for byte against the stored serialization, along with the Merkle root and every inclusion proof. All checks pass with exit code 0. Altering any signed event or any stored belief makes the same command exit nonzero. The conclusion is reproduced from the record, not accepted from the operator.

Tamper-evidence establishes that the record was not altered after commitment and that every displayed conclusion follows mechanically from that record under the declared policy. Two boundaries apply. First, it establishes nothing about the truth of the recorded claims; that boundary is Section 5's subject. Second, the reference implementation signs events with HMAC under a local trust authority: attribution holds within that declared trust model and is not third-party non-repudiation. The identity interface admits public-key substitution, but this implementation does not claim that property.

## 5. Limits, stated plainly

The limits are part of the method. A reader who needs this section weakened should not cite this note.

- It proves what was claimed, not what is true. Garbage claims, faithfully logged, are still garbage — they are garbage with provenance, which is what makes them auditable. A replayed belief object demonstrates that a conclusion follows from the recorded claims under the declared policy; it cannot upgrade the claims themselves.
- It is not a detector. It cannot determine whether a work was used to train a model, whether a signature's holder is honest, or whether a filed deed is forged. It fuses and preserves evidence produced by other instruments; it does not generate that evidence. A disclosure derived from this system is verifiable against the log — never against the world.
- Fusion does not launder weak evidence into strong evidence. The typed uncertainty is carried through to the output, not hidden by it. A self-asserted claim enters at its declared weight and is visible as self-asserted in every conclusion it touches.
- Evidentiary standing is undetermined here. Whether a replayable belief object satisfies authentication requirements in the class of Federal Rules of Evidence 901 and 902, and whether the method's outputs would survive reliability challenges in the class of Daubert, are open questions for qualified counsel and for courts. This note asserts no conclusion in either direction.
- The demonstration has a disclosed gap. The revocation fold — the mechanism by which a later event withdraws an earlier claim — is proven by test in the music domain. Its land-records instance, a tax-sale redemption, is not demonstrated: as of 2026-08-01 no real redemption record was reachable, because Cook County redemption records are request-based Clerk documents and the Clerk's online search was unavailable at the time of retrieval. The mechanism requires no new code; a single real Estimate of Redemption converts the gap to a demonstrated case with a fixture addition. The gap is disclosed because a methodology note that conceals its own demonstration's gap fails the standard it proposes.

The method's claim is narrow: contested claims can be recorded with typed provenance, fused without erasing their contradictions, and replayed byte for byte by a stranger. Everything beyond that narrow claim belongs to the instruments that produce evidence, the counsel and courts that weigh it, and the institutions that would operate such records.

## References

- Thierry Denœux, "Conjunctive and disjunctive combination of belief functions induced by nondistinct bodies of evidence," Artificial Intelligence 172(2–3):234–264, 2008. [Record](https://philpapers.org/rec/DENCAD)
- RFC 9162, "Certificate Transparency Version 2.0," IETF, 2021. [Text](https://www.rfc-editor.org/rfc/rfc9162)
- EU AI Act, Article 53. [Public text](https://artificialintelligenceact.eu/article/53/)
- European Commission, adoption of the Template for the Public Summary of Training Content, 24 July 2025. [Adoption record](https://digitalpolicyalert.org/event/32126-european-commission-adopted-template-for-the-public-summary-of-training-content-for-general-purpose-artificial-intelligence-models); [independent analysis](https://openfuture.eu/blog/a-step-forward-but-not-far-enough-the-eus-ai-transparency-template/)
- C2PA and Content Credentials Explainer, C2PA Specifications. [Explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)
- The Mechanical Licensing Collective, "The MLC Receives $424 Million in Historical Unmatched Royalties from DSPs," February 2021. [Announcement](https://blog.themlc.com/press/mechanical-licensing-collective-receives-424-million-historical-unmatched-royalties-digital)
