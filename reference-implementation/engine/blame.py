"""Trace blame: where a wrong output came from (JH-C11 wpF, G-M8).

    python -m engine.blame <run_id> [--against RUN_ID] [--record] [--db DSN]

Musk: most of the time a model "just did something wrong.  It's a bug effectively."  A bug has an
origin.  For a failed or overridden run this walks the trace (run -> iteration -> candidate -> provider
and tool calls), diffs the working context against a followed run of the same agent on the same input
(or the latest followed run when none matches, or ``--against``), and names the first divergent item and
one origin:

  judge              the operator followed a run the judge had marked otherwise
  tool_error         a tool call inside the run returned an error
  memory_truncated   a grounding item the followed run had was dropped by the working-memory budget
  grounding_missing  a grounding item (or a cited source) is absent from the context and nothing dropped it
  prompt             same context, different instructions (manifest/onboarding/prompt hash differs)
  model              same context, same instructions, different output

``blame_week`` (called by the autoloop each cycle) records a ``<pack>.blame`` event once per run; the
crank aggregates the origins per agent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

from engine.analytics import JUDGEABLE, run_context, week_events, week_runs
from engine.citations import iter_citations
from engine.errors import EngineError
from engine.freshness import item_id

ORIGINS = ("judge", "tool_error", "memory_truncated", "grounding_missing", "prompt", "model")
_REF = re.compile(r"\b(?:table|event|file|run):[A-Za-z0-9_./\-]+:[A-Za-z0-9_.\-*]+")


def _grounding_items(pack, ctx: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for g in ctx.get("grounding") or []:
        data = g["data"] if isinstance(g["data"], list) else [g["data"]]
        out[f"{g['kind']}:{g['ref']}"] = [item_id(pack, g["kind"], g["ref"], d) for d in data]
    return out


def reference_run(engine, row: dict) -> dict | None:
    """A followed run of the same agent: on the same input when one exists, else the latest."""
    rows = [r for r in engine.store.list_runs(pack=row["pack"], agent=row["agent"], status="succeeded")
            if r["human_verdict"] == "followed" and r["run_id"] != row["run_id"]]
    same = [r for r in rows if r["input_hash"] == row["input_hash"]]
    return (same or rows or [None])[-1]


def blame(engine, pack, run_id: str, *, against: str | None = None) -> dict:
    row = engine.store.get_run(run_id)
    if row is None:
        raise EngineError(f"no run {run_id!r}")
    base = {"run_id": run_id, "agent": row["agent"], "against_run_id": None}
    verdicts = [e for e in engine.store.query_events(event_type=f"{pack.name}.verdict", limit=100000, ascending=True)
                if e["payload"]["run_id"] == run_id]
    agent_v = [e["payload"]["verdict"] for e in verdicts if e["source"].startswith("agent:")]
    human_v = [e["payload"]["verdict"] for e in verdicts if e["source"] == "human"]
    if agent_v and human_v and human_v[-1] == "followed" and agent_v[-1] != "followed":
        return {**base, "origin": "judge", "item": f"the judge said {agent_v[-1]}; the operator followed the run"}
    for it in row["iterations"]:
        for cand in it.get("candidates") or []:
            for call in cand.get("tool_calls") or []:
                if "error" in call:
                    return {**base, "origin": "tool_error", "item": f"{call['tool']}: {call['error']}"[:300]}
    ctx = run_context(row)
    ref = engine.store.get_run(against) if against else reference_run(engine, row)
    if against and ref is None:
        raise EngineError(f"no run {against!r} to blame against")
    ref_ctx = run_context(ref) if ref else None
    trunc = (ctx or {}).get("truncation") or []
    if ctx is not None and ref_ctx is not None:
        base["against_run_id"] = ref["run_id"]
        mine, theirs = _grounding_items(pack, ctx), _grounding_items(pack, ref_ctx)
        missing = [f"{source}:{item}" for source in sorted(theirs) for item in theirs[source]
                   if item not in set(mine.get(source, []))]
        if missing:
            cited = {c.get("ref") for _, c in iter_citations(ref["output"] or {})}
            first = next((m for m in missing if m in cited), missing[0])     # a row the followed run cited is the needed one
            dropped = any(first.rsplit(":", 1)[0] in t for t in trunc)
            return {**base, "origin": "memory_truncated" if dropped else "grounding_missing", "item": first}
        if row["manifest_hash"] != ref["manifest_hash"]:
            return {**base, "origin": "prompt", "item": f"instructions hash {ref['manifest_hash'][:12]} -> {row['manifest_hash'][:12]}"}
        return {**base, "origin": "model", "item": (row["failure_reasons"] or [row["verdict_reason"] or "output differs"])[0][:300]}
    reasons = row["failure_reasons"] or []
    for r in reasons:
        if any(g in r for g in ("citations_resolve", "no_fabrication", "cited_values_match")):
            m = _REF.search(r)
            if m and any(m.group(0).rsplit(":", 1)[0] in t for t in trunc):
                return {**base, "origin": "memory_truncated", "item": m.group(0)}
            return {**base, "origin": "grounding_missing", "item": m.group(0) if m else r[:300]}
    if trunc:
        return {**base, "origin": "memory_truncated", "item": trunc[0][:300]}
    return {**base, "origin": "model", "item": (reasons or [row["verdict_reason"] or "output differs"])[0][:300]}


def record(engine, pack, result: dict) -> dict:
    from engine.events import EventLog
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=result["run_id"], event_type=f"{pack.name}.blame",
        payload={k: result[k] for k in ("run_id", "agent", "origin", "item", "against_run_id")},
        source="pipeline:blame", source_ref=result["run_id"])


def _needs_blame(row: dict) -> bool:
    return row["role"] in JUDGEABLE and (row["status"] != "succeeded" or row["human_verdict"] in ("overridden", "wrong")
                                         or (row["human_verdict"] == "followed" and row.get("verdict_source") == "human"))


def blame_week(engine, pack, week: str) -> list[dict]:
    """Blame every failed or overridden run of the week (and every operator-followed run the judge contested) once."""
    done = {e["payload"]["run_id"] for e in week_events(engine, pack, "blame")}
    out = []
    for row in week_runs(engine, pack, week):
        if row["run_id"] in done or not _needs_blame(row):
            continue
        result = blame(engine, pack, row["run_id"])
        if row["status"] == "succeeded" and row["human_verdict"] == "followed" and result["origin"] != "judge":
            continue
        record(engine, pack, result)
        out.append(result)
    return out


def report(engine, pack, week: str) -> list[dict]:
    by_agent: dict[str, Counter] = defaultdict(Counter)
    items: dict[str, list[str]] = defaultdict(list)
    for e in week_events(engine, pack, "blame", week):
        p = e["payload"]
        by_agent[p["agent"]][p["origin"]] += 1
        if len(items[p["agent"]]) < 5:
            items[p["agent"]].append(f"{p['origin']}: {p['item']}")
    return [{"agent": a, "origins": dict(sorted(by_agent[a].items())), "examples": items[a]} for a in sorted(by_agent)]


def render(report_: dict) -> list[str]:
    L = ["", "## Blame (origin of wrong outputs)", ""]
    for b in report_["blame"]:
        L.append(f"- {b['agent']}: " + ", ".join(f"{k} {v}" for k, v in b["origins"].items()))
        L += [f"  - {x}" for x in b["examples"]]
    if not report_["blame"]:
        L.append("- nothing blamed this week")
    return L


def main(argv: list[str] | None = None) -> int:
    from engine.packs import load_pack
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.blame")
    p.add_argument("run_id")
    p.add_argument("--against")
    p.add_argument("--record", action="store_true", help="append the <pack>.blame event")
    p.add_argument("--db")
    a = p.parse_args(argv)
    try:
        engine = Engine.open(a.db)
        try:
            row = engine.store.get_run(a.run_id)
            if row is None:
                raise EngineError(f"no run {a.run_id!r}")
            pack = load_pack(row["pack"])
            result = blame(engine, pack, a.run_id, against=a.against)
            if a.record:
                result["event_id"] = record(engine, pack, result)["event_id"]
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
