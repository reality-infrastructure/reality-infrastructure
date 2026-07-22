# SPEC v0.2 Findings

Three limitations identified during M-RI-08 and M-RI-10 that require
SPEC-level changes to resolve.  None blocks v0.1 conformance; findings
1–2 are documented in ri_core/replay.py's module docstring, finding 3 in
the M-RI-10 contract closeout.

---

## 1. Identity-link events as logged first-class evidence

**Limitation.**  Shared-provenance declarations (`link_identities`) live
exclusively in the `LocalAuthority` object's in-memory union-find structure.
They are never serialized to the evidence log.  Consequently, `replay()`
cannot reconstruct the authority's link state from log bytes alone — it
requires the caller to supply a pre-configured authority with the correct
link topology.  Two replayers holding the same log but different authority
objects may produce different justification structures (different provenance
equivalence classes), even though the fused belief values are identical by
the idempotence property of cautious fusion.

**Consequence.**  The SPEC §6 goal that replay is fully determined by the
serialized log is only partially met: belief values are log-determined, but
justification terms (which include provenance-class partitions) depend on
authority-side state that is not in the log.  This also means the §14
mandatory interoperability test — "two independent implementations, same
serialized log ⇒ byte-identical belief state and identical justification
terms" — cannot be satisfied unless both implementations are given the same
link state out-of-band.

**Proposed spec change.**  Introduce a new logged entry kind
`identity_link` with fields `{kind: "identity_link", id_a, id_b, ltime}`.
`link_identities()` would append this record to the evidence log (analogous
to how `rule_version` records are logged per §11).  Replay would process
`identity_link` entries in log order, calling `authority.link_identities()`
for each.  The authority supplied to replay would then only need issued
identities, not pre-configured links.

---

## 2. Public-key signature profile (Ed25519) for third-party-verifiable replay

**Limitation.**  The v0.1 identity anchor uses HMAC-SHA256, a symmetric-key
MAC.  Verification requires possession of the same secret key used for
signing.  A replayer without the original authority's key store cannot
independently verify observation signatures — it must be given (or trust) the
original `LocalAuthority` object.  This means replay's signature
re-verification step is meaningful only within the same trust boundary that
produced the original log.  A third party receiving an exported log has no
way to confirm that signatures are valid without also receiving the secret
key material, which would allow that party to forge new signatures.

**Consequence.**  SPEC §4's requirement that observations are
"cryptographically bound via sig" is satisfied locally but not in any
distributed or adversarial setting.  The §14 interoperability test between
independent implementations is viable only if both share the anchor's key
store, which contradicts the spirit of independent verification.  Replay
across trust boundaries — the natural use case for counterfactual analysis
by auditors or counterparties — is not cryptographically meaningful under
HMAC.

**Proposed spec change.**  Define an `Ed25519Authority` profile as a
SPEC-level alternative to the local HMAC model.  Public keys would be
logged as `identity_issued` entries (tied to finding 1 above).  Signature
verification would use only the public key, making it possible for any
party with the log to re-verify every observation without secret material.
The `LocalAuthority` HMAC profile would remain valid for single-trust-root
deployments; the spec would require that the signature scheme is declared
in a log preamble entry so replayers know which verification path to use.

---

## 3. Open observation schema: signed bytes include unknown fields

**Limitation.**  `_unsigned_bytes()` (`project.py:62-65`) constructs the
signing input as `{k: v for k, v in obs.items() if k != "sig"}` — every
top-level key except `sig` is included in the HMAC input.  `submit()`
(`project.py:87-88`) checks only that the required fields are present
(`_REQUIRED_OBS_FIELDS`); it does not reject unknown extra fields.
Consequently, any caller-supplied extra top-level fields are silently
signed, logged, and accessible to verification rules via
`["field", "extra_key"]`.

**Discovery.**  During M-RI-10 Plan Gate, a reviewer flagged the opposite
assumption — that extra metadata fields would be *outside* the signed
bytes (based on the M-RI-07 Plan Gate description, which implied a
fixed-key schema).  Reading the implementation revealed the schema is
open: extra fields are signed.  The Plan-Gate description and the
implementation disagree on signing scope.

**Consequence.**  The open schema is not inherently wrong — it provides
extensibility (e.g., domain-specific metadata that rules can gate on).
However, (a) the SPEC does not declare whether the observation schema is
open or closed, so the signing scope is an implementation detail rather
than spec text; (b) the M-RI-07 Plan Gate description created a false
assumption that was only caught by reading the code; (c) a closed-schema
implementation would silently produce different HMAC values for the same
logical observation, breaking interoperability.

**Proposed spec change.**  Explicitly specify the observation schema
policy in SPEC §4.  Two options:

- **Open schema (recommended):** Document that the signing input is all
  non-sig fields, sorted canonically.  Extra fields are signed, logged,
  and rule-accessible.  This preserves v0.1 behavior and enables
  domain-specific metadata.
- **Closed schema:** Enumerate the allowed top-level keys.  `submit()`
  rejects observations with extra fields.  Simpler interoperability
  guarantees but less extensible.

Either way, the signing scope must be spec text, not implementation
detail — this is a load-bearing interoperability property.
