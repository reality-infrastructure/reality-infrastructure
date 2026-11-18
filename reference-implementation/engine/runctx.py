"""What a run carries beyond its input (JH-C11 wpH): session linkage, a forked parent context, a shared scratch,
its fan-out siblings, and the replay it belongs to.

- Session (G-P13, the panel: a user revises, changes their mind, and the trace must hold the whole exchange).  A
  run may name a ``session_id`` and the run it ``supersedes``; both are run columns bound to the ledger.  The run's
  context carries the session's earlier turns (input, output, status, verdict), the last ``memory.session_turns``.
- Fork (G-B4, Brown: a sub-agent that starts from the parent's working context, not only its input).  An
  orchestrator whose manifest sets ``loop.fork_context: true`` starts each child with its own context plus the
  parent's under ``forked``, with the parent context's sha256; the child row records ``forked_from``.
- Shared scratch (G-B4).  Workers of one sweep or one fan-out share findings as ``<pack>.scratch`` events
  (written only when the writing candidate is certified); later workers find them in ``memory.scratch``, oldest
  dropped first beyond ``memory.shared_scratch.max_tokens``.
- Peers (G-B3).  A fan-out child sees ``{group, part, parts}`` so it can address a sibling with siblings.message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.errors import EngineError
from engine.hashing import canonical_json, sha256_json

_CHARS_PER_TOKEN = 4


@dataclass
class RunOptions:
    session_id: str | None = None
    supersedes_run_id: str | None = None
    scratch_scope: str | None = None
    fanout_group: str | None = None
    part: int | None = None
    parts: int | None = None
    bus: Any = None                       # engine.fanout.Bus of the fan-out group
    forked: dict | None = None            # {"from_run_id", "context_sha256", "context"}
    may_clarify: bool = False             # a child whose parent still has clarification budget
    replay: Any = None                    # engine.replay.ReplayPlan
    replayed_from: str | None = None
    commit_effects: bool = True           # False on a replay: a re-execution never re-sends effects
    sample: int = 0                       # an eval's draw number (JH-C11 wpA): candidate indices sample*width+c


def resolve_links(engine, pack, agent_name: str, opts: RunOptions) -> dict:
    """The link columns of the new run.  A revision must revise a run of the same agent; it inherits its session."""
    session = opts.session_id
    if opts.supersedes_run_id is not None:
        prior = engine.store.get_run(opts.supersedes_run_id)
        if prior is None or prior["pack"] != pack.name:
            raise EngineError(f"supersedes: no run {opts.supersedes_run_id!r} in pack {pack.name!r}")
        if prior["agent"] != agent_name:
            raise EngineError(f"supersedes: run {opts.supersedes_run_id} is {prior['agent']!r}'s, not {agent_name!r}'s")
        if session is None:
            session = prior.get("session_id")
        elif prior.get("session_id") not in (None, session):
            raise EngineError(f"supersedes: run {opts.supersedes_run_id} belongs to session {prior['session_id']!r}")
    return {"session_id": session, "supersedes_run_id": opts.supersedes_run_id,
            "replayed_from": opts.replayed_from, "forked_from": (opts.forked or {}).get("from_run_id"),
            "fanout_group": opts.fanout_group}


def session_turns(engine, pack, session_id: str, limit: int) -> list[dict]:
    rows = [r for r in engine.store.runs_by_link("session_id", session_id) if r["pack"] == pack.name]
    return [{"run_id": r["run_id"], "agent": r["agent"], "input": r["input"], "output": r["output"],
             "status": r["status"], "verdict": r["human_verdict"], "verdict_reason": r["verdict_reason"],
             "supersedes_run_id": r.get("supersedes_run_id"), "clarification": r.get("clarification")}
            for r in rows][-limit:] if limit > 0 else []


def links(engine, run_id: str) -> dict:
    """Both directions of the revision link, and the session, of one run."""
    row = engine.store.get_run(run_id)
    if row is None:
        raise EngineError(f"no run {run_id!r}")
    return {"run_id": run_id, "session_id": row.get("session_id"), "supersedes": row.get("supersedes_run_id"),
            "superseded_by": [r["run_id"] for r in engine.store.runs_by_link("supersedes_run_id", run_id)]}


def scratch_entries(ctx, scope: str) -> list[dict]:
    rows = ctx.call("events.query", {"entity_type": "agent_run", "entity_id": scope,
                                     "event_type": f"{ctx.pack.name}.scratch", "limit": 500}, origin="memory")
    return [{"event_id": r["event_id"], "agent": r["payload"]["agent"], "run_id": r["payload"]["run_id"],
             "text": r["payload"]["text"], "ref": f"event:events:{r['event_id']}"} for r in reversed(rows)]


def extend_context(engine, agent, ctx, context: dict, opts: RunOptions) -> None:
    """Add what the options carry to an assembled context, then re-fit it to the working budget."""
    from engine.memory import _fit_budget
    if opts.forked is not None:
        context["forked"] = {"from_run_id": opts.forked["from_run_id"],
                             "context_sha256": opts.forked["context_sha256"], "context": opts.forked["context"]}
    if opts.part is not None:
        context["peers"] = {"group": opts.fanout_group, "part": opts.part, "parts": opts.parts}
    session = opts.session_id
    if session is not None:
        ctx.access.check_table("agent_runs", "read")
        context["session"] = {"session_id": session,
                              "turns": session_turns(engine, agent.pack, session, engine.config.shared_memory["session_turns"])}
    scope = opts.scratch_scope
    if scope is not None and "events" in (agent.access.tables_read | agent.access.tables_write):
        entries = scratch_entries(ctx, scope)
        budget = engine.config.shared_memory["scratch_max_tokens"] * _CHARS_PER_TOKEN
        while entries and len(canonical_json(entries)) > budget:
            entries.pop(0)
            context["truncation"].append("dropped oldest shared scratch entry")
        context["memory"]["scratch"] = entries
    _fit_budget(context, int(agent.memory["working"]["max_tokens"]))


def context_hash(context: dict) -> str:
    return sha256_json(context)


def run_session_case(runner, agent_name: str, prior_turns: tuple, final_input: dict, **run_kw):
    """A golden case that is a session: the prior turns run in order in one fresh session, then the final turn,
    which is the one scored.  Each turn sees the earlier ones in its context."""
    if not prior_turns:
        return runner.run(agent_name, final_input, **run_kw)
    session = f"eval:{runner.engine.ids.new()}"
    for turn in prior_turns:
        runner.run(agent_name, turn, session_id=session, **run_kw)
    return runner.run(agent_name, final_input, session_id=session, **run_kw)
