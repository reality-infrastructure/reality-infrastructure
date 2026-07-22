# SPEC v0.2 Findings — Deferred from M-RI-08

Two limitations identified during M-RI-08 (replay + counterfactual) that
require SPEC-level changes to resolve.  Neither blocks v0.1 conformance;
both are documented in ri_core/replay.py's module docstring.

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
