"""Disagreement between passing candidates (JH-C11 G-B3, Brown: two agents reaching different answers is a
signal to reconcile, not to pick silently).

With ``search_width > 1`` (or ``stop_when: iterations_exhausted``) several candidates may pass.  Their outputs are
projected on the agent's compare fields (the header of eval/golden.jsonl; the whole output when there is none);
when the projections differ the loop writes a ``<pack>.disagreement`` event and, under ``loop.reconcile``, runs
one reconcile turn whose feedback lists the disagreeing projections.  A passing reconcile candidate is chosen;
otherwise the most-accepted original stands.
"""

from __future__ import annotations

import json

from engine.hashing import sha256_json
from engine.schema import get_path


def compare_fields(agent) -> tuple[str, ...] | None:
    path = agent.dir / "eval" / "golden.jsonl"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            fields = json.loads(line).get("compare")
            return tuple(fields) if fields else None
    return None


def project(output, fields: tuple[str, ...] | None):
    if fields is None:
        return output
    out = {}
    for f in fields:
        try:
            out[f] = get_path(output, f)
        except (KeyError, IndexError, ValueError, TypeError):
            out[f] = None
    return out


def disagreement(agent, keyed_outputs: list[tuple[str, object]]) -> dict | None:
    """``[(candidate key, output)]`` -> {fields, candidates: [{key, values, values_sha256}]} when they differ."""
    fields = compare_fields(agent)
    rows = [{"key": k, "values": project(o, fields), "values_sha256": sha256_json(project(o, fields))}
            for k, o in keyed_outputs]
    if len({r["values_sha256"] for r in rows}) < 2:
        return None
    return {"fields": list(fields) if fields else ["*"], "candidates": rows}
