"""PREREG A22: SETTLED.md, the founder's document, RATIFIED by the operator on 2026-11-04.
From that line on its sha256 is a frozen-file gate (R89): no session edits it; a change is
a new document with a new name and a new ratification. The grader's arithmetic must still be
the document's. Offline.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from rights_events import agent_arena as runner
from rights_events.adapters.agent_arena import settled_event  # noqa: F401  (the rule the document binds)

SETTLED = Path(runner.__file__).resolve().parents[1] / "contracts" / "agent_record" / "SETTLED.md"
FROZEN_SHA = "c6b590de2289de698053a203e22941bafd55e558f0d5947ac8a4b40274042878"


def _lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def test_settled_md_is_frozen_at_its_ratified_sha():
    assert hashlib.sha256(_lf(SETTLED)).hexdigest() == FROZEN_SHA


def test_settled_md_is_ratified_by_the_operator_on_its_last_line():
    text = _lf(SETTLED).decode("utf-8")
    last = text.rstrip("\n").splitlines()[-1]
    assert last.startswith("ratified 2026-11-04 (the operator")
    assert "Not yet ratified" not in text
    assert "7. The machine never edits this document. The operator may." in text


def test_the_graders_rule_is_the_documents_arithmetic():
    """R89: realized_ex_funding = sum closedPnl - sum fee; net_with_funding adds sum funding.usdc."""
    import inspect
    from rights_events.adapters import agent_arena as adapter
    src = inspect.getsource(adapter.settle)
    assert '"realized_ex_funding": closed - fees' in src
    assert '"net_with_funding": closed - fees + funding_sum' in src
    text = _lf(SETTLED).decode("utf-8")
    assert "closedPnl" in text and "funding" in text and "FULL" in text and "NONE" in text
