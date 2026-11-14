"""A45 / P37 gates: THE KIT (arena-kit/arena.mjs).

R201 the face (one line per row, the pinned file's own strings, nothing else); R202 three verbs; R204 the words
across cohorts and the exit codes; S121 no figure that is not the file's text; S122 the refusals; S123 no key, no
call but a GET to three fixed endpoints, one write; the statement byte-equal to the door's. The kit is run by Node
with pinned files in place of the network. Offline.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rights_events import arena_door as d

_ROOT = Path(__file__).resolve().parents[1]
_ARENA = _ROOT / "rights_events" / "fixtures" / "agent_record" / "arena"
_KIT = _ROOT / "arena-kit" / "arena.mjs"
_HARNESS = Path(__file__).with_name("arena_kit_harness.mjs")
SHA = "c6b590de2289de698053a203e22941bafd55e558f0d5947ac8a4b40274042878"
FEED = _ARENA / "feed" / "feed_2026-11-12.json"
DOOR = _ARENA / "door" / "door_2026-11-13.json"
BOARD = _ARENA / "ai_board" / "ai_board_2026-11-13.json"
LEADER = "0x4c6d679eac539bf7c5a0b7ebd8949ae93b1e5ee9"
RECORD = "0x9f976123e7c48952be487664b8130aad144b7f23"
A1 = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"      # a published test key's address; no funds
SIG = "0x" + "ab" * 65

_NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(_NODE is None, reason="the kit's gates need Node 18+ on PATH")


def kit(tmp_path, argv, mutate=None, files=None):
    spec = {"files": {k: str(v) for k, v in (files or {"feed": FEED, "door": DOOR, "board": BOARD}).items()},
            "mutate": mutate, "argv": argv}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    r = subprocess.run([_NODE, str(_HARNESS), _KIT.as_uri(), str(p)], capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return json.loads(r.stdout.decode("utf-8"))


def test_known_answer_1_the_leader_reads_keep(tmp_path):
    r = kit(tmp_path, ["grade", LEADER])
    assert r["code"] == 0
    assert r["out"][0].split("   ") == ["KEEP", "838846.44510952 USD", "2026-10-26 … 2026-11-02", "4566 fills", "proof"]
    assert r["out"][1:] == ["as of 2026-11-12 (feed), 2026-11-13 (door)"]


def test_known_answer_2_the_record_reads_keep_then_drop(tmp_path):
    r = kit(tmp_path, ["grade", RECORD])
    assert r["code"] == 1
    rows = [re.split(r" {3,}", line) for line in r["out"][:2]]
    assert rows == [["KEEP", "0.073533 USD", "2026-10-26 … 2026-11-02", "4 fills", "proof"],
                    ["DROP", "0 USD", "2026-11-04 … 2026-11-10", "0 fills", "proof"]]
    assert r["out"][2] == "KEEP → DROP"


def test_known_answer_3_the_board_prints_the_door_as_it_stands(tmp_path):
    r = kit(tmp_path, ["board"])
    assert r["code"] == 0
    assert r["out"][:5] == ["THE DOOR", "no entrant is graded", "entered 0, withdrawn 0, active 0, outside 0",
                            "OPEN 0 of 20: 0 outside entrants, 0 of 3 outside FULL rows over a complete window",
                            "as of 2026-11-13 (door)"]
    assert len([x for x in r["out"] if x.endswith("trades")]) == len(json.loads(BOARD.read_text(encoding="utf-8"))["rows"])


def test_known_answer_4_the_statement_is_the_doors_bytes(tmp_path):
    r = kit(tmp_path, ["enter", "--address", A1, "--model", "test"])
    text = r["out"][0] + "\n"                                  # the six lines are one print; the last line feed is the print's
    assert text == d.statement_text(A1, "test", SHA, False)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == "ce2b2c34ee32d8e6de7479d295e8575b2738fd1911d4a5384bf78956654b2c13"
    assert r["gets"] == [] and r["writes"] == {}


def test_known_answer_5_not_listed_and_the_refusals(tmp_path):
    r = kit(tmp_path, ["grade", A1])
    assert r["code"] == 4 and r["out"][0] == "NOT LISTED" and A1 in r["out"][1]
    for mutate in ("feed", "door", "down"):
        r = kit(tmp_path, ["grade", LEADER], mutate=mutate)
        assert r["code"] == 10 and len(r["out"]) == 1 and r["out"][0].startswith("REFUSED S122"), mutate
    assert kit(tmp_path, ["board"], mutate="board")["code"] == 10
    assert kit(tmp_path, ["grade", "0xNOPE"])["code"] == 10
    assert kit(tmp_path, ["enter", "--address", A1, "--model", "x" * 65])["code"] == 10
    assert kit(tmp_path, ["enter", "--address", A1, "--model", "ok", "--signature", "0x12"])["code"] == 10


def test_s121_every_figure_on_every_face_is_the_files_own_text(tmp_path):
    feed_text, board_text = FEED.read_text(encoding="utf-8"), BOARD.read_text(encoding="utf-8")
    feed = json.loads(feed_text)
    for address in sorted({row["address"] for row in feed["rows"]}):
        r = kit(tmp_path, ["grade", address])
        want = [row for row in feed["rows"] if row["address"] == address]
        want.sort(key=lambda row: row["cohort_date"])
        assert r["code"] == {"KEEP": 0, "DROP": 1, "UNDECIDED": 2, "OPEN": 3}[want[-1]["status"]]
        for line, row in zip(r["out"], want):
            cells = re.split(r" {3,}", line)
            assert cells[0] == row["status"]
            assert cells[1] == f"{row['verified_net']} USD" and f'"{row["verified_net"]}"' in feed_text
            assert cells[3] == f"{row['fills']} fills"
    for line in kit(tmp_path, ["board"])["out"]:
        m = re.search(r" {3}(-?[0-9.e+-]+) (USD|bps) {3}", line)
        if m:
            assert m.group(1) in board_text, line


def test_r201_an_entrant_row_carries_the_label_and_the_sentence(tmp_path):
    door = json.loads(DOOR.read_text(encoding="utf-8"))
    door["rows"] = [{"klass": "AGENT", "model": "GDEX-123 scout v3", "address": A1, "cohort_date": "2026-11-03",
                     "window": {"t0_date": "2026-11-04", "t1_date": "2026-11-10", "complete": True}, "status": "DROP",
                     "total_pnl": "-1.25", "trips": {"fills": 6, "trades": 3}}]
    door["not_yet_captured"] = [{"address": "0x" + "1" * 40, "model": "late v1", "status": "LISTED, NOT YET CAPTURED"}]
    p = tmp_path / "door.json"
    p.write_text(json.dumps(door), encoding="utf-8")
    files = {"feed": FEED, "door": p, "board": BOARD}
    r = kit(tmp_path, ["grade", A1], files=files)
    assert r["code"] == 1 and r["out"][0].split("   ") == ["DROP", "-1.25 USD", "2026-11-04 … 2026-11-10", "6 fills", "proof"]
    assert d.ROW_SENTENCE in r["out"]
    r = kit(tmp_path, ["grade", "0x" + "1" * 40], files=files)
    assert r["code"] == 3 and r["out"][0] == "LISTED, NOT YET CAPTURED"
    b = kit(tmp_path, ["board"], files=files)["out"]
    assert b[1].startswith("GDEX-123 scout v3   0xf39f…2266   DROP") and "late v1" in b[2] and d.ROW_SENTENCE in b
    proof = json.loads(kit(tmp_path, ["grade", A1, "--proof"], files=files)["out"][0])
    assert proof["row"] == door["rows"][0] and proof["settled_sha256"] == SHA
    assert proof["file_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()


def test_enter_with_a_signature_writes_one_file_and_sends_nothing(tmp_path):
    r = kit(tmp_path, ["enter", "--address", A1, "--model", "GDEX-123 scout v3", "--signature", SIG])
    assert r["gets"] == [] and list(r["writes"]) == [f"arena-enrolment-{A1}.json"]
    body = json.loads(r["writes"][f"arena-enrolment-{A1}.json"])
    assert body["statement"] == d.statement_text(A1, "GDEX-123 scout v3", SHA, False) and body["signature"] == SIG


def test_s123_the_source_reads_no_key_and_calls_nothing_but_three_gets():
    src = _KIT.read_text(encoding="utf-8")
    assert re.findall(r"from '([^']+)'", src) == ["node:crypto", "node:fs", "node:url"]
    assert "import { writeFileSync } from 'node:fs'" in src and src.count("writeFileSync(") == 1
    assert src.count("fetch(") == 1 and "method: 'GET'" in src
    for banned in ("readFile", "privateKey", "mnemonic", "process.env", "child_process", "POST", "require(", "eval("):
        assert banned not in src, banned
    assert re.findall(r"https?://[^'\"\s]+", src) == [
        "https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/contract/agent-record/"
        "reference-implementation/rights_events/fixtures/agent_record/arena/"]
    assert f"'{SHA}'" in src
    for name in ("feed", "door", "board"):
        pin = {"feed": FEED, "door": DOOR, "board": BOARD}[name]
        assert json.loads(pin.read_text(encoding="utf-8"))["endpoint"].endswith(
            {"feed": "feed/feed_latest.json", "door": "door/door_latest.json", "board": "ai_board/ai_board_latest.json"}[name])
