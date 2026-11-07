"""PREREG A24.1 gates on cohort 2's first graded read (the boards of 2026-11-03, window 11-04 …
11-10, read as of 2026-11-06 from the channel's parts at `c395d8f`): the six committed files
byte for byte, the run file re-verifies, the counts and the one PARTIAL row's measured
continuity. The 141 pinned gz page files (226 752 914 bytes) are NOT on this branch: their bytes
are the channel's parts, pinned page by page (sha256) in the capture and by the index sha; the
documented rebuild from the channel reproduces the capture byte for byte (A24.1). Offline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rights_events import agent_arena as runner

ARENA = runner._FIXTURES / "arena" / "2026-11-03"
AS_OF = "2026-11-06"

PINS = {
    f"capture_ARENA_2026-11-03_{AS_OF}.json": "9e62c2db536f133159fbd30d8d0f30db84a4c3f3069340e54876c5b147ebad4c",
    f"run_ARENA_2026-11-03_{AS_OF}.ri": "b813b46dfc7d4d14f6c2638c4697263080112d657ad351cc24aea1d69dcd07ef",
    f"arena_2026-11-03_{AS_OF}.json": "705a844b95e12ed9ca9cefae5f5c645e333727fc840d69f722a00c4d0975a4be",
    f"arena_2026-11-03_{AS_OF}.md": "35221f7a83c9284338482e11ae0fbedf9124c117c3be53ab238adc953956753c",
    f"arena_2026-11-03_{AS_OF}.html": "d06edf0203f133d7c6b7c6a6d547f682ed0d2caf268a52390ecf0726ef5c0894",
    f"MANIFEST_ARENA_2026-11-03_{AS_OF}.json": "1ee37d7bfe8964b877857135f0f8ca6b54af0f7d9d4e5ca844704cede3a763f1",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_the_six_files_are_pinned_byte_for_byte():
    for name, sha in PINS.items():
        assert _sha(ARENA / name) == sha, name


def test_the_run_file_reverifies_without_the_pages(capsys):
    rc = runner.main(["--verify", "--run", str(ARENA / f"run_ARENA_2026-11-03_{AS_OF}.ri")])
    out = capsys.readouterr().out
    assert rc == 0 and "RESULT: OK" in out and "reloaded 72 events" in out


def test_counts_and_the_one_partial_row_by_measured_continuity():
    a = json.loads((ARENA / f"arena_2026-11-03_{AS_OF}.json").read_text(encoding="utf-8"))
    assert a["as_of"] == AS_OF and a["window"]["started"] is True and a["window"]["complete"] is False
    assert a["counts"] == {"FULL": 27, "PARTIAL": 1, "NONE": 41, "REFUSED": 0}
    partial = [r for r in a["rows"] if r["status"] == "PARTIAL"]
    assert len(partial) == 1
    reason = partial[0]["coverage_reason"]
    assert "15 capped cycles of 58" in reason and "28827 s" in reason and "1458 s" in reason and "(R114)" in reason
    assert partial[0]["fills_served"] == 960272 and partial[0]["fills"] == 946417
    full = [r for r in a["rows"] if r["status"] == "FULL"]
    assert all("capped cycles" in r["coverage_reason"] and "(R114)" in r["coverage_reason"] for r in full)
    assert a["record_row"]["coverage"] == "NONE" and a["record_row"]["fills"] == 0 and a["record_row"]["net_with_funding"] == "0"


def test_the_capture_aligned_every_page_and_recovered_fourteen():
    cap = json.loads((ARENA / f"capture_ARENA_2026-11-03_{AS_OF}.json").read_text(encoding="utf-8"))
    al = cap["as_of"]["alignment"]
    assert al == {"files": 140, "pages": 8910, "recovered_pages": 14, "dropped_trailing_lines": 0, "files_without_index": 0}
    assert len(cap["rows"]) == 70
    assert sum(len(r["fills_pages"]) for r in cap["rows"]) == 5031
    assert sum(p["items"] for r in cap["rows"] for p in r["fills_pages"]) == 3152780
    assert all("fetched" in p for r in cap["rows"] for p in r["fills_pages"] + r["funding_pages"])
    assert sum(r["pages_recovered"] for r in cap["rows"]) == 14
    m = json.loads((ARENA / f"MANIFEST_ARENA_2026-11-03_{AS_OF}.json").read_text(encoding="utf-8"))
    gz = [f for f in m["files"] if f["name"].endswith(".jsonl.gz")]
    assert len(gz) == 140 and sum(f["bytes"] for f in m["files"]) == 226752914        # the page bytes live on the channel (F4)
    assert m["sha256"] == PINS[f"capture_ARENA_2026-11-03_{AS_OF}.json"]
