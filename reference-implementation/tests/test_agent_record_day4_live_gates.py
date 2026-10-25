"""Day-4 gates for agent_record's settled LIVE pair: the REAL captures pinned in A4.1
(open, 5d76416) and A4.2 (close, c946cb3), each committed strictly before this file.
The numbers below are the A4.1 / A4.2 known answers, not re-derived from the fixtures.
The paper stop forks (A5.1) and the fifteen-event run file are gated in the P8 block
appended below once the watcher reached the gate. Pre-existing gates are untouched.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    GAP_CHECK, INTENT_CLAIMANT, LIVE_CLAIMANT, LIVE_PNL_CHECK, PAPER_CLAIMANT,
    parse_events,
)
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
OPEN_PV = "pv_aca51be96df9478c"
CLOSE_PV = "pv_3e5df69d73074fd2"
OPEN_CAP = _FIX / f"capture_LIVE_2026-10-25_{OPEN_PV}.json"
CLOSE_CAP = _FIX / f"capture_LIVE_2026-10-25_{OPEN_PV}_close.json"
OPEN_TEXT = OPEN_CAP.read_text(encoding="utf-8")
CLOSE_TEXT = CLOSE_CAP.read_text(encoding="utf-8")
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"

PINS = {
    # A4.1 (open leg)
    f"capture_LIVE_2026-10-25_{OPEN_PV}.json":
        "71b181749208262ddb43f712922096418d3b5e36bf42af2fbc2a2275a90d5258",
    f"MANIFEST_LIVE_2026-10-25_{OPEN_PV}.json":
        "904d5c28e15fbf34d4706f16f2bc32384277ca8f2fac879b485b3feb5e4fe19e",
    f"gdex_preview_{OPEN_PV}.json":
        "4583eac293f047c9031128915efd2392ac47ddf4a12715a13653c20db6b94ba6",
    "hl_userFillsByTime_1792907352982.json":
        "61f133c2c29f23fb046d5f138195882bd87626fed4c91b707ee835433aae773e",
    "hl_allMids_1792907353204.json":
        "35efd07aa26ea6e19282bdbe3e15f8b6c17ccd27954fa0930f78971f5d8d0bad",
    # A4.2 (close leg)
    f"capture_LIVE_2026-10-25_{OPEN_PV}_close.json":
        "883ac6494bdb19873ca382ca773e72d65314123ddba6e01c9999c9e33b4b144f",
    f"MANIFEST_LIVE_2026-10-25_{OPEN_PV}_close.json":
        "815d174da508b08e82fc94d47dbabc2d2d6784849f723c871e194dc5fca7ff71",
    f"gdex_preview_{CLOSE_PV}.json":
        "afe123a25a43f93bf07150c04660d365ac05d33c8f5a566c4174fcf5e4b26b79",
    "hl_userFillsByTime_1792919726408.json":
        "9520c3decb3f810acc77cba76d8be274e2cc81d2e8527f84c03c67874cca7608",
    "hl_allMids_1792919726691.json":
        "551f1c133565208ac146704eb1a408d73f42471793124f2d5a9aa889e49bfcd4",
}
OPEN_TX = "0x239c825c5cb3130f251604474f72980203e30041f7b631e1c7652daf1bb6ecf9"
CLOSE_TX = "0x196062567a9bd2ce1ada0447520dbe020133003c159ef1a0bd290da9399facb8"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _by(events, claimant):
    return [e for e in events if e.claimant == claimant]


# --- S15 / S17: pinned inputs -----------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_day4_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day4_close_capture_names_the_pinned_open_leg():
    c = json.loads(CLOSE_TEXT)["closes"]
    assert c["capture"] == OPEN_CAP.name
    assert c["sha256"] == PINS[OPEN_CAP.name]                 # S17
    assert c["intent_id"] == OPEN_PV and c["fill_id"] == f"live:{OPEN_PV}:open"
    assert c["size"] == "0.00014" and c["fill_price_usd"] == "80522.0"
    assert c["fill_fee_usd"] == "0.016141"


def test_day4_captures_match_their_verbatim_payloads():
    """The capture's numbers are the chain's and the mid's, not typed in."""
    for cap, fills_name, mids_name in (
        (OPEN_TEXT, "hl_userFillsByTime_1792907352982.json", "hl_allMids_1792907353204.json"),
        (CLOSE_TEXT, "hl_userFillsByTime_1792919726408.json", "hl_allMids_1792919726691.json"),
    ):
        doc = json.loads(cap)
        rows = json.loads((_FIX / fills_name).read_text(encoding="utf-8"))
        assert len(rows) == 1 == doc["live_fill"]["rows"]
        row = rows[0]
        assert doc["live_fill"]["tx_hashes"] == [row["hash"]]
        assert Decimal(doc["live_fill"]["price_usd"]) == Decimal(row["px"])
        assert Decimal(doc["live_fill"]["fee_usd"]) == (
            Decimal(row["fee"]) + Decimal(row["builderFee"]))
        assert doc["live_fill"]["fill_time_ms"] == row["time"]
        assert row["crossed"] is True                           # taker both legs
        mids = json.loads((_FIX / mids_name).read_text(encoding="utf-8"))
        assert Decimal(doc["shadow_fill"]["price_usd"]) == Decimal(mids["BTC"])


# --- A4 R26: the close path as declared --------------------------------------------

def test_day4_close_followed_r26():
    """The reduce-only limit at P = markPx x 0.999 rounded DOWN to a whole 10 USD; a
    sell limit fills at or above P; the fill landed inside the preview's own window."""
    prev = json.loads((_FIX / f"gdex_preview_{CLOSE_PV}.json").read_text(encoding="utf-8"))
    assert prev["kind"] == "perp_close" and prev["terms"]["reduceOnly"] is True
    assert prev["terms"]["positionSize"] == prev["terms"]["size"] == "0.00014"
    assert prev["terms"]["isFullClose"] is True and prev["terms"]["closeSide"] == "sell"
    mark = Decimal(prev["terms"]["markPx"])
    assert mark == Decimal("80160")
    price = (mark * Decimal("0.999") / 10).to_integral_value(rounding="ROUND_FLOOR") * 10
    assert price == Decimal("80070")
    fill = json.loads(CLOSE_TEXT)["live_fill"]
    assert Decimal(fill["price_usd"]) >= price
    assert prev["createdAt"] <= fill["fill_time_ms"] <= prev["expiresAt"]
    assert fill["oid"] == 585206689925 and fill["dir"] == "Close Long"


# --- A4.1 known answer: the open leg --------------------------------------------

def test_day4_open_leg_known_answer():
    events = parse_events(OPEN_TEXT)
    assert len(events) == 4
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    assert {e.observed_date for e in events} == {"2026-10-25"}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["quote_price_usd"] == Decimal("80534")
    assert intent.claim["size"] == Decimal("0.00014")
    assert intent.claim["leverage"] == 1 and intent.claim["margin_mode"] == "cross"
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == Decimal("80522.0")
    assert live.claim["fee_usd"] == Decimal("0.016141")
    assert live.claim["tx_hashes"] == [OPEN_TX]
    assert live.claim["dir"] == "Open Long"
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.ep_type is EPType.SELF_ASSERTED
    assert shadow.claim["price_usd"] == Decimal("80516.5")
    assert shadow.claim["mode"] == "PAPER"
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.6830898014692640638875261592")
    assert gap.claim["cost_sign"] == 1 and gap.claim["shadow_lag_ms"] == 1166
    assert [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED] == [live]
    assert parse_events(OPEN_TEXT) == events


# --- A4.2 known answer: the close leg -------------------------------------------

def test_day4_close_leg_known_answer():
    events = parse_events(CLOSE_TEXT)
    assert len(events) == 5
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert {e.observed_date for e in events} == {"2026-10-25"}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["kind"] == "perp_close" and intent.claim["side"] == "sell"
    assert intent.claim["quote_price_usd"] == Decimal("80160")
    assert intent.claim["reduce_only"] is True and intent.claim["is_full_close"] is True
    assert "leverage" not in intent.claim
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == Decimal("80110.0")
    assert live.claim["fee_usd"] == Decimal("0.016059")
    assert live.claim["tx_hashes"] == [CLOSE_TX]
    assert live.claim["dir"] == "Close Long"
    assert live.claim["closed_pnl_usd"] == Decimal("-0.05768")
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06241379095124858788797972800")
    assert gap.claim["cost_sign"] == -1 and gap.claim["shadow_lag_ms"] == 975
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert r.claim["realized_pnl_usd"] == Decimal("-0.089880")
    assert r.claim["fees_usd"] == Decimal("0.032200")
    assert r.claim["bucket"] == "LOSS"
    assert r.claim["venue_closed_pnl_usd"] == Decimal("-0.05768")
    assert r.claim["realized_pnl_usd"] + r.claim["fees_usd"] == r.claim["venue_closed_pnl_usd"]
    assert r.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",
                                  f"agent_record:fill:live:{OPEN_PV}:close")
    assert parse_events(CLOSE_TEXT) == events


# --- R19 / S10: the pair alone is nine events, two signed ---------------------------

def test_day4_pair_is_nine_events_two_signed_zero_disputes():
    pipeline, events, indices = runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT])
    assert len(events) == len(pipeline.event_log) == 9
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert sorted(e.event_id for e in signed) == [
        f"agent_record:fill:live:{OPEN_PV}:close", f"agent_record:fill:live:{OPEN_PV}:open"]
    assert len(_by(events, GAP_CHECK)) == 2
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                               # S10
    assert runner._all_inclusions_verify(pipeline)


def test_day4_unexecuted_previews_are_not_in_the_record():
    """A4.1: two open previews expired unexecuted while the stop was decided; their ids
    are the venue's and their files were never placed in the fixtures."""
    for pv in ("pv_c5f97c90d642402f", "pv_45f7f1dfe17e4747"):
        assert not (_FIX / f"gdex_preview_{pv}.json").exists()


# =====================================================================================
# P8d — A5.1: the real paper stop-fork capture (pinned c21c415, before this block) and
# the fifteen-event Day-4 run file. The numbers are the A5.1 known answers.
# =====================================================================================

from rights_events.adapters.agent_fork import FORK_CLAIMANT, parse_events as parse_forks  # noqa: E402

FORK_CAP = _FIX / f"forks_LIVE_2026-10-25_{OPEN_PV}.json"
TAPE = _FIX / f"watch_LIVE_2026-10-25_{OPEN_PV}.jsonl"
RUN_FILE = _FIX / f"run_LIVE_2026-10-25_{OPEN_PV}.ri"
FORK_TEXT = FORK_CAP.read_text(encoding="utf-8")
RUN_ROOT = "c805f1240831a27f6ce924e7172e76f4cb19b4ca810ca71fd5815aea166605d9"

FORK_PINS = {
    FORK_CAP.name: "8499ce2927952dfb33a36d35040d4a97bdeae9895fd217f310f24836db3fc9cd",
    TAPE.name: "1e9a9e9216c0c4357efbea454d2a152ab353b211b36bbfab7810ec196359b64b",
    "hl_allMids_1792911091777.json":
        "a774ffc72f05be10046d9a1ea361ebe1cf320af95ab8eac9d05ebc11fbe102ce",
    "hl_allMids_1792916921385.json":
        "7b22b3603d8646a6f4133fa9b4760e85fa69728bd464120fdd4cff7c492a4e72",
    "hl_allMids_1792919581626.json":
        "56a9589fdf862001d474fd35186544bb53bfd81cb19b83761297084bb1d777c3",
    "hl_allMids_1792919698491.json":
        "c58c3335df9cc1a87fd2e23d945ba4f097443b430079a0e021a896eaf7044e73",
    "hl_allMids_1792925356293.json":
        "71f2826ddca32a5853662365a33efea9cb1f7aae32cb15536524ce6e8aa0fa45",
}

# fork -> (exit_reason, exit_ms, exit_mid, gross)
FORK_ANSWERS = {
    "10": ("stop", 1792911091777, "80440.5", "-0.011410"),
    "20": ("stop", 1792916921385, "80354.5", "-0.023450"),
    "30": ("stop", 1792919581626, "80260.5", "-0.036610"),
    "50": ("stop", 1792919698491, "80115.5", "-0.056910"),
    "100": ("gate", 1792925356293, "80194.5", "-0.045850"),
    "gate_only": ("gate", 1792925356293, "80194.5", "-0.045850"),
}


@pytest.mark.parametrize("name,sha", sorted(FORK_PINS.items()))
def test_day4_fork_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day4_fork_file_names_the_tape_and_the_pinned_open_leg():
    doc = json.loads(FORK_TEXT)
    assert doc["kind"] == "agent_record_fork_capture" and doc["complete"] is True
    assert doc["tape"]["file"] == TAPE.name
    assert doc["tape"]["sha256"] == hashlib.sha256(TAPE.read_bytes()).hexdigest()
    assert doc["tape"]["rows"] == 3366 and doc["tape"]["null_rows"] == 19
    assert doc["open"]["capture"] == OPEN_CAP.name
    assert doc["open"]["capture_sha256"] == PINS[OPEN_CAP.name]
    assert doc["open"]["fill_event_id"] == f"agent_record:fill:live:{OPEN_PV}:open"
    assert doc["rules"]["live_stop_bps"] == 30 and doc["rules"]["gate_ms"] == 1792925352038
    assert doc["gate"]["ms"] == 1792925356293 and doc["live_trigger"]["ms"] == 1792919581626
    assert "source_url" not in doc                   # A5.1 disclosure: the fallback applies


def test_day4_tape_is_what_the_fork_file_says():
    """The tape's rows, nulls and the marks' mids are read back from the tape itself."""
    rows = [json.loads(line) for line in TAPE.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3366 and sum(1 for r in rows if r["mid"] is None) == 19
    by_ms = {r["ms"]: r["mid"] for r in rows}
    for key, (_reason, ms, mid, _gross) in FORK_ANSWERS.items():
        assert by_ms[ms] == mid, key
    mids = [Decimal(r["mid"]) for r in rows if r["mid"] is not None]
    worst = max((Decimal("80522.0") - m) / Decimal("80522.0") * 10000 for m in mids)
    assert Decimal("58.43") < worst < Decimal("58.44")          # never 100
    for key in ("10", "20", "30", "50"):                          # first crossing (R28)
        _r, ms, _m, _g = FORK_ANSWERS[key]
        before = [Decimal(r["mid"]) for r in rows if r["mid"] is not None and r["ms"] < ms]
        assert all((Decimal("80522.0") - m) / Decimal("80522.0") * 10000 < Decimal(key)
                   for m in before), key


def test_day4_fork_payloads_match_their_marks():
    doc = json.loads(FORK_TEXT)
    for key, f in doc["forks"].items():
        payload = json.loads((_FIX / f["payload_file"]).read_text(encoding="utf-8"))
        assert Decimal(payload["BTC"]) == Decimal(f["exit_mid_usd"]), key
        assert _lf_sha(_FIX / f["payload_file"]) == f["payload_sha256"]


def test_day4_fork_known_answer():
    events = parse_forks(FORK_TEXT)
    assert [e.claim["fork"] for e in events] == ["10", "100", "20", "30", "50", "gate_only"]
    assert all(e.ep_type is EPType.SELF_ASSERTED and e.claimant == FORK_CLAIMANT
               and e.claim["mode"] == "PAPER" and e.observed_date == "2026-10-25"
               and e.source_url == "https://api.hyperliquid.xyz/info"
               and e.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",)
               for e in events)
    by = {e.claim["fork"]: e.claim for e in events}
    for key, (reason, ms, mid, gross) in FORK_ANSWERS.items():
        c = by[key]
        assert c["exit_reason"] == reason and c["exit_ms"] == ms, key
        assert c["exit_mid_usd"] == Decimal(mid) and c["gross_paper_pnl_usd"] == Decimal(gross), key
        assert c["triggered"] is (reason == "stop"), key
    assert by["30"]["is_live_control"] and sum(1 for c in by.values() if c["is_live_control"]) == 1
    assert by["30"]["adverse_bps_at_exit"] == Decimal("32.47559673132808425026700777")
    assert by["10"]["adverse_bps_at_exit"] == Decimal("10.12145748987854251012145749")
    # R29 material, day one of three: tighter beat the control, wider lost more.
    control = by["30"]["gross_paper_pnl_usd"]
    assert by["10"]["gross_paper_pnl_usd"] > by["20"]["gross_paper_pnl_usd"] > control
    assert control > by["100"]["gross_paper_pnl_usd"] > by["50"]["gross_paper_pnl_usd"]
    # The control's REAL gross (A4.2) is worse than its paper fork by the close latency.
    live_gross = (Decimal("80110.0") - Decimal("80522.0")) * Decimal("0.00014")
    assert control - live_gross == Decimal("0.021070")
    assert parse_forks(FORK_TEXT) == events


# --- R30: the Day-4 run is fifteen events, two signed, in ONE log ----------------------

def _day4_run():
    return runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT, FORK_TEXT])


def test_day4_run_is_fifteen_events_two_signed_zero_disputes():
    pipeline, events, indices = _day4_run()
    assert len(events) == len(pipeline.event_log) == 15
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert sorted(e.event_id for e in signed) == [
        f"agent_record:fill:live:{OPEN_PV}:close", f"agent_record:fill:live:{OPEN_PV}:open"]
    assert len([e for e in events if e.event_id.startswith("agent_record:fork:")]) == 6
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                               # S10 / C4
    assert runner._all_inclusions_verify(pipeline)
    assert pipeline.event_log.root(len(pipeline.event_log)).hex() == RUN_ROOT


def test_day4_committed_run_file_is_the_run(tmp_path):
    """The committed Day-4 run file is byte-identical to a fresh run of the three pinned
    captures and re-verifies as a stranger would check it."""
    pipeline, _e, _i = _day4_run()
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    assert fresh.read_bytes() == RUN_FILE.read_bytes()
    assert _lf_sha(RUN_FILE) == "4c03441d4c6224fb8fc2358eea2b5819ed34bd98dca0fa3cec38c3766ec80d1b"
    ok, report = runner.verify_run(RUN_FILE)
    assert ok, report
    assert "reloaded 15 events" in report and report.endswith(RUN_ROOT)


def test_day4_runner_main_ok(tmp_path, capsys):
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--capture", str(FORK_CAP), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD RUN: OK" in text
    assert "2 gap, 2 cryptographically_signed, 6 paper stop fork" in text
    assert "Paper stop fork        30 (live control): triggered, exit by stop at mid 80260.5" in text
    assert "Paper stop fork gate_only: untriggered, exit by gate at mid 80194.5" in text
    assert "Realized live PnL (pv_aca51be96df9478c): -0.089880 USD, LOSS" in text


def test_day1_to_4_run_files_untouched_by_day4_pair():
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
        assert _lf_sha(_FIX / name) == sha
