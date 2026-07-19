"""Append-only Merkle history tree with inclusion and consistency proofs.

Implements an RFC 6962-style Merkle tree over canonically serialized entries
(from ri_core.serialization).  Proof generation follows RFC 6962; verification
follows the explicit algorithms in RFC 9162 §2.1.3.2 (inclusion) and §2.1.4.2
(consistency).

Hash construction (domain-separated):
    leaf_hash   = SHA-256(0x00 || entry_bytes)
    node_hash   = SHA-256(0x01 || left || right)
    empty root  = SHA-256("")

This module imports only ri_core.serialization and stdlib.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from ri_core.serialization import encode

# ---------------------------------------------------------------------------
# Domain-separated hash primitives
# ---------------------------------------------------------------------------

_LEAF_PREFIX = b'\x00'
_NODE_PREFIX = b'\x01'
_EMPTY_ROOT = hashlib.sha256(b'').digest()


def leaf_hash(entry_bytes: bytes) -> bytes:
    """SHA-256(0x00 || entry_bytes).  Domain-separated leaf hash."""
    return hashlib.sha256(_LEAF_PREFIX + entry_bytes).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """SHA-256(0x01 || left || right).  Domain-separated internal node hash."""
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()


# ---------------------------------------------------------------------------
# Proof dataclasses (frozen / immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InclusionProof:
    """Proof that a leaf is included at *index* in a tree of *tree_size*."""
    index: int
    tree_size: int
    leaf_hash: bytes
    hashes: tuple[bytes, ...]
    root_hash: bytes


@dataclass(frozen=True)
class ConsistencyProof:
    """Proof that tree at *old_size* is a prefix of tree at *new_size*."""
    old_size: int
    new_size: int
    old_root: bytes
    new_root: bytes
    hashes: tuple[bytes, ...]


# ---------------------------------------------------------------------------
# RFC 6962 split point
# ---------------------------------------------------------------------------

def _split(n: int) -> int:
    """Largest power of 2 strictly less than *n* (RFC 6962 §2.1).

    k = 1 << ((n - 1).bit_length() - 1)
    """
    assert n > 1
    return 1 << ((n - 1).bit_length() - 1)


# ---------------------------------------------------------------------------
# Merkle tree hash (recursive, RFC 6962 §2.1)
# ---------------------------------------------------------------------------

def _mth(hashes: Sequence[bytes]) -> bytes:
    """Compute Merkle Tree Hash over a sequence of leaf hashes."""
    n = len(hashes)
    if n == 0:
        return _EMPTY_ROOT
    if n == 1:
        return hashes[0]
    k = _split(n)
    return node_hash(_mth(hashes[:k]), _mth(hashes[k:]))


# ---------------------------------------------------------------------------
# Proof generation (RFC 6962 §2.1.1 inclusion, §2.1.2 consistency)
# ---------------------------------------------------------------------------

def _inclusion_path(index: int, hashes: Sequence[bytes]) -> list[bytes]:
    """Return the audit path (sibling hashes, leaf-to-root) for *index*."""
    n = len(hashes)
    if n == 1:
        return []
    k = _split(n)
    if index < k:
        path = _inclusion_path(index, hashes[:k])
        path.append(_mth(hashes[k:]))
    else:
        path = _inclusion_path(index - k, hashes[k:])
        path.append(_mth(hashes[:k]))
    return path


def _consistency_path(old_size: int, new_hashes: Sequence[bytes],
                      start_from_old: bool) -> list[bytes]:
    """Return consistency proof hashes (RFC 6962 §2.1.2 SUBPROOF)."""
    n = len(new_hashes)
    if old_size == n:
        if start_from_old:
            return []
        return [_mth(new_hashes)]
    if old_size == 0:
        # Empty old tree is trivially consistent.
        return []
    k = _split(n)
    if old_size <= k:
        path = _consistency_path(old_size, new_hashes[:k], start_from_old)
        path.append(_mth(new_hashes[k:]))
    else:
        path = _consistency_path(old_size - k, new_hashes[k:], False)
        path.append(_mth(new_hashes[:k]))
    return path


# ---------------------------------------------------------------------------
# Verification — RFC 9162 §2.1.3.2 (inclusion) and §2.1.4.2 (consistency)
# ---------------------------------------------------------------------------

def verify_inclusion(
    leaf_hash_val: bytes,
    index: int,
    tree_size: int,
    proof_hashes: Sequence[bytes],
    expected_root: bytes,
) -> bool:
    """Verify an inclusion proof per RFC 9162 §2.1.3.2.

    Uses the fn/sn index-walking algorithm.  Pure function — needs no Log.
    """
    if tree_size <= 0 or index >= tree_size:
        return False
    fn = index
    sn = tree_size - 1
    r = leaf_hash_val

    for p in proof_hashes:
        if sn == 0:
            return False  # more hashes than the tree depth allows
        if fn & 1 == 1 or fn == sn:
            r = node_hash(p, r)
            while fn & 1 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1

    return sn == 0 and r == expected_root


def verify_consistency(
    old_size: int,
    new_size: int,
    old_root: bytes,
    new_root: bytes,
    proof_hashes: Sequence[bytes],
) -> bool:
    """Verify a consistency proof per RFC 9162 §2.1.4.2.

    Uses the fn/sn index-walking algorithm.  Pure function — needs no Log.
    """
    if old_size == 0:
        # Empty old tree is trivially consistent with anything.
        return old_root == _EMPTY_ROOT
    if old_size == new_size:
        return len(proof_hashes) == 0 and old_root == new_root
    if old_size > new_size or new_size == 0:
        return False

    proof = list(proof_hashes)
    if not proof:
        return False

    # Determine starting point.
    # If old_size is a power of 2, the first hash IS the old root.
    if old_size & (old_size - 1) == 0:  # power of 2
        # Prepend old_root as implicit first element per RFC 9162
        proof.insert(0, old_root)

    fn = old_size - 1
    sn = new_size - 1

    # Remove the left-most set bits shared by fn and sn.
    while fn & 1 == 1:
        fn >>= 1
        sn >>= 1

    fr = proof[0]
    sr = proof[0]

    for p in proof[1:]:
        if sn == 0:
            return False
        if fn & 1 == 1 or fn == sn:
            fr = node_hash(p, fr)
            sr = node_hash(p, sr)
            while fn & 1 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            sr = node_hash(sr, p)
        fn >>= 1
        sn >>= 1

    return sn == 0 and fr == old_root and sr == new_root


# ---------------------------------------------------------------------------
# EvidenceLog — append-only Merkle history tree
# ---------------------------------------------------------------------------

class EvidenceLog:
    """Append-only Merkle history tree over canonically serialized entries.

    Entries are serialized via ``ri_core.serialization.encode`` on append,
    then hashed into a RFC 6962-style Merkle tree.  No method modifies or
    deletes an existing entry.
    """

    __slots__ = ('_entries', '_leaf_hashes')

    def __init__(self) -> None:
        self._entries: list[bytes] = []
        self._leaf_hashes: list[bytes] = []

    def __len__(self) -> int:
        return len(self._entries)

    def append(self, obj) -> int:
        """Serialize *obj*, compute leaf hash, store immutably.

        Returns the 0-based index of the new entry.
        """
        entry_bytes = encode(obj)
        lh = leaf_hash(entry_bytes)
        idx = len(self._entries)
        self._entries.append(entry_bytes)
        self._leaf_hashes.append(lh)
        return idx

    def entry(self, index: int) -> bytes:
        """Return the canonical bytes of the entry at *index*."""
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Entry index {index} out of range [0, {len(self._entries)})")
        return self._entries[index]

    def root(self, tree_size: int | None = None) -> bytes:
        """Merkle root hash at *tree_size* (default: current size)."""
        if tree_size is None:
            tree_size = len(self._leaf_hashes)
        if tree_size < 0 or tree_size > len(self._leaf_hashes):
            raise ValueError(
                f"tree_size {tree_size} out of range [0, {len(self._leaf_hashes)}]"
            )
        return _mth(self._leaf_hashes[:tree_size])

    def inclusion_proof(
        self, index: int, tree_size: int | None = None
    ) -> InclusionProof:
        """Audit path proving entry[index] is in the tree at *tree_size*."""
        if tree_size is None:
            tree_size = len(self._leaf_hashes)
        if tree_size < 1 or tree_size > len(self._leaf_hashes):
            raise ValueError(
                f"tree_size {tree_size} out of range [1, {len(self._leaf_hashes)}]"
            )
        if index < 0 or index >= tree_size:
            raise ValueError(
                f"index {index} out of range [0, {tree_size})"
            )
        hashes = _inclusion_path(index, self._leaf_hashes[:tree_size])
        return InclusionProof(
            index=index,
            tree_size=tree_size,
            leaf_hash=self._leaf_hashes[index],
            hashes=tuple(hashes),
            root_hash=self.root(tree_size),
        )

    def consistency_proof(
        self, old_size: int, new_size: int | None = None
    ) -> ConsistencyProof:
        """Proof that tree at *old_size* is a prefix of tree at *new_size*."""
        if new_size is None:
            new_size = len(self._leaf_hashes)
        if old_size < 0 or old_size > new_size:
            raise ValueError(
                f"old_size {old_size} out of range [0, {new_size}]"
            )
        if new_size > len(self._leaf_hashes):
            raise ValueError(
                f"new_size {new_size} out of range [0, {len(self._leaf_hashes)}]"
            )
        if old_size == 0 or old_size == new_size:
            hashes: list[bytes] = []
        else:
            hashes = _consistency_path(
                old_size, self._leaf_hashes[:new_size], True
            )
        return ConsistencyProof(
            old_size=old_size,
            new_size=new_size,
            old_root=self.root(old_size),
            new_root=self.root(new_size),
            hashes=tuple(hashes),
        )
