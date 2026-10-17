"""C4 — model economics.

Acceptance: matrix file generated for _reference/allocator across >= 2 models;
downgrade without a parity file -> load error.
"""

from __future__ import annotations

import json

import pytest
import yaml

from engine.errors import ManifestError
from engine.eval import run_eval, write_matrix
from engine.manifest import load_agent
from engine.packs import load_pack
from engine.scaffold import new_domain


def test_matrix_across_two_models(engine, pack, tmp_path):
    report = run_eval(engine, pack, "allocator", models=["local/allocator-v1", "local/allocator-greedy"])
    rows = {r["model"]: r for r in report["models"]}
    assert rows["local/allocator-v1"]["score"] == "1.0000"
    assert rows["local/allocator-greedy"]["score"] == "0.5000"
    assert all(r["parity"] is None for r in rows.values())   # frontier absent from a fixture matrix
    md, js = write_matrix(tmp_path, report, "2026-10-16")
    assert md.name == "matrix-2026-10-16.md" and js.exists()
    text = md.read_text(encoding="utf-8")
    assert "| `local/allocator-greedy` | 0.5000 | 1/2 |" in text
    assert json.loads(js.read_text(encoding="utf-8"))["agent"] == "_reference/allocator"


def _real_pack(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    new_domain("econ_pack", root)
    return root


def _set_model(root, agent, provider, name):
    m = root / "econ_pack" / "agents" / agent / "manifest.yaml"
    doc = yaml.safe_load(m.read_text(encoding="utf-8"))
    doc["model"]["provider"], doc["model"]["name"] = provider, name
    m.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def test_downgrade_without_parity_is_refused(tmp_path):
    root = _real_pack(tmp_path)
    _set_model(root, "worker", "anthropic", "claude-sonnet-5-5")
    with pytest.raises(ManifestError, match="no eval/matrix"):
        load_agent(load_pack("econ_pack", root), "worker")
    eval_dir = root / "econ_pack" / "agents" / "worker" / "eval"
    matrix = {"agent": "econ_pack/worker", "frontier": "openai_compat/deepseek-flash", "frontier_score": "0.9",
              "models": [{"model": "openai_compat/deepseek-flash", "score": "0.9", "parity": True},
                         {"model": "anthropic/claude-sonnet-5-5", "score": "0.8", "parity": False}]}
    (eval_dir / "matrix-2026-10-01.json").write_text(json.dumps(matrix), encoding="utf-8")
    with pytest.raises(ManifestError, match="downgrade refused"):
        load_agent(load_pack("econ_pack", root), "worker")
    matrix["models"][1].update(score="0.9", parity=True)
    (eval_dir / "matrix-2026-10-02.json").write_text(json.dumps(matrix), encoding="utf-8")
    assert load_agent(load_pack("econ_pack", root), "worker").model.name == "claude-sonnet-5-5"


def test_orchestrator_never_downgrades_even_with_parity(tmp_path):
    root = _real_pack(tmp_path)
    _set_model(root, "orchestrator", "anthropic", "claude-opus-5-5")
    eval_dir = root / "econ_pack" / "agents" / "orchestrator" / "eval"
    (eval_dir / "matrix-2026-10-01.json").write_text(json.dumps({"models": [
        {"model": "anthropic/claude-opus-5-5", "score": "1.0", "parity": True}]}), encoding="utf-8")
    with pytest.raises(ManifestError, match="orchestrator must run the frontier"):
        load_agent(load_pack("econ_pack", root), "orchestrator")


def test_fixture_provider_forbidden_in_real_pack(tmp_path):
    root = _real_pack(tmp_path)
    _set_model(root, "worker", "local", "anything")
    with pytest.raises(ManifestError, match="fixture provider"):
        load_agent(load_pack("econ_pack", root), "worker")
