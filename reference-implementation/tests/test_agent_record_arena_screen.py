"""PREREG A20 gates (P16): THE LEADER SCREEN. Nine written criteria (R102) over the pinned
arena and pages; pure and pinned (R103); a partial window screens nobody and an unstarted
window is refused (S92); a PARTIAL row can never be selected (S90); the screen's settled
figures must equal the arena run's (S91). Cohort 1's known answer: ZERO selected of 80, with
each FULL row's failing letters pinned. Offline; no network, no clock.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_arena as runner
from rights_events import arena_screen as scr
from rights_events.adapters.common import AdapterError
from test_agent_record_arena import A1, A2, A3, make_capture

ARENA = runner._FIXTURES / "arena"
C1 = ARENA / "2026-10-25"
C1_CAP = C1 / "capture_ARENA_2026-10-25_2026-11-03.json"
C1_ARENA = C1 / "arena_2026-10-25_2026-11-03.json"
C2 = ARENA / "2026-11-03"

PINS = {
    "screen_2026-10-25_2026-11-03.json": "cf810f2695eb854a00626ba14b82f8fc078f7cea58edc88323c1dcf6adb5ad2a",
    "screen_2026-10-25_2026-11-03.md": "fdb495a39f6890a1865f8bed0e31fe49ded4cf8c3d35b4dea3e935f9a2b4349e",
}

# A20.1: the code's verdicts under A20's written definitions, pinned
KNOWN_FAILS = {
    "0x4c6d679eac539bf7c5a0b7ebd8949ae93b1e5ee9": "DGH",
    "0xfc667adba8d4837586078f4fdcdc29804337ca06": "BEFH",
    "0xf818fa41af44a1b42ba7433f4ec472be40a2c268": "EFH",
    "0x856c35038594767646266bc7fd68dc26480e910d": "GH",
    "0x484bc1608211d0604bf70bae72792a56884562f8": "BCEFHI",
    "0x9794bbbc222b6b93c1417d01aa1ff06d42e5333b": "CDFG",
    "0x218a65e21eddeece7a9df38c6bbdd89f692b7da2": "BEFHI",
    "0xa312114b5795dff9b8db50474dd57701aa78ad1e": "EFGI",
}


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_screen_outputs_pinned(name, sha):
    assert _lf_sha(C1 / name) == sha


def test_cohort_1_known_answer_zero_selected_and_the_failing_letters(tmp_path):
    m = scr.screen(C1_CAP, C1_ARENA)
    assert m["counts"] == {"SELECTED": 0, "REFUSED": 80, "NOT_SCREENED": 0}
    assert m["selected"] == []
    full = {r["address"].lower(): r for r in m["rows"] if r["status"] == "FULL"}
    assert len(full) == 8
    for addr, letters in KNOWN_FAILS.items():
        assert "".join(full[addr]["fails"]) == letters, addr
    partial = [r for r in m["rows"] if r["status"] == "PARTIAL"]
    assert len(partial) == 23 and all(r["fails"][0] == "A" for r in partial)
    assert sum(1 for r in m["rows"] if r["status"] == "NONE") == 49
    # the operator's RECORD row is graded, never screened as a leader
    assert all(r["address"].lower() != "0x9f976123e7c48952be487664b8130aad144b7f23" for r in m["rows"])
    # the committed files are this screen, byte for byte
    assert scr.screen_json(m).encode("utf-8") == (C1 / "screen_2026-10-25_2026-11-03.json").read_bytes().replace(b"\r\n", b"\n")
    assert scr.render_markdown(m).encode("utf-8") == (C1 / "screen_2026-10-25_2026-11-03.md").read_bytes().replace(b"\r\n", b"\n")


def test_rank_1_fails_for_the_reasons_read_by_hand():
    m = scr.screen(C1_CAP, C1_ARENA)
    r = next(x for x in m["rows"] if x["address"].lower().startswith("0x4c6d679e"))
    f = r["features"]
    assert f["perp_share"] < Decimal("0.51")            # half its notional is one spot token
    assert f["day_concentration"] > Decimal("0.5")     # 11-02 alone is over half the positive days
    assert f["exposure_share"] > Decimal("1")           # inventory still open at the window's end
    assert f["net_bps_of_notional"] > Decimal("600")    # the number a copier would be sold on
    assert r["verdict"] == scr.REFUSED


def test_s92_an_unstarted_window_is_refused():
    with pytest.raises(AdapterError, match=r"S92"):
        scr.screen(C2 / "capture_ARENA_2026-11-03_2026-11-03.json", C2 / "arena_2026-11-03_2026-11-03.json")


def _synthetic_arena(tmp_path: Path):
    cap = make_capture(tmp_path)
    pipeline, events, _i, doc, _r, _l = runner.build(cap)
    m = runner.render_arena(doc, events, "x.ri", pipeline.event_log.root(len(pipeline.event_log)).hex())
    arena = tmp_path / "arena_2026-10-25_2026-11-03.json"
    arena.write_bytes(runner.arena_json(m).encode("utf-8"))
    return cap, arena


def test_synthetic_partial_row_fails_a_and_full_rows_fail_the_small_sample_criteria(tmp_path):
    cap, arena = _synthetic_arena(tmp_path)
    m = scr.screen(cap, arena)
    by = {r["address"]: r for r in m["rows"]}
    assert by[A3]["status"] == "PARTIAL" and by[A3]["fails"][0] == "A"
    assert by[A2]["status"] == "NONE" and "A" in by[A2]["fails"]
    assert by[A1]["status"] == "FULL" and "A" not in by[A1]["fails"] and "C" in by[A1]["fails"]
    assert m["selected"] == []


def test_s91_a_tampered_arena_figure_fails_the_screen(tmp_path):
    cap, arena = _synthetic_arena(tmp_path)
    doc = json.loads(arena.read_text(encoding="utf-8"))
    row = next(r for r in doc["rows"] if r["address"] == A1)
    row["net_with_funding"] = "999"
    arena.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(AdapterError, match=r"S91: rows\[" + A1 + r"\]\.net_with_funding"):
        scr.screen(cap, arena)


def test_a_partial_window_screens_nobody(tmp_path):
    cap, arena = _synthetic_arena(tmp_path)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    doc["as_of"]["as_of_date"] = "2026-10-30"
    doc["window"]["complete"] = False
    cap.write_text(json.dumps(doc), encoding="utf-8")
    a = json.loads(arena.read_text(encoding="utf-8"))
    a["as_of"] = "2026-10-30"
    arena.write_text(json.dumps(a), encoding="utf-8")
    m = scr.screen(cap, arena)
    assert m["window_complete"] is False and m["selected"] == []
    assert all(r["verdict"] == scr.NOT_SCREENED for r in m["rows"])


def test_the_screen_is_deterministic_and_reads_no_clock(tmp_path):
    cap, arena = _synthetic_arena(tmp_path)
    assert scr.screen_json(scr.screen(cap, arena)) == scr.screen_json(scr.screen(cap, arena))
    src = Path(scr.__file__).read_text(encoding="utf-8")
    for banned in ("time.time(", "datetime.now(", "utcnow(", "import urllib", "import random",
                   "import socket", "import subprocess"):
        assert banned not in src


def test_the_cli_writes_both_files_and_refuses_on_an_unstarted_window(tmp_path, capsys):
    cap, arena = _synthetic_arena(tmp_path)
    rc = scr.main(["--capture", str(cap), "--arena", str(arena), "--out-prefix", str(tmp_path / "screen_x")])
    assert rc == 0 and (tmp_path / "screen_x.json").exists() and (tmp_path / "screen_x.md").exists()
    assert "selected 0, refused 3" in capsys.readouterr().out
    rc = scr.main(["--capture", str(C2 / "capture_ARENA_2026-11-03_2026-11-03.json"),
                   "--arena", str(C2 / "arena_2026-11-03_2026-11-03.json"),
                   "--out-prefix", str(tmp_path / "screen_y")])
    assert rc == 1 and "SCREEN REFUSED: S92" in capsys.readouterr().out
