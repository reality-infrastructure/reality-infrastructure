"""C6 — blueprint scaffolder.

Acceptance: scaffolded pack passes engine.validate with zero engine code
changes.  (The first REAL domain pack lives in its own repo and needs >= 10
real golden cases before code; that half is a PLAN GATE, not a test.)
"""

from __future__ import annotations

import pytest

from engine.errors import ManifestError
from engine.scaffold import main as scaffold_main
from engine.scaffold import new_domain
from engine.validate import main as validate_main
from engine.validate import validate_pack


def test_scaffold_loads_and_validates(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    dest = new_domain("acme_ops", root)
    assert (dest / "problem.md").exists() and (dest / "VENDOR-SCORECARD.md").exists()
    info = validate_pack("acme_ops", root)
    assert info["agents"] == {"orchestrator": "orchestrator", "worker": "worker"}
    assert "acme_ops.todo_observed" in info["event_types"]
    assert "acme_ops.verdict" in info["event_types"] and "compaction.summary" in info["event_types"]
    assert info["golden_cases"] == {"orchestrator": 0, "worker": 0}
    assert not any("__PACK__" in p.read_text(encoding="utf-8")
                   for p in dest.rglob("*") if p.is_file() and p.suffix in {".py", ".yaml", ".md", ".json", ".jsonl"})


def test_scaffold_refuses_overwrite_and_reserved_names(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    new_domain("acme_ops", root)
    with pytest.raises(ManifestError, match="refusing to overwrite"):
        new_domain("acme_ops", root)
    with pytest.raises(ManifestError, match="reserved"):
        new_domain("json", root)
    with pytest.raises(ManifestError, match="must match"):
        new_domain("Bad-Name", root)


def test_scaffold_cli(tmp_path, capsys):
    root = tmp_path / "packs"
    root.mkdir()
    assert scaffold_main(["new-domain", "acme_ops", "--root", str(root)]) == 0
    assert "scaffolded" in capsys.readouterr().out
    assert validate_main(["acme_ops", "--root", str(root)]) == 0
    assert capsys.readouterr().out.startswith("OK acme_ops fixture=False")
