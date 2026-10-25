"""PREREG A5 gates on DERIVED fork documents: a synthetic tape run through the
watcher's pure functions (new_state / mark) against the pinned Day-3 LIVE open
capture, then through the pure fork adapter and the runner, in the same log as the
Day-3 LIVE legs. No real fork capture is pinned yet (A5.1 lands after the gate);
nothing here reads the network. Pre-existing gates are untouched; these only add.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from decimal import Decimal

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_fork import FORK_CLAIMANT, parse_events
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
OPEN_PV = "pv_e1849abce514440c"
OPEN_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}.json"
CLOSE_CAP = _FIX / f"capture_LIVE_2026-10-24_{OPEN_PV}_close.json"
OPEN_DOC = json.loads(OPEN_CAP.read_text(encoding="utf-8"))
FILL_MS = OPEN_DOC["live_fill"]["fill_time_ms"]          # 1792823305604
OPEN_FILL = Decimal(OPEN_DOC["live_fill"]["price_usd"])  # 80778.0


def _watcher():
    path = _FIX / "watch_stop_forks.py"
    spec = importlib.util.spec_from_file_location("stop_watcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fork_doc(tape=None) -> dict:
    """A complete fork capture from a synthetic tape: 10 bps at +5 s, 20 and 30 bps
    (the live control) at +10 s, then a recovery, then the gate at +5 h."""
    w = _watcher()
    st = w.new_state(OPEN_DOC, 30, [10, 20, 30, 50, 100], 5)
    st["open"]["capture"] = OPEN_CAP.name
    st["open"]["capture_sha256"] = hashlib.sha256(OPEN_CAP.read_bytes()).hexdigest()
    st["rules"]["poll_seconds"] = 5
    tape = tape or [(FILL_MS + 5000, "80690.0"), (FILL_MS + 10000, "80530.0"),
                    (FILL_MS + 15000, None), (FILL_MS + 20000, "80700.0"),
                    (st["rules"]["gate_ms"], "80800.0")]
    rows = 0
    for ms, mid in tape:
        rows += 1
        fired = w.mark(st, ms, None if mid is None else Decimal(mid))
        for key in fired:
            st["forks"][key]["payload_file"] = f"hl_allMids_{ms}.json"
            st["forks"][key]["payload_sha256"] = hashlib.sha256(str(ms).encode()).hexdigest()
    st["tape"].update({"file": f"watch_LIVE_2026-10-24_{OPEN_PV}.jsonl",
                       "sha256": "a" * 64, "rows": rows,
                       "null_rows": sum(1 for _m, mid in tape if mid is None)})
    st["complete"] = True
    return st


def _text(doc) -> str:
    return json.dumps(doc, indent=2) + "\n"


# --- R28: the fork events ---------------------------------------------------------------

def test_fork_known_answer_from_synthetic_tape():
    doc = _fork_doc()
    assert "source_url" in doc                       # the watcher names its source
    events = parse_events(_text(doc))
    assert [e.claim["fork"] for e in events] == ["10", "100", "20", "30", "50", "gate_only"]
    assert all(e.event_type is EventType.CHAIN_ASSERTION for e in events)
    assert all(e.ep_type is EPType.SELF_ASSERTED for e in events)        # simulations
    assert all(e.claimant == FORK_CLAIMANT and e.claim["mode"] == "PAPER" for e in events)
    assert all(e.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",) for e in events)
    assert all(e.source_url == "https://api.hyperliquid.xyz/info" for e in events)
    by = {e.claim["fork"]: e.claim for e in events}
    assert by["10"]["triggered"] and by["10"]["exit_reason"] == "stop"
    assert by["10"]["exit_mid_usd"] == Decimal("80690.0")
    assert by["10"]["gross_paper_pnl_usd"] == (Decimal("80690.0") - OPEN_FILL) * Decimal("0.00014")
    assert by["30"]["is_live_control"] and by["30"]["triggered"]
    assert by["30"]["exit_mid_usd"] == by["20"]["exit_mid_usd"] == Decimal("80530.0")
    assert by["30"]["adverse_bps_at_exit"] >= 30 and by["20"]["adverse_bps_at_exit"] >= 20
    for k in ("50", "100", "gate_only"):
        assert not by[k]["triggered"] and by[k]["exit_reason"] == "gate"
        assert by[k]["exit_mid_usd"] == Decimal("80800.0")
        assert by[k]["gross_paper_pnl_usd"] == Decimal("0.003080")
    assert by["gate_only"]["stop_bps"] is None and by["50"]["stop_bps"] == 50
    assert sum(1 for c in by.values() if c["is_live_control"]) == 1
    assert by["10"]["tape_null_rows"] == 1 and by["10"]["tape_rows"] == 5
    assert all(e.observed_date == "2026-10-24" for e in events)
    assert parse_events(_text(doc)) == events


def test_fork_rejections_nothing_invented():
    doc = _fork_doc(); doc["complete"] = False
    with pytest.raises(AdapterError, match="not complete"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["forks"]["10"]["gross_paper_pnl_usd"] = "0.5"
    with pytest.raises(AdapterError, match="gross_paper_pnl_usd"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["forks"]["50"]["triggered"] = True; doc["forks"]["50"]["exit_reason"] = "stop"
    with pytest.raises(AdapterError, match="stop exit"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["forks"]["20"]["is_live_control"] = True
    with pytest.raises(AdapterError, match="live control"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["forks"]["30"]["is_live_control"] = False
    with pytest.raises(AdapterError, match="exactly one fork"):
        parse_events(_text(doc))
    doc = _fork_doc(); del doc["forks"]["gate_only"]
    with pytest.raises(AdapterError, match="gate_only"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["forks"]["10"]["adverse_bps_at_exit"] = "11"
    with pytest.raises(AdapterError, match="recomputed"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["mode"] = "LIVE"
    with pytest.raises(AdapterError, match="PAPER by definition"):
        parse_events(_text(doc))
    doc = _fork_doc(); doc["kind"] = "agent_record_capture"
    with pytest.raises(AdapterError, match="kind"):
        parse_events(_text(doc))
    doc = _fork_doc(); del doc["source_url"]; doc["rules"]["exit_mark_source"] = "somewhere else"
    with pytest.raises(AdapterError, match="source_url"):
        parse_events(_text(doc))


def test_source_url_falls_back_to_the_declared_mark_source():
    """Today's running watcher predates the source_url line; the declared mark
    source names a real public URL, so nothing is invented."""
    doc = _fork_doc(); del doc["source_url"]
    events = parse_events(_text(doc))
    assert all(e.source_url == "https://api.hyperliquid.xyz/info" for e in events)


# --- R30: forks in the same log as the LIVE legs ----------------------------------------

def test_forks_join_the_live_run_as_fifteen_events(tmp_path):
    texts = [OPEN_CAP.read_text(encoding="utf-8"), CLOSE_CAP.read_text(encoding="utf-8"),
             _text(_fork_doc())]
    pipeline, events, indices = runner.ingest_captures(texts)
    assert len(events) == len(pipeline.event_log) == 15
    forks = [e for e in events if e.event_id.startswith("agent_record:fork:")]
    assert len(forks) == 6
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert len(signed) == 2                                  # the forks sign nothing
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                            # every fork hangs off the real open fill
    assert runner._all_inclusions_verify(pipeline)
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    pipeline.save(a)
    runner.ingest_captures(texts)[0].save(b)
    assert a.read_bytes() == b.read_bytes()
    ok, report = runner.verify_run(a)
    assert ok and "reloaded 15 events" in report


def test_runner_main_reports_forks(tmp_path, capsys):
    fork_path = tmp_path / f"forks_LIVE_2026-10-24_{OPEN_PV}.json"
    fork_path.write_text(_text(_fork_doc()), encoding="utf-8")
    out = tmp_path / "run.ri"
    rc = runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                      "--capture", str(fork_path), "--out", str(out)])
    text = capsys.readouterr().out
    assert rc == 0, text
    assert "AGENT-RECORD RUN: OK" in text
    assert "2 gap, 2 cryptographically_signed, 6 paper stop fork" in text
    assert "Paper stop fork        30 (live control): triggered, exit by stop" in text
    assert "Paper stop fork gate_only: untriggered, exit by gate" in text


def test_fork_capture_alone_is_refused_by_the_runner_as_a_record():
    """A fork capture has no intent: it never stands alone as a run (R30)."""
    pipeline, events, indices = runner.ingest_captures([_text(_fork_doc())])
    assert len(events) == 6
    for e in events:
        for ref in e.prior_event_refs:
            assert ref not in indices        # the open fill is NOT in a forks-only log


def test_watcher_reads_only():
    """R31 / S14: allMids only; no exchange, no order, no funding, no fills query."""
    src = (_FIX / "watch_stop_forks.py").read_text(encoding="utf-8")
    assert src.count('"allMids"') >= 1 and "https://api.hyperliquid.xyz/info" in src
    for forbidden in ("/exchange", "userFills", "clearinghouseState", "execute_trade",
                      "place_perp_order", "open_perp_position", "perp_deposit", "transfer_",
                      "preview_trade", "trade-api.gemach.io"):
        assert forbidden not in src, forbidden


def test_day1_to_3_run_files_untouched_by_the_fork_path():
    pins = {
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri":
            "598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri":
            "8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri":
            "126afbe5a4bb5116162919c6cd47cedcaa41d55805475ceb1b4167de13c9559a",
        "run_BOARD_2026-10-25.ri":
            "3d4f13d611d0383bdd6af71a4285e5aa4a6d1cb2a77b968f5ac5eb9c09b8d1ab",
    }
    for name, sha in pins.items():
        assert hashlib.sha256((_FIX / name).read_bytes()).hexdigest() == sha
