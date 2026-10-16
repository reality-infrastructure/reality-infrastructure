"""Canonical JSON hashing used for input hashes, payload binding, and manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_tree(root: Path, *, exclude_dirs: tuple[str, ...] = ()) -> str:
    """Hash of every file under *root* (sorted relative path + bytes)."""
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if any(part in exclude_dirs or part == "__pycache__" for part in rel.parts):
            continue
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()
