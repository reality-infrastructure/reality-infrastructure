"""Shared fixtures for the harness engine tests.

Every test gets a fresh in-memory engine with a pinned clock and seeded ids so
runs are deterministic.  The reference pack loads once per session; tests that
need to mutate pack files work on a copy under tmp_path.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engine.config import ENGINE_ROOT
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine

PACKS_ROOT = ENGINE_ROOT / "packs"
T0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("harness-test"))
    try:
        yield eng
    finally:
        eng.close()


@pytest.fixture(scope="session")
def pack():
    return load_pack("_reference", PACKS_ROOT)


@pytest.fixture
def runner(engine, pack):
    return Runner(engine, pack)


def copy_reference_pack(dest_root: Path) -> Path:
    """Copy packs/_reference to <dest_root>/_reference (no caches, no matrices)."""
    dest = dest_root / "_reference"
    shutil.copytree(PACKS_ROOT / "_reference", dest,
                    ignore=shutil.ignore_patterns("__pycache__", "matrix-*", "crank"))
    return dest


@pytest.fixture
def pack_copy(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    copy_reference_pack(root)
    return root
