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
COMMANDS = ("ri-bottleneck", "ri-judgment", "ri-gate", "ri-pack", "ri-evidence")

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


def test_five_commands_exist_and_each_ends_in_a_ledger_record():
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
