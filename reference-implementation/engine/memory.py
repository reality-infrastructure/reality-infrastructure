"""Three-tier memory.

Working     the run's context: onboarding pack + grounding + long-term reads + feedback
Long-term   event-log queries + the agent's last N outputs with their verdicts
Compaction  rolling summaries of events older than ``after_days``, written by the
            designated summary agent as ``compaction.summary`` events whose
            citations resolve; raw events are never replaced.

Every read here goes through the tool registry, so it is access-checked and
appears in the trace as a tool call with origin ``grounding`` or ``memory``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from engine.errors import EngineError, ManifestError
from engine.events import COMPACTION_TYPE, EventLog
from engine.hashing import canonical_json
from engine.runtime import iso, parse_iso
from engine.store import Engine
from engine.tools import ToolContext

_CHARS_PER_TOKEN = 4


def _parse_query_ref(ref: str) -> dict:
    """``entity_type=x;event_type=y;limit=20`` -> kwargs for events.query."""
    out: dict[str, Any] = {}
    for part in ref.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ManifestError(f"event_query ref {ref!r}: expected key=value pairs")
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "limit":
            out[k] = int(v)
        elif k in ("entity_type", "entity_id", "event_type", "since"):
            out[k] = v
        else:
            raise ManifestError(f"event_query ref {ref!r}: unknown key {k!r}")
    return out


def _estimate_tokens(obj) -> int:
    return len(canonical_json(obj)) // _CHARS_PER_TOKEN


def assemble_working_context(agent, ctx: ToolContext, run_input: dict) -> dict:
    """Build the run's context window.  Deterministic for a given store state."""
    grounding = []
    for src in agent.grounding:
        kind, ref = src["kind"], src["ref"]
        if kind == "table":
            data = ctx.call("tables.read", {"table": ref, "limit": int(src.get("limit", 1000))},
                            origin="grounding")
        elif kind == "file":
            data = ctx.call("files.read", {"path": ref}, origin="grounding")
        elif kind == "event_query":
            q = _parse_query_ref(ref)
            if "limit" in src:
                q["limit"] = int(src["limit"])
            data = ctx.call("events.query", q, origin="grounding")
        elif kind == "agent_output":
            runs = ctx.engine.store.list_runs(pack=agent.pack.name, agent=ref, status="succeeded")
            runs = runs[-int(src.get("limit", 5)):]
            data = [ctx.call("agent_output.read", {"run_id": r["run_id"]}, origin="grounding")
                    for r in runs]
        else:  # unreachable: manifest schema bounds kind
            raise ManifestError(f"unknown grounding kind {kind!r}")
        grounding.append({"kind": kind, "ref": ref, "data": data})

    memory: dict[str, Any] = {"events": [], "prior_outputs": [], "compaction": []}
    long_term = agent.memory.get("long_term")
    if long_term is not None:
        for q in long_term.get("event_queries") or []:
            args = {k: v for k, v in q.items() if v is not None}
            args.setdefault("limit", 50)
            memory["events"].append({"query": args,
                                     "rows": ctx.call("events.query", args, origin="memory")})
        n = int(long_term.get("prior_outputs", 0))
        if n > 0:
            runs = ctx.engine.store.list_runs(pack=agent.pack.name, agent=agent.name, status="succeeded")
            for r in runs[-n:]:
                out = ctx.call("agent_output.read", {"run_id": r["run_id"]}, origin="memory")
                out["human_verdict"] = r["human_verdict"]
                out["verdict_reason"] = r["verdict_reason"]
                memory["prior_outputs"].append(out)
        memory["compaction"] = ctx.call(
            "events.query", {"event_type": COMPACTION_TYPE, "entity_type": "compaction",
                             "entity_id": agent.name, "limit": 10}, origin="memory")

    context = {
        "agent": {"name": agent.name, "role": agent.role, "version": agent.version},
        "input": run_input,
        "onboarding": {"skills": agent.skills, "workflow": agent.workflow},
        "grounding": grounding,
        "memory": memory,
        "truncation": [],
    }
    _fit_budget(context, int(agent.memory["working"]["max_tokens"]))
    return context


def _fit_budget(context: dict, max_tokens: int) -> None:
    """Deterministic trimming, cheapest-to-lose first.  Truncation is recorded."""
    def over() -> bool:
        return _estimate_tokens(context) > max_tokens

    if not over():
        return
    mem = context["memory"]
    while over() and mem["prior_outputs"]:
        mem["prior_outputs"].pop(0)
        context["truncation"].append("dropped oldest prior output")
    while over() and any(e["rows"] for e in mem["events"]):
        for e in mem["events"]:
            if e["rows"]:
                e["rows"].pop()
                context["truncation"].append(f"dropped oldest event for query {e['query']}")
                break
    while over() and any(isinstance(g["data"], list) and g["data"] for g in context["grounding"]):
        for g in context["grounding"]:
            if isinstance(g["data"], list) and g["data"]:
                g["data"].pop()
                context["truncation"].append(f"dropped last grounding row of {g['kind']}:{g['ref']}")
                break
    if over():
        raise EngineError(
            f"working memory budget {max_tokens} tokens cannot fit the onboarding pack and input")


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------

def compaction_window(engine: Engine, events: EventLog, agent, *, now) -> tuple[list[dict], dict] | None:
    """Events older than after_days not yet covered by this agent's last summary."""
    cfg = agent.memory.get("compaction")
    if cfg is None:
        raise ManifestError(f"agent {agent.name!r} declares no compaction policy")
    cutoff = now - timedelta(days=int(cfg["after_days"]))
    prior = events.query(event_type=COMPACTION_TYPE, entity_type="compaction",
                         entity_id=agent.name, limit=1)
    since = prior[0]["payload"]["range"]["to_observed_at"] if prior else None
    rows = engine.store.query_events(since=since, until=iso(cutoff), limit=100000, ascending=True)
    # the prior summary's last event is its own upper bound (inclusive); start strictly after it
    rows = [r for r in rows if r["event_type"] != COMPACTION_TYPE
            and (since is None or r["observed_at"] > since)]
    if not rows:
        return None
    rng = {"from_observed_at": rows[0]["observed_at"], "to_observed_at": rows[-1]["observed_at"],
           "event_count": len(rows)}
    return rows, rng


def compact(engine: Engine, events: EventLog, agent, run_agent: Callable[[str, dict], dict], *, now) -> dict | None:
    """Run the summary agent over the window and log a cited compaction.summary event.

    Returns the event row, or None when there is nothing to compact.  The
    summary agent's own run is guarded like any other run; the engine then
    re-checks that every citation names an event inside the window before it
    writes the summary.  Raw events are untouched.
    """
    window = compaction_window(engine, events, agent, now=now)
    if window is None:
        return None
    rows, rng = window
    summary_agent = agent.memory["compaction"]["summary_agent"]
    result = run_agent(summary_agent, {"events": [
        {k: r[k] for k in ("event_id", "entity_type", "entity_id", "event_type", "payload", "observed_at")}
        for r in rows], "range": rng, "for_agent": agent.name})
    if result["status"] != "succeeded":
        raise EngineError(f"compaction summary run {result['run_id']} failed: {result['failure_reasons']}")
    output = result["output"]
    window_ids = {r["event_id"] for r in rows}
    citations = output.get("citations") or []
    cited_ids = {c["ref"].split(":", 2)[2] for c in citations if isinstance(c.get("ref"), str)}
    if not cited_ids or not cited_ids <= window_ids:
        raise EngineError("compaction summary cites events outside the compacted window")
    return events.append(
        entity_type="compaction", entity_id=agent.name, event_type=COMPACTION_TYPE,
        payload={"agent": agent.name, "summary": output["summary"], "range": rng,
                 "citations": [{"ref": c["ref"]} for c in citations]},
        source=f"agent:{summary_agent}", source_ref=result["run_id"],
        observed_at=parse_iso(rng["to_observed_at"]))
