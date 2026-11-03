"""PREREG A18.1 / A18.2 gates on THE ARENA's real pins: the captures of cohort 1 (the
10-25 boards, 80 addresses + the operator, window 2026-10-26 … 11-02) and cohort 2 (the
boards of 2026-11-03, window 11-04 … 11-10), their run files and rendered pages, byte for
byte; the known answer (the operator's RECORD row from its own pinned pages); the counts;
the committed run file re-verifies and equals a fresh build. Offline; nothing here reads the
network or the clock. Later arena days ADD files under arena/<cohort>/; these pins never move.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import GRADER_CLAIMANT, STATUS_FULL

ARENA = runner._FIXTURES / "arena"
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
C1, C2 = "2026-10-25", "2026-11-03"
AS_OF = "2026-11-03"
C1_ROOT = "dda593db906690aaad9359f8df070455f41a7d1cac2b3a2658f462582ce9c1c3"
C2_ROOT = "3e23db83c08e3c1360d5e7a71c92e87d472a1820348ac4b4a3fd8fd8a12b5e4f"

PINS = {
    # A18.1 — the captures
    f"{C1}/capture_ARENA_{C1}_{AS_OF}.json": "1471de788d474bae26b47ef176afb7e31c66b8596d8765fd9a112fe7d0514016",
    f"{C1}/MANIFEST_ARENA_{C1}_{AS_OF}.json": "252f37417cfa3df1426b2e44f140dc7692e9411832be7472579aee4eb5ba625b",
    f"{C2}/capture_ARENA_{C2}_{C2}.json": "19c1cc1f0d3dc60a74d493084c3f0fef372d6ace5472cf6f86f7755bfa04185b",
    f"{C2}/MANIFEST_ARENA_{C2}_{C2}.json": "2ed3b4a327c1efc9c142bbab1d5a826dd1be779109673c9900a29df408cc760d",
    f"{C2}/gdex_hl_top_traders_by_pnl_{C2}.json": "0cd4bb5f0bb4a73a655e97b1324bfc48986df876a2fa05537417bcdc56b9650c",
    # A18.2 — the runs and the pages (pure functions of the pins above)
    f"{C1}/run_ARENA_{C1}_{AS_OF}.ri": "27c9898a33d9d6a15eafe156a72959e888f6667fa75040f514436d290a5002b5",
    f"{C1}/arena_{C1}_{AS_OF}.json": "94710e8d01bd85cab09e86cbbbdcab4f4eb830e5b081a13d53d56fbde3061619",
    f"{C1}/arena_{C1}_{AS_OF}.md": "1f155f3f0ec8053bf120db23fb06d6d41ce53fdb9e173c2dbe5edae3e5a4ad9d",
    f"{C1}/arena_{C1}_{AS_OF}.html": "870f5d83f3a190734c4f471f51ce1f84faaa1e60b60ec3d790001329d00d6a26",
    f"{C2}/run_ARENA_{C2}_{C2}.ri": "8c3ec86cee48af10289f1bc0b5118cb8439ade4e39520f017ddfbe077fc086c6",
    f"{C2}/arena_{C2}_{C2}.json": "b81ff9bcf975e9921baefd4f625c7906129ce3d7388856e954182d16b952bde1",
}


def _lf_sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix not in (".ri", ".gz"):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_arena_pinned_inputs_and_outputs_unchanged(name, sha):
    assert _lf_sha(ARENA / name) == sha


def test_every_page_file_of_cohort_1_hashes_to_its_manifest():
    man = json.loads((ARENA / C1 / f"MANIFEST_ARENA_{C1}_{AS_OF}.json").read_text(encoding="utf-8"))
    assert len(man["files"]) == 163 and man["rows_with_pages"] == 81 and man["rows_with_errors"] == 0
    for f in man["files"]:
        assert hashlib.sha256((ARENA / C1 / f["name"]).read_bytes()).hexdigest() == f["sha256"], f["name"]


def test_cohort_1_known_answer_and_counts():
    cap = ARENA / C1 / f"capture_ARENA_{C1}_{AS_OF}.json"
    pipeline, events, _i, _doc, refused, _l = runner.build(cap)
    assert refused == []
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    c = ranking.claim
    assert c["addresses_in_cohort"] == 80
    assert c["counts"] == {"FULL": 8, "PARTIAL": 23, "NONE": 49, "REFUSED": 0}
    assert c["median_net_full"] == Decimal("3937.1486885") and c["share_positive_full"] == Decimal("0.75")
    assert c["ranked"][0]["address"] == "0x4c6d679eac539bf7c5a0b7ebd8949ae93b1e5ee9"
    assert c["ranked"][0]["net_with_funding"] == Decimal("838846.44510952")
    rr = c["record_row"]
    assert rr["address"] == ACTOR and rr["coverage"] == STATUS_FULL and rr["fills"] == 4
    assert rr["realized_ex_funding"] == Decimal("0.077207")
    assert rr["funding"] == Decimal("-0.003674")
    assert rr["net_with_funding"] == Decimal("0.073533")
    assert rr["settled_pairs_on_record"] == {"PAPER": 1, "LIVE": 4}
    paper = {p["fork"]: p["episodes"] for b in c["paper_rows"] for p in b["rows"]}
    assert paper["F4:NEAR"] == 15 and paper["C1:ZEC"] == 1
    assert pipeline.event_log.root(len(pipeline.event_log)).hex() == C1_ROOT
    assert len(pipeline.event_log) == 83


def test_cohort_1_committed_run_file_is_the_run_and_verifies(tmp_path):
    cap = ARENA / C1 / f"capture_ARENA_{C1}_{AS_OF}.json"
    pipeline, _e, _i, _d, _r, _l = runner.build(cap)
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    committed = ARENA / C1 / f"run_ARENA_{C1}_{AS_OF}.ri"
    assert fresh.read_bytes() == committed.read_bytes()
    ok, report = runner.verify_run(committed)
    assert ok, report
    assert "reloaded 83 events" in report and report.endswith(C1_ROOT)


def test_cohort_2_is_boards_only_until_its_window_opens():
    cap = ARENA / C2 / f"capture_ARENA_{C2}_{C2}.json"
    pipeline, events, _i, doc, refused, _l = runner.build(cap)
    assert refused == [] and len(events) == 2
    ranking = next(e for e in events if e.claimant == GRADER_CLAIMANT)
    assert ranking.claim["addresses_in_cohort"] == 69 and ranking.claim["ranked"] == []
    assert doc["window"]["started"] is False and doc["window"]["t0_ms"] == 1793750400000
    assert pipeline.event_log.root(2).hex() == C2_ROOT
    ok, report = runner.verify_run(ARENA / C2 / f"run_ARENA_{C2}_{C2}.ri")
    assert ok and report.endswith(C2_ROOT)
    # the operator's address is on none of the four boards observed 2026-11-03
    assert ACTOR not in {a["address"].lower() for a in doc["cohort"]["addresses"]}


def test_a3_one_board_capture_gate_still_holds():
    """A18 R92: cohort 2's payload is NOT a capture_BOARD_ file; Day 4's gate stands."""
    from rights_events.agent_board import pinned_board_captures
    assert [p.name for p in pinned_board_captures()] == ["capture_BOARD_2026-10-25.json"]
