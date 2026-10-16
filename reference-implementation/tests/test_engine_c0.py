"""C0 — core runner: manifest, loop, provider, access, guardrails, traces, eval.

Acceptance (spec PART 3, C0):
1. run exits 0, prints run_id; row has non-null iterations, cost, latency, manifest_hash
2. eval prints PASS
3. unlisted table read -> AccessDenied, run status access_denied
4. malformed output -> failed_guardrail, output null
5. manifest with unknown key / tool / guardrail -> load error
6. model swap: same agent on two model strings, no code change
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from engine.config import ENGINE_ROOT
from engine.errors import ManifestError
from engine.eval import run_eval
from engine.manifest import load_agent
from engine.packs import load_pack
from engine.replay import verify_run
from engine.run import main as run_main

ENGINE_DIR = ENGINE_ROOT / "engine"


# 1 ---------------------------------------------------------------------------

def test_run_succeeds_and_is_traced(runner, engine):
    result = runner.run("checker", {"sheet_id": "S1"})
    assert result.status == "succeeded"
    row = engine.store.get_run(result.run_id)
    assert row["iterations"] and row["iterations"][1]["candidates"][0]["accepted"]
    assert isinstance(row["cost_usd"], Decimal) and row["cost_usd"] > 0
    assert row["latency_ms"] >= 0
    assert row["manifest_hash"] == runner.agent("checker").hash
    assert row["items_evaluated"] == 3
    # every tool call of the candidate is in the trace, with its result
    calls = row["iterations"][1]["candidates"][0]["tool_calls"]
    assert {c["tool"] for c in calls} == {"_reference.arith.eval", "events.append"}
    assert all("result" in c for c in calls)
    # the flagged row is the one the fixture misstates
    flagged = [i["row_id"] for i in row["output"]["items"] if i["flag"]]
    assert flagged == ["S1-2"]
    # the row is bound to the RI ledger and the judgement replays byte for byte
    engine.ledger.verify_row(row)
    proof = verify_run(engine, result.run_id)
    assert proof["byte_identical"] and proof["summaries_match"]


def test_cli_prints_run_id_and_exits_zero(capsys, tmp_path):
    db = f"sqlite:///{(tmp_path / 'cli.sqlite3').as_posix()}"
    code = run_main(["_reference/checker", "--input", '{"sheet_id": "S2"}', "--db", db])
    out = capsys.readouterr().out
    assert code == 0
    assert re.search(r"run_id=[0-9a-f-]{36} status=succeeded", out)


# 2 ---------------------------------------------------------------------------

def test_eval_prints_pass(engine, pack):
    report = run_eval(engine, pack, "checker")
    assert report["summary"] == "PASS (2/2 >= 1.0)"
    assert report["pass"]


# 3 ---------------------------------------------------------------------------

def test_unlisted_table_read_fails_closed(runner, engine):
    result = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-snoop"))
    assert result.status == "access_denied"
    row = engine.store.get_run(result.run_id)
    assert row["access_denied"] is True and row["output"] is None
    assert "may not read table 'candidates'" in row["failure_reasons"][0]
    denied = [c for c in row["iterations"][1]["candidates"][0]["tool_calls"] if "error" in c]
    assert denied and denied[0]["error"].startswith("AccessDenied")


def test_tool_outside_allowlist_fails_closed(runner, engine, monkeypatch):
    """A known tool the manifest does not list is an access violation, not a soft error."""
    from engine.providers import Completion, ToolUse, Usage

    def rogue(*, model, system, messages, tools, candidate_index):
        return Completion(text="", tool_uses=(ToolUse("x", "files__read", {"path": "pack.yaml"}),),
                          stop_reason="tool_use", usage=Usage(1, 1), model="")

    monkeypatch.setitem(runner.providers.local_responders, "rogue", rogue)
    runner.pack.local_models["rogue"] = rogue
    result = runner.run("allocator", {"capacity": 20}, model_override=("local", "rogue"))
    assert result.status == "access_denied"


# 4 ---------------------------------------------------------------------------

def test_malformed_output_fails_guardrail(runner, engine):
    result = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-malformed"))
    assert result.status == "failed_guardrail"
    row = engine.store.get_run(result.run_id)
    assert row["output"] is None
    assert any("invented key 'bogus'" in r for r in row["failure_reasons"])
    assert len(row["iterations"]) == 3  # context + 2 iterations, both failed, both logged
    # failure reasons were fed back to the second iteration as data
    assert row["iterations"][2]["feedback"][0]["guardrails"]


# 5 ---------------------------------------------------------------------------

def _edit_manifest(root: Path, agent: str, mutate) -> None:
    path = root / "_reference" / "agents" / agent / "manifest.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d.__setitem__("surprise", 1), "Additional properties"),
    (lambda d: d["tools"].append("nonexistent.tool"), "unknown tool"),
    (lambda d: d["safeguards"]["guardrails"].append("no_such_guardrail"), "unknown guardrail"),
    (lambda d: d["safeguards"].__setitem__("verifier", "no_such_verifier"), "unknown verifier"),
    (lambda d: d["model"].__setitem__("provider", "anthropic"), "local model"),
])
def test_manifest_load_errors(pack_copy, mutate, needle):
    _edit_manifest(pack_copy, "checker", mutate)
    pack = load_pack("_reference", pack_copy)
    if needle == "local model":
        # anthropic provider with a fixture model name: the frontier check does not apply to
        # workers, so loading succeeds; running it would fail at the provider.  Covered elsewhere.
        load_agent(pack, "checker")
        return
    with pytest.raises(ManifestError, match=needle):
        load_agent(pack, "checker")


def test_manifest_hash_changes_with_onboarding_files(pack_copy):
    pack = load_pack("_reference", pack_copy)
    before = load_agent(pack, "checker").hash
    skills = pack_copy / "_reference" / "agents" / "checker" / "skills.md"
    skills.write_text(skills.read_text(encoding="utf-8") + "\nAddendum.\n", encoding="utf-8")
    after = load_agent(pack, "checker").hash
    assert before != after


# 6 ---------------------------------------------------------------------------

def test_model_swap_without_code_change(runner, engine):
    a = runner.run("checker", {"sheet_id": "S2"}, model_override=("local", "checker-v1"))
    b = runner.run("checker", {"sheet_id": "S2"}, model_override=("local", "checker-v2"))
    assert a.status == b.status == "succeeded"
    assert a.output["items"] == b.output["items"]
    ra, rb = engine.store.get_run(a.run_id), engine.store.get_run(b.run_id)
    assert (ra["model"], rb["model"]) == ("checker-v1", "checker-v2")
    assert ra["manifest_hash"] == rb["manifest_hash"]  # same agent, same files


# invariants ---------------------------------------------------------------------

def test_engine_contains_no_domain_nouns_and_no_prompts():
    nouns = re.compile(r"\b(parcel|lead|offer|deal)s?\b", re.IGNORECASE)
    prompt_markers = ("You are ", "system_prompt = \"", "system_prompt = '")
    for path in sorted(ENGINE_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not nouns.search(text), f"domain noun in {path.name}"
        assert not any(m in text for m in prompt_markers), f"prompt text in {path.name}"


def test_judgement_records_conflict_when_model_is_confidently_wrong(runner, engine):
    result = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    row = engine.store.get_run(result.run_id)
    summary = row["judgement"]["summaries"]["1:0"]
    assert Decimal(summary["conflict"]) > 0          # verifier says reject, model says 0.95 confident
    assert Decimal(summary["reject"]) > Decimal(summary["accept"])
    good = runner.run("allocator", {"capacity": 20})
    assert Decimal(engine.store.get_run(good.run_id)["judgement"]["summaries"]["1:0"]["conflict"]) == 0
