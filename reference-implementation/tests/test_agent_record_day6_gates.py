"""PREREG A9 (2026-10-27) gates, P10: the watcher declares a late gate (R45), the adapter
checks the declaration on files that carry rules.gate_late_rule and reads older files as
written (R46, S41), the runner's fork line says so. Synthetic tapes only, plus the committed
Day-4 and Day-5 tapes replayed through the new pure mark(); no real Day-6 capture exists yet.
Known answers are the ones A9 commits to in advance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_fork import GATE_LATE_RULE, LATE_POLLS, parse_events
from rights_events.adapters.common import AdapterError

_FIX = runner._FIXTURE.parent
ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "contracts" / "agent_record" / "PREREG.md"
WATCHER = _FIX / "watch_stop_forks.py"

# the synthetic base: the Day-3 LIVE open (the same base the A5 fork gates use)
OPEN_PV = "pv_e1849abce514440c"
OPEN_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}.json"
CLOSE_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}_close.json"
OPEN_DOC = json.loads(OPEN_CAP.read_text(encoding="utf-8"))
FILL_MS = OPEN_DOC["live_fill"]["fill_time_ms"]

DAYS = {
    # day: (open capture, forks file, tape, run file, root, run sha, late_ms, late, span)
    "2026-10-25": ("pv_aca51be96df9478c",
                   "c805f1240831a27f6ce924e7172e76f4cb19b4ca810ca71fd5815aea166605d9",
                   "4c03441d4c6224fb8fc2358eea2b5819ed34bd98dca0fa3cec38c3766ec80d1b",
                   4255, False, {"from_ms": 1792920766241, "to_ms": 1792920834189, "rows": 14}),
    "2026-10-26": ("pv_e9e6406179d94a4f",
                   "5215bc902440f8fcd925ec964d34fc699af5bb8ec3b7b9c06692e4b44ecc4e02",
                   "a5d0793cd576f91571a0c447298d3461bd56079610f0014fc03b3f95e2898b60",
                   16461940, True, {"from_ms": 1793004589036, "to_ms": 1793024133270, "rows": 3906}),
}


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _watcher():
    spec = importlib.util.spec_from_file_location("stop_watcher_a9", WATCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fork_doc(tape) -> dict:
    """A complete A9 fork capture from a synthetic tape of (ms, mid-or-None) rows."""
    w = _watcher()
    st = w.new_state(OPEN_DOC, 30, [10, 20, 30, 50, 100], 5)
    st["open"]["capture"] = OPEN_CAP.name
    st["open"]["capture_sha256"] = hashlib.sha256(OPEN_CAP.read_bytes()).hexdigest()
    st["rules"]["poll_seconds"] = 5
    rows = 0
    for ms, mid in tape:
        rows += 1
        for key in w.mark(st, ms, None if mid is None else Decimal(mid)):
            st["forks"][key]["payload_file"] = f"hl_allMids_{ms}.json"
            st["forks"][key]["payload_sha256"] = hashlib.sha256(str(ms).encode()).hexdigest()
    st["tape"].update({"file": f"watch_LIVE_2026-10-24_{OPEN_PV}.jsonl", "sha256": "a" * 64,
                       "rows": rows, "null_rows": sum(1 for _m, mid in tape if mid is None)})
    st["complete"] = True
    return st


def _text(doc) -> str:
    return json.dumps(doc, indent=2) + "\n"


def _gate_ms() -> int:
    return FILL_MS + 5 * 3600 * 1000


G = _gate_ms()
ON_TIME = [(FILL_MS + 5000, "80690.0"), (FILL_MS + 10000, "80530.0"),
           (FILL_MS + 20000, "80700.0"), (G + 3000, "80800.0")]
LATE = [(FILL_MS + 5000, "80690.0"), (FILL_MS + 10000, "80530.0"), (G - 5000, "80700.0"),
        (G + 5000, None), (G + 10000, None), (G + 15000, None), (G + 20000, "80800.0")]
THROUGH_A_HOLE = [(FILL_MS + 5000, None), (FILL_MS + 10000, None), (FILL_MS + 15000, None),
                  (FILL_MS + 20000, "80530.0"), (G + 1000, "80800.0")]


# --- prereg before code --------------------------------------------------------------------

def test_a9_is_pre_registered_with_its_rules_and_stops():
    text = PREREG.read_text(encoding="utf-8")
    assert "### A9 — 2026-10-27" in text
    for rule in ("R45", "R46", "R47", "R48", "R49", "R50", "R51", "S41", "S42", "S43", "S44"):
        assert re.search(rf"\b{rule}\b", text[text.index("### A9 —"):]), rule
    assert GATE_LATE_RULE in text.replace("\n  ", " ").replace("\n", " ") or \
        "late if gate.ms - gate_ms > 2 * poll_seconds" in text.replace("\n  ", " ")
    assert LATE_POLLS == 2


# --- R45: the watcher declares ------------------------------------------------------------

def test_r45_threshold_is_two_poll_intervals():
    w = _watcher()
    assert w.GATE_LATE_RULE == GATE_LATE_RULE
    assert w.is_late(10000, 5) is False
    assert w.is_late(10001, 5) is True
    assert w.is_late(4255, 5) is False            # Day 4's gate mark
    assert w.is_late(16461940, 5) is True         # Day 5's gate mark


def test_r45_on_time_gate_known_answer():
    doc = _fork_doc(ON_TIME)
    assert doc["rules"]["gate_late_rule"] == GATE_LATE_RULE
    assert doc["gate"] == {"ms": G + 3000, "mid": "80800.0",
                           "adverse_bps": doc["gate"]["adverse_bps"], "late_ms": 3000,
                           "late": False}
    assert doc["tape"]["longest_null_span"] == {"from_ms": None, "to_ms": None, "rows": 0}
    for key in ("50", "100", "gate_only"):
        f = doc["forks"][key]
        assert f["exit_reason"] == "gate" and f["gate_late_ms"] == 3000 and f["usable_for_r29"]
    for key in ("10", "20", "30"):
        f = doc["forks"][key]
        assert f["exit_reason"] == "stop" and f["gate_late_ms"] is None and f["usable_for_r29"]
    assert doc["live_trigger"]["after_null_rows"] == 0
    events = parse_events(_text(doc))
    assert len(events) == 6
    for e in events:
        c = e.claim
        assert c["gate_late"] is False
        assert c["tape_longest_null_span"] == {"from_ms": None, "to_ms": None, "rows": 0}
        assert c["usable_for_r29"] is True
        assert c["gate_late_ms"] == (None if c["exit_reason"] == "stop" else 3000)


def test_r45_late_gate_known_answer():
    doc = _fork_doc(LATE)
    assert doc["gate"]["late_ms"] == 20000 and doc["gate"]["late"] is True
    assert doc["tape"]["longest_null_span"] == {"from_ms": G + 5000, "to_ms": G + 15000, "rows": 3}
    assert doc["tape"]["null_rows"] == 3
    assert doc["tape"]["null_run"] == {"from_ms": None, "to_ms": None, "rows": 0}
    for key in ("50", "100", "gate_only"):
        f = doc["forks"][key]
        assert f["exit_reason"] == "gate" and f["exit_ms"] == G + 20000
        assert f["gate_late_ms"] == 20000 and f["usable_for_r29"] is False
    for key in ("10", "20", "30"):
        f = doc["forks"][key]
        assert f["exit_reason"] == "stop" and f["gate_late_ms"] is None and f["usable_for_r29"]
    # R28 unchanged: the same marks the A5 watcher would have made
    assert doc["forks"]["10"]["exit_ms"] == FILL_MS + 5000
    assert doc["forks"]["20"]["exit_ms"] == doc["forks"]["30"]["exit_ms"] == FILL_MS + 10000
    events = parse_events(_text(doc))
    by = {e.claim["fork"]: e.claim for e in events}
    assert all(by[k]["gate_late"] is True for k in by)
    assert {k for k in by if not by[k]["usable_for_r29"]} == {"50", "100", "gate_only"}
    assert by["gate_only"]["tape_longest_null_span"] == {"from_ms": G + 5000, "to_ms": G + 15000,
                                                         "rows": 3}
    assert by["30"]["live_trigger_after_null_rows"] == 0
    assert "live_trigger_after_null_rows" not in by["10"]


def test_r45_trigger_seen_through_a_hole_says_so():
    doc = _fork_doc(THROUGH_A_HOLE)
    assert doc["live_trigger"]["after_null_rows"] == 3
    assert doc["tape"]["longest_null_span"] == {"from_ms": FILL_MS + 5000, "to_ms": FILL_MS + 15000,
                                                "rows": 3}
    assert doc["gate"]["late_ms"] == 1000 and doc["gate"]["late"] is False
    by = {e.claim["fork"]: e.claim for e in parse_events(_text(doc))}
    assert by["30"]["live_trigger_after_null_rows"] == 3
    assert all(by[k]["usable_for_r29"] for k in by)


# --- R46: the runner's line ---------------------------------------------------------------

def test_r46_runner_names_the_late_gate_on_each_gate_fork(tmp_path, capsys):
    fork_path = tmp_path / f"forks_LIVE_2026-10-24_{OPEN_PV}.json"
    fork_path.write_text(_text(_fork_doc(LATE)), encoding="utf-8")
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--capture", str(fork_path), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert text.count(" -- GATE LATE, unusable for R29") == 3
    for key in ("50", "100", "gate_only"):
        assert re.search(rf"Paper stop fork +{key}: untriggered, exit by gate .* -- GATE LATE", text)
    assert "AGENT-RECORD RUN: OK" in text


def test_r46_runner_is_silent_on_an_on_time_gate(tmp_path, capsys):
    fork_path = tmp_path / f"forks_LIVE_2026-10-24_{OPEN_PV}.json"
    fork_path.write_text(_text(_fork_doc(ON_TIME)), encoding="utf-8")
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--capture", str(fork_path), "--out", str(out)]) == 0
    assert "GATE LATE" not in capsys.readouterr().out


# --- S41: the declaration is checked, not trusted -----------------------------------------

@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d["gate"].__setitem__("late", False), "gate.late"),
    (lambda d: d["gate"].__setitem__("late_ms", 19999), "gate.late_ms"),
    (lambda d: d["forks"]["50"].__setitem__("usable_for_r29", True), "usable_for_r29"),
    (lambda d: d["forks"]["10"].__setitem__("usable_for_r29", False), "usable_for_r29"),
    (lambda d: d["forks"]["gate_only"].pop("usable_for_r29"), "usable_for_r29"),
    (lambda d: d["forks"]["100"].__setitem__("gate_late_ms", 0), "gate exit"),
    (lambda d: d["forks"]["20"].__setitem__("gate_late_ms", 20000), "stop exit"),
    (lambda d: d["tape"].pop("longest_null_span"), "longest_null_span"),
    (lambda d: d["tape"]["longest_null_span"].__setitem__("rows", 4), "null_rows"),
    (lambda d: d["rules"].__setitem__("gate_late_rule", "A9 R45, paraphrased"), "gate_late_rule"),
    (lambda d: d["live_trigger"].pop("after_null_rows"), "after_null_rows"),
    (lambda d: d.pop("gate"), "gate object"),
])
def test_s41_refuses_a_declaration_that_disagrees(mutate, needle):
    doc = _fork_doc(LATE)
    mutate(doc)
    with pytest.raises(AdapterError) as exc:
        parse_events(_text(doc))
    msg = str(exc.value)
    assert needle in msg
    # a disagreeing declaration names S41; an absent field is refused by the shape check
    assert "S41" in msg or "must be an integer" in msg or "must be a boolean" in msg


def test_s41_does_not_touch_a_file_without_the_key():
    doc = _fork_doc(LATE)
    del doc["rules"]["gate_late_rule"]
    for f in doc["forks"].values():
        del f["usable_for_r29"], f["gate_late_ms"]
    del doc["gate"]["late_ms"], doc["gate"]["late"]
    del doc["tape"]["longest_null_span"], doc["tape"]["null_run"]
    del doc["live_trigger"]["after_null_rows"]
    events = parse_events(_text(doc))
    assert len(events) == 6
    assert all("gate_late" not in e.claim and "usable_for_r29" not in e.claim for e in events)


# --- R46: the record is read as written; nothing regenerated --------------------------------

@pytest.mark.parametrize("day", sorted(DAYS))
def test_older_forks_files_read_as_written_and_their_runs_regenerate(day, tmp_path):
    pv, root, sha, _late_ms, _late, _span = DAYS[day]
    fork_cap = _FIX / f"forks_LIVE_{day}_{pv}.json"
    doc = json.loads(fork_cap.read_text(encoding="utf-8"))
    assert "gate_late_rule" not in doc["rules"]
    events = parse_events(fork_cap.read_text(encoding="utf-8"))
    assert len(events) == 6
    assert all("gate_late" not in e.claim and "usable_for_r29" not in e.claim
               and "tape_longest_null_span" not in e.claim for e in events)
    texts = [(_FIX / f"capture_LIVE_{day}_{pv}.json").read_text(encoding="utf-8"),
             (_FIX / f"capture_LIVE_{day}_{pv}_close.json").read_text(encoding="utf-8"),
             fork_cap.read_text(encoding="utf-8")]
    pipeline, evs, _idx = runner.ingest_captures(texts)
    assert len(evs) == 15
    assert pipeline.event_log.root(len(pipeline.event_log)).hex() == root
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    run_file = _FIX / f"run_LIVE_{day}_{pv}.ri"
    assert fresh.read_bytes() == run_file.read_bytes()
    assert _lf_sha(run_file) == sha


@pytest.mark.parametrize("day", sorted(DAYS))
def test_committed_tapes_replayed_through_r45_give_the_a9_known_answers(day):
    """The A7.3 facts, now machine-made: the same marks (R28 unchanged) plus the lateness
    and the hole the A5 watcher never declared."""
    pv, _root, _sha, late_ms, late, span = DAYS[day]
    w = _watcher()
    open_doc = json.loads((_FIX / f"capture_LIVE_{day}_{pv}.json").read_text(encoding="utf-8"))
    committed = json.loads((_FIX / f"forks_LIVE_{day}_{pv}.json").read_text(encoding="utf-8"))
    st = w.new_state(open_doc, 30, [10, 20, 30, 50, 100], 5)
    st["rules"]["poll_seconds"] = 5
    rows = nulls = 0
    for line in (_FIX / f"watch_LIVE_{day}_{pv}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        rows += 1
        nulls += r["mid"] is None
        w.mark(st, r["ms"], None if r["mid"] is None else Decimal(r["mid"]))
    assert (rows, nulls) == (committed["tape"]["rows"], committed["tape"]["null_rows"])
    for key, f in committed["forks"].items():
        mine = st["forks"][key]
        for field in ("exit_ms", "exit_mid_usd", "adverse_bps_at_exit", "exit_reason",
                      "gross_paper_pnl_usd", "triggered"):
            assert mine[field] == f[field], (day, key, field)
    assert st["gate"]["ms"] == committed["gate"]["ms"]
    assert st["gate"]["late_ms"] == late_ms and st["gate"]["late"] is late
    assert st["tape"]["longest_null_span"] == span
    assert st["live_trigger"]["ms"] == committed["live_trigger"]["ms"]
    assert st["live_trigger"]["after_null_rows"] == 0
    unusable = {k for k, f in st["forks"].items() if not f["usable_for_r29"]}
    assert unusable == ({"50", "100", "gate_only"} if late else set())


# --- R31 still holds: the watcher reads only ------------------------------------------------

def test_watcher_still_reads_only_and_pins_nothing_new():
    src = WATCHER.read_text(encoding="utf-8")
    assert src.count('{"type": "allMids"}') == 1
    for forbidden in ("gdex", "place_perp", "execute", "exchange", "reduceOnly"):
        assert forbidden not in src, forbidden
    assert "GATE LATE" in src and "longest_null_rows=" in src
