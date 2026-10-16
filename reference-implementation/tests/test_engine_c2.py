"""C2 — proposer/verifier, specialist slot, orchestrator composition.

Acceptance:
1. seeded infeasible proposal -> failed_verifier
2. seeded misstated figure -> verifier recompute mismatch -> violation
3. second specialist in a pack without ADR -> load error
4. orchestrator manifest with non-frontier model swap -> load error
5. orchestrator run -> child specialist run linked by parent_run_id; every number
   in the brief resolves via citations
"""

from __future__ import annotations

import shutil

import pytest
import yaml

from engine.citations import CitationResolver, iter_citations
from engine.errors import ManifestError
from engine.manifest import load_agent, load_all_agents
from engine.packs import load_pack


def test_infeasible_proposal_fails_verifier(runner, engine):
    r = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-infeasible"))
    assert r.status == "failed_verifier" and r.output is None
    cand = engine.store.get_run(r.run_id)["iterations"][1]["candidates"][0]
    assert all(g["passed"] for g in cand["guardrails"])
    assert not cand["verifier"]["certified"]
    assert any("infeasible" in v for v in cand["verifier"]["violations"])


def test_misstated_figure_is_a_recompute_violation(runner, engine):
    r = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    assert r.status == "failed_verifier"
    cand = engine.store.get_run(r.run_id)["iterations"][1]["candidates"][0]
    assert cand["verifier"]["recomputed"]["total_value"] == 110
    assert any("total_value misstated: proposal says 111, recomputed 110" == v
               for v in cand["verifier"]["violations"])


def test_suboptimal_proposal_is_rejected(runner):
    r = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-greedy"))
    assert r.status == "failed_verifier"
    assert any("suboptimal" in reason for reason in r.failure_reasons)


def test_second_specialist_needs_adr(pack_copy):
    agents = pack_copy / "_reference" / "agents"
    shutil.copytree(agents / "allocator", agents / "allocator2")
    m = agents / "allocator2" / "manifest.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace("name: allocator", "name: allocator2"), encoding="utf-8")
    with pytest.raises(ManifestError, match="max_specialists=1"):
        load_all_agents(load_pack("_reference", pack_copy))
    pack_yaml = pack_copy / "_reference" / "pack.yaml"
    pack_yaml.write_text(pack_yaml.read_text(encoding="utf-8").replace("max_specialists: 1", "max_specialists: 2"),
                         encoding="utf-8")
    with pytest.raises(ManifestError, match="requires an ADR"):
        load_all_agents(load_pack("_reference", pack_copy))
    (pack_copy / "_reference" / "adr").mkdir()
    (pack_copy / "_reference" / "adr" / "0001-two-specialists.md").write_text("# ADR\nwhy\n", encoding="utf-8")
    agents_loaded = load_all_agents(load_pack("_reference", pack_copy))
    assert {n for n, a in agents_loaded.items() if a.role == "specialist"} == {"allocator", "allocator2"}


def test_specialist_requires_verifier_and_problem(pack_copy):
    m = pack_copy / "_reference" / "agents" / "allocator" / "manifest.yaml"
    doc = yaml.safe_load(m.read_text(encoding="utf-8"))
    doc["safeguards"]["verifier"] = None
    doc["loop"]["stop_when"] = "all_guardrails_pass"
    m.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(ManifestError, match="requires a verifier"):
        load_agent(load_pack("_reference", pack_copy), "allocator")
    (pack_copy / "_reference" / "problem.md").unlink()
    with pytest.raises(ManifestError):
        load_agent(load_pack("_reference", pack_copy), "allocator")


def test_orchestrator_cannot_leave_the_frontier(pack_copy):
    m = pack_copy / "_reference" / "agents" / "briefer" / "manifest.yaml"
    doc = yaml.safe_load(m.read_text(encoding="utf-8"))
    doc["model"]["provider"], doc["model"]["name"] = "anthropic", "claude-sonnet-5-5"
    m.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(ManifestError, match="must run the frontier model"):
        load_agent(load_pack("_reference", pack_copy), "briefer")
    doc["model"]["name"] = "claude-fable-5-1"
    m.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert load_agent(load_pack("_reference", pack_copy), "briefer").model.name == "claude-fable-5-1"


def test_only_orchestrators_call_agents_and_only_one_level(pack_copy):
    m = pack_copy / "_reference" / "agents" / "checker" / "manifest.yaml"
    doc = yaml.safe_load(m.read_text(encoding="utf-8"))
    doc["tools"].append("agent._reference.allocator")
    m.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(ManifestError, match="only an orchestrator may call"):
        load_agent(load_pack("_reference", pack_copy), "checker")


def test_orchestrator_composes_specialist_with_linkage_and_citations(runner, engine, pack):
    r = runner.run("briefer", {"capacity": 50})
    assert r.status == "succeeded"
    parent = engine.store.get_run(r.run_id)
    children = engine.store.list_runs(parent_run_id=r.run_id)
    assert len(children) == 1 and children[0]["agent"] == "allocator" and children[0]["status"] == "succeeded"
    child = children[0]
    # the orchestrator's cost includes the child's
    assert parent["cost_usd"] >= child["cost_usd"]
    # every figure resolves and equals the certified source
    resolver = CitationResolver(engine=engine, pack=pack, access=runner.agent("briefer").access,
                                kinds=engine.config.citation_kinds)
    figures = r.output["figures"]
    assert {f["name"] for f in figures} == {"total_value", "total_weight"}
    for f in figures:
        resolved = resolver.resolve(f["citations"][0])
        assert resolved.citation.id == child["run_id"]
        assert resolved.value() == f["value"]
    assert r.output["headline"] == "total_value=270 total_weight=50 selected=4 records_seen=0"
    assert all(c["ref"].startswith(("run:", "event:")) for _, c in iter_citations(r.output))
    # the child's trace is independent and replayable
    from engine.replay import verify_run
    assert verify_run(engine, child["run_id"])["byte_identical"]


def test_orchestrator_cannot_cite_an_uncertified_run(runner, engine, pack):
    bad = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-infeasible"))
    resolver = CitationResolver(engine=engine, pack=pack, access=runner.agent("briefer").access,
                                kinds=engine.config.citation_kinds)
    from engine.errors import CitationError
    with pytest.raises(CitationError, match="did not succeed"):
        resolver.resolve({"ref": f"run:agent_runs:{bad.run_id}", "field": "total_value"})
