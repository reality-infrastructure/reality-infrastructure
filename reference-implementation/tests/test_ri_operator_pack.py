"""RI-OPERATOR: the operator pack loads, its events bind to the ledger, and the
pre-registered known answers hold (contracts/ri_operator/PREREG.md)."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from engine.errors import CitationError, EventError
from engine.store import Engine
from engine.validate import validate_pack
from packs.ri_operator import record

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "packs" / "ri_operator"
COMMANDS_DIR = ROOT.parent / ".claude" / "commands"
COMMANDS = ("ri-bottleneck", "ri-judgment", "ri-gate", "ri-pack", "ri-evidence", "ri-scan", "ri-week")

# PREREG.md "Banned nouns": substring match, case-insensitive.
BANNED = ("atlas", "hyperliquid", "venue", "clip", "leg", "vps", "pump", "polymarket",
          "wallet", "newce", "irvin", "ppg", "rich/", "hood", "ladder", "mimicry")

SAMPLES = {
    "constraint_named": ("system", {
        "system": "intake to reply", "state": "SLOW-BUT-HEALTHY", "unit_of_flow": "resolved tickets",
        "throughput_command": "python count.py --day 2026-01-05", "throughput_before": "41 per day",
        "throughput_after": "UNKNOWN", "constraint": "review queue holds 62% of cycle time",
        "constraint_class": "queue", "prediction": "halving the queue raises throughput about 31%",
        "prediction_held": "not-tested", "action": "none", "result": "diagnosis only",
        "next_binding": "UNKNOWN", "parking_lot": ["slow export"], "unknowns": ["p95 of stage 3"]}),
    "judgment_run": ("decision", {
        "decision": "ship the new intake form", "disproving_fact": "drop-off rose in the trial",
        "looked": True, "independent_root": "server access log", "ruin_reachable": False,
        "load_bearing_assumption": "trial users resemble all users", "who_profits": "the author",
        "probability": "60%", "best_alternative": "fix the old form", "reversible_part": "the flag",
        "irreversible_part": "the data migration", "hot": False, "outcome": "PROCEED-REVERSIBLE-PART"}),
    "gate_requested": ("action", {
        "action": "delete the old table", "author": "agent:builder",
        "assumptions": [{"statement": "nothing reads it", "status": "BELIEF", "evidence": "", "load_bearing": True}],
        "evidence_roots": ["code search"], "urgency": "none"}),
    "gate_verdict": ("action", {
        "request_event_id": "evt-1", "verdict": "VERIFY-FIRST", "failed_checks": ["G1", "G5"],
        "top_failure_mode": "a nightly job reads the table", "reversal_trigger": "if a read appears in the query log, restore from backup",
        "de_risking_move": "rename the table for a week; the owner's hand", "run_by": "agent:disprover"}),
    "evidence_submitted": ("claim", {
        "claim_id": "C-1", "hypothesis": "in force", "source_url": "https://example.org/act/12",
        "source_tier": "PRIMARY", "ep_type": "statutory_registry", "quote": "This Act takes effect on January 1.",
        "observed_date": "2026-01-05", "published_date": None, "derived_from": None,
        "source_id": "example-registry", "note": "effective date only"}),
    "fetch_logged": ("claim", {"claim_id": "C-1", "url": "https://example.org/act/13", "outcome": "refused"}),
    "scan_recorded": ("system", {
        "system": "intake to reply", "mode": "DEEP", "output_unit": "resolved tickets per day",
        "baseline": "no-baseline", "previous_scan": None, "previous_outcome": "none",
        "constraint": "62 tickets wait for review, oldest 3 days", "owner": "SELF",
        "count_command": "python count.py --stage review --day 2026-01-05", "count_result": "62 waiting, oldest 3d",
        "comfortable_candidate": "the mail provider is slow", "why_not_comfortable": "intake shows no wait",
        "owner_pending": "4 decisions, oldest 9 days", "test": "review 20 today and count resolved tomorrow",
        "price": "about 20 resolved tickets a day", "exploit": "review the oldest first", "subordinate": "the export job",
        "next_constraint": "SELF: drafting", "prediction": "resolved per day reaches 55",
        "prediction_resolves_on": "2026-01-12", "move": "one hour of review before anything else; the owner does it",
        "stop_doing": "tuning the export job", "attention": "the review queue", "unknowns": []}),
    "move_graded": ("system", {"scan_event_id": "evt-9", "executed": "N", "evidence": "no commit, no later event",
                               "waited_on": "the owner"}),
    "week_reviewed": ("system", {"week": "2026-W02", "scans": 5, "moves_written": 5, "moves_executed": 2,
                                 "repeater": "the review hour, written five times, done twice", "miss": "a holiday backlog",
                                 "loop": "one scan started late", "prior_repeater_open": "no-prior-week",
                                 "bet": "the review hour"}),
    "watch_set": ("system", {"week": "2026-W02", "blind_spot": "the mailbox key expires", "found_by": "dependency",
                             "tripwire": "days to expiry under 14", "tripwire_source": "python key_age.py",
                             "mark": "ACT", "action": "renew the key", "whose_hand": "the owner",
                             "weeks_carried": 0, "basis": "evidence"}),
    "clock_set": ("system", {"what": "mailbox key expiry", "due": "2026-02-01", "source": "provider console export",
                             "status": "open"}),
}


@pytest.fixture()
def engine():
    e = Engine.open("sqlite://:memory:")
    yield e
    e.close()


def _append(engine, name, payload=None):
    entity_type, sample = SAMPLES[name]
    return record.append(engine, name, entity_type=entity_type, entity_id="t-1",
                         payload=sample if payload is None else payload, source="agent:test")


def test_pack_validates_with_one_fenced_agent():
    info = validate_pack("ri_operator")
    assert info["fixture"] is False
    assert info["agents"] == {"disprover": "worker"}
    assert {f"ri_operator.{n}" for n in SAMPLES} <= set(info["event_types"])
    assert info["golden_cases"] == {"disprover": 0} and info["holdout_cases"] == {"disprover": 0}


def test_disprover_is_denied_everything_but_the_event_log():
    text = (PACK_DIR / "agents" / "disprover" / "access.yaml").read_text(encoding="utf-8")
    assert re.search(r"files:\s*\n\s*read: \[\]\s*\n\s*write: \[\]", text)
    assert "network: []" in text


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_each_event_type_binds_to_the_ledger_and_verifies(engine, name):
    row = _append(engine, name)
    assert row["event_type"] == f"ri_operator.{name}"
    assert record.verify(engine, row["event_id"])["leaf_hash"] == row["leaf_hash"]


def test_known_answer_2_verdict_outside_the_closed_vocabulary_is_refused(engine):
    bad = dict(SAMPLES["gate_verdict"][1], verdict="LOOKS-FINE")
    before = len(engine.ledger)
    with pytest.raises(EventError):
        _append(engine, "gate_verdict", bad)
    assert len(engine.ledger) == before


def test_known_answer_3_altered_evidence_fails_verification(engine):
    row = _append(engine, "gate_requested")
    engine.ledger.verify_row(row)
    tampered = copy.deepcopy(row)
    tampered["payload"]["assumptions"][0]["status"] = "VERIFIED"
    with pytest.raises(CitationError):
        engine.ledger.verify_row(tampered)


def test_a_missing_field_is_refused_not_defaulted(engine):
    partial = {k: v for k, v in SAMPLES["constraint_named"][1].items() if k != "throughput_after"}
    with pytest.raises(EventError):
        _append(engine, "constraint_named", partial)


def test_an_unread_source_is_a_logged_outcome_not_an_empty_one(engine):
    row = _append(engine, "fetch_logged")
    assert row["payload"]["outcome"] == "refused"
    with pytest.raises(EventError):
        _append(engine, "fetch_logged", {"claim_id": "C-1", "url": "https://example.org", "outcome": "empty"})


def test_record_cli_appends_then_verifies(tmp_path, capsys):
    import json
    db = f"sqlite:///{(tmp_path / 'e.sqlite3').as_posix()}"
    payload = tmp_path / "p.json"
    payload.write_text(json.dumps(SAMPLES["judgment_run"][1]), encoding="utf-8")
    assert record.main(["append", "judgment_run", "--entity-type", "decision", "--entity-id", "d-1",
                        "--payload", f"@{payload}", "--source", "agent:ri-judgment", "--db", db]) == 0
    event_id = re.search(r"event_id=(\S+)", capsys.readouterr().out).group(1)
    assert record.main(["verify", event_id, "--db", db]) == 0
    assert record.main(["append", "judgment_run", "--entity-type", "decision", "--entity-id", "d-1",
                        "--payload", '{"decision": "x"}', "--source", "agent:ri-judgment", "--db", db]) == 2


def test_scan_known_answer_1_a_constraint_with_no_count_is_refused(engine):
    read_not_counted = {k: v for k, v in SAMPLES["scan_recorded"][1].items() if k != "count_command"}
    with pytest.raises(EventError):
        _append(engine, "scan_recorded", read_not_counted)
    with pytest.raises(EventError):
        _append(engine, "scan_recorded", dict(SAMPLES["scan_recorded"][1], count_command=""))


def test_scan_known_answer_2_nothing_is_carried_a_third_week(engine):
    _append(engine, "watch_set", dict(SAMPLES["watch_set"][1], weeks_carried=2))
    with pytest.raises(EventError):
        _append(engine, "watch_set", dict(SAMPLES["watch_set"][1], weeks_carried=3))


def test_scan_known_answer_3_a_prediction_without_a_date_is_refused(engine):
    for bad in ("", "soon", "next week sometime"):
        with pytest.raises(EventError):
            _append(engine, "scan_recorded", dict(SAMPLES["scan_recorded"][1], prediction_resolves_on=bad))


def test_exactly_one_owner_class_and_one_mode(engine):
    for field, bad in (("owner", "SEVERAL"), ("mode", "QUICK"), ("previous_outcome", "partly")):
        with pytest.raises(EventError):
            _append(engine, "scan_recorded", dict(SAMPLES["scan_recorded"][1], **{field: bad}))


def test_list_counts_a_week_from_the_ledger(tmp_path, capsys):
    import json
    db = f"sqlite:///{(tmp_path / 'w.sqlite3').as_posix()}"
    for name in ("scan_recorded", "scan_recorded", "watch_set"):
        entity_type, sample = SAMPLES[name]
        f = tmp_path / f"{name}.json"
        f.write_text(json.dumps(sample), encoding="utf-8")
        assert record.main(["append", name, "--entity-type", entity_type, "--entity-id", "sys-1",
                            "--payload", f"@{f}", "--source", "agent:test", "--db", db]) == 0
    capsys.readouterr()
    assert record.main(["list", "--type", "scan_recorded", "--entity-id", "sys-1", "--db", db]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == "count=2"
    assert json.loads(out[0])["payload"]["mode"] == "DEEP"
    assert record.main(["list", "--entity-id", "sys-1", "--db", db]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "count=3"


def test_commands_exist_and_each_ends_in_a_ledger_record():
    for name in COMMANDS:
        text = (COMMANDS_DIR / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith("---\ndescription:"), name
        assert "$RI_HOME" in text, name
        assert "packs.ri_operator.record append" in text or "engine.replay" in text, name


def test_pack_and_commands_carry_no_banned_noun():
    files = [p for p in PACK_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [COMMANDS_DIR / f"{n}.md" for n in COMMANDS]
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        hits += [f"{path.name}: {word}" for word in BANNED if word in text]
    assert hits == []
