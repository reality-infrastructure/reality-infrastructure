"""Identity-anchor interface realizing axiom A1 (bounded Sybil cost).

Provides:
- Identity: frozen dataclass representing an anchor-issued identity
- LocalAuthority: local trust-root implementation with HMAC-SHA256 signatures,
  union-find shared-provenance tracking, and explicit Sybil-cost accounting

Signature scheme: HMAC-SHA256 (stdlib hmac)
-----------------------------------------------
This is a reference implementation using symmetric-key MACs, not public-key
digital signatures.  The trust implications:

+-------------------------+----------------------+-----------------------+
| Property                | HMAC-SHA256          | Ed25519 (future)      |
+-------------------------+----------------------+-----------------------+
| Who can sign            | anyone with the key  | only private-key holder|
| Who can verify          | anyone with the key  | anyone with public key|
| Non-repudiation         | No (verifier forges) | Yes                   |
| Third-party verifiable  | No (needs key store) | Yes                   |
+-------------------------+----------------------+-----------------------+

HMAC is cryptographically sound for integrity and identity binding within the
LocalAuthority trust model (the anchor is the sole verifier).  It satisfies
SPEC section 4 "cryptographically bound via sig" in the local-trust-root context.
For distributed or adversarial settings, swap in an Ed25519Authority -- the
interface is designed so this requires no changes above the identity layer.

Key derivation (domain-separated per amendment A3)::

    key = HMAC-SHA256(seed, anchor_id_bytes || 0x00 || identity_id_bytes)

Two anchors sharing a seed but with different anchor_id will produce different
keys for the same identity name, and the 0x00 separator prevents concatenation
ambiguity.

This module imports only stdlib (hashlib, hmac, dataclasses).
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
from dataclasses import dataclass


class IdentityError(Exception):
    """Error in identity operations.

    Raised for: signing with an unissued identity, issuing a duplicate
    identity, or linking an unknown identity.
    """


@dataclass(frozen=True)
class Identity:
    """An anchor-issued source identity.  Immutable.  Carries no secret."""
    identity_id: str
    anchor_id: str
    name: str


class LocalAuthority:
    """Local trust-root identity anchor with HMAC-SHA256 signatures.

    Manages identity issuance, signing/verification, shared-provenance
    tracking (union-find), and Sybil-cost accounting (kappa knob).
    """

    __slots__ = (
        '_anchor_id', '_seed', '_kappa', '_identities', '_keys',
        '_parent', '_rank', '_issued_count',
    )

    def __init__(
        self, *, anchor_id: str = 'local', seed: bytes = b'', kappa: int = 1,
    ) -> None:
        if isinstance(kappa, bool) or not isinstance(kappa, int):
            raise TypeError(f"kappa must be int, got {type(kappa).__name__}")
        if kappa < 1:
            raise ValueError(f"kappa must be >= 1, got {kappa}")
        self._anchor_id = anchor_id
        self._seed = seed
        self._kappa = kappa
        self._identities: dict[str, Identity] = {}
        self._keys: dict[str, bytes] = {}
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}
        self._issued_count = 0

    @property
    def anchor_id(self) -> str:
        """This anchor's identifier."""
        return self._anchor_id

    @property
    def kappa(self) -> int:
        """Per-identity issuance cost (the A1 knob)."""
        return self._kappa

    def issue_identity(self, name: str) -> Identity:
        """Issue a new identity bound to this anchor.

        Raises IdentityError if *name* collides with an already-issued
        identity (amendment A2).  Increments cumulative Sybil cost by kappa.
        """
        if name in self._identities:
            raise IdentityError(f"Identity already issued: {name!r}")
        identity = Identity(
            identity_id=name, anchor_id=self._anchor_id, name=name,
        )
        # Key derivation with domain separation (amendment A3):
        # HMAC-SHA256(seed, anchor_id || 0x00 || identity_id)
        key_input = (
            self._anchor_id.encode('utf-8')
            + b'\x00'
            + name.encode('utf-8')
        )
        key = _hmac.new(self._seed, key_input, hashlib.sha256).digest()
        self._identities[name] = identity
        self._keys[name] = key
        self._parent[name] = name
        self._rank[name] = 0
        self._issued_count += 1
        return identity

    def cumulative_cost(self) -> int:
        """Total Sybil cost = kappa * n_issued.  Monotonically increasing."""
        return self._kappa * self._issued_count

    def sign(self, identity: Identity, entry_bytes: bytes) -> bytes:
        """HMAC-SHA256(identity_key, entry_bytes).  Returns 32-byte sig.

        Raises IdentityError if *identity* was not issued by this anchor
        (amendment A1 — signing with unknown identity is a caller bug).
        """
        if identity.identity_id not in self._keys:
            raise IdentityError(
                f"Cannot sign: identity {identity.identity_id!r} not issued "
                f"by this anchor"
            )
        key = self._keys[identity.identity_id]
        return _hmac.new(key, entry_bytes, hashlib.sha256).digest()

    def verify(
        self, identity: Identity, entry_bytes: bytes, sig: bytes,
    ) -> bool:
        """Verify HMAC signature.  Timing-safe via hmac.compare_digest.

        Returns False (does not raise) if *identity* is unknown to this
        anchor (amendment A1 — verifying adversarial input is normal).
        """
        if identity.identity_id not in self._keys:
            return False
        key = self._keys[identity.identity_id]
        expected = _hmac.new(key, entry_bytes, hashlib.sha256).digest()
        return _hmac.compare_digest(expected, sig)

    # ── Shared-provenance (union-find) ──────────────────────────────

    def link_identities(self, id_a: Identity, id_b: Identity) -> None:
        """Declare shared provenance between id_a and id_b.  Append-only.

        Raises IdentityError if either identity was not issued by this anchor.
        """
        for ident in (id_a, id_b):
            if ident.identity_id not in self._parent:
                raise IdentityError(
                    f"Cannot link: identity {ident.identity_id!r} not issued "
                    f"by this anchor"
                )
        self._union(id_a.identity_id, id_b.identity_id)

    def shared_provenance(self, id_a: Identity, id_b: Identity) -> bool:
        """True iff id_a and id_b are in the same equivalence class.

        Returns False if either identity is unknown to this anchor.
        Equivalence relation: reflexive, symmetric, transitive.
        """
        if id_a.identity_id not in self._parent:
            return False
        if id_b.identity_id not in self._parent:
            return False
        return self._find(id_a.identity_id) == self._find(id_b.identity_id)

    # ── Union-find internals ────────────────────────────────────────

    def _find(self, identity_id: str) -> str:
        """Find root of equivalence class with path compression."""
        root = identity_id
        while self._parent[root] != root:
            root = self._parent[root]
        current = identity_id
        while self._parent[current] != root:
            next_p = self._parent[current]
            self._parent[current] = root
            current = next_p
        return root

    def _union(self, id_a: str, id_b: str) -> None:
        """Union by rank."""
        root_a = self._find(id_a)
        root_b = self._find(id_b)
        if root_a == root_b:
            return
        if self._rank[root_a] < self._rank[root_b]:
            self._parent[root_a] = root_b
        elif self._rank[root_a] > self._rank[root_b]:
            self._parent[root_b] = root_a
        else:
            self._parent[root_b] = root_a
            self._rank[root_a] += 1
