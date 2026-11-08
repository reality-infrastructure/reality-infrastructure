"""PREREG A34: the two documents ratified on the operator's word on 2026-11-08 — SETTLED_SOLANA.md (A32/R133)
and SETTLED_CENSUS.md (A30/R129). From their ratification lines on, their sha256 are frozen-file gates: no
session edits them; a change is a new document with a new name and a new ratification. Offline.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rights_events import agent_arena as runner

DOCS = Path(runner.__file__).resolve().parents[1] / "contracts" / "agent_record"
FROZEN = {
    "SETTLED_SOLANA.md": "b99d88ec0a67f59c3c30b61a7fb4a778f7c68b5f2b9fd4507256b7e1234e4fb7",
    "SETTLED_CENSUS.md": "af76778b7325b85933881a0158f9e587465f80644613017f4d5d67f8c963150f",
}
RATIFIED = 'ratified 2026-11-08 (the operator, in session at 06:1xZ: "Use the three transcripts verbatim to sign the following:'


def _lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.parametrize("name,sha", sorted(FROZEN.items()))
def test_document_is_frozen_at_its_ratified_sha(name, sha):
    assert hashlib.sha256(_lf(DOCS / name)).hexdigest() == sha


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_document_is_ratified_by_the_operator_on_its_last_line(name):
    text = _lf(DOCS / name).decode("utf-8")
    last = text.rstrip("\n").splitlines()[-1]
    assert last.startswith(RATIFIED)
    assert "DRAFT — not ratified" not in text
    assert "The machine never edits this document. The operator may." in text


def test_census_is_never_a_settled_outcome():
    text = _lf(DOCS / "SETTLED_CENSUS.md").decode("utf-8")
    assert "never a settled outcome under SETTLED.md" in text and "CENSUS-WHOLE" in text and "CENSUS-CUT" in text
    assert "never ranked with arena rows" in text
