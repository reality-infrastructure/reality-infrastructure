"""Generic tools the engine ships.  Descriptions and schemas come from config/tools.yaml.

- events.query / events.append   the event log, through EventLog (declared types only)
- agent_output.read              a prior certified run's output
- agent_run.read / runs.list     a prior run in full (for a judge) / the run list (for a planner)
- files.read                     a granted file
- tables.read                    a pack table
- agent.<pack>.<name>            call another agent (orchestrator only, one level deep)
"""

from __future__ import annotations

from engine.access import Target
from engine.config import load_config
from engine.errors import ToolError
from engine.tools import ToolContext, ToolRegistry, ToolSpec

AGENT_TOOL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["input"],
    "properties": {"input": {"type": "object"}},
}


def _cfg(tool_id: str) -> dict:
    doc = load_config().tools.get(tool_id)
    if doc is None:
        raise ToolError(f"config/tools.yaml has no entry for {tool_id!r}")
    return doc


def _events_query(args: dict, ctx: ToolContext):
    log = ctx.extra["events"]
    rows = log.query(entity_type=args.get("entity_type"), entity_id=args.get("entity_id"),
                     event_type=args.get("event_type"), since=args.get("since"),
                     limit=int(args.get("limit", 50)))
    return [{k: r[k] for k in ("event_id", "entity_type", "entity_id", "event_type",
                               "payload", "source", "source_ref", "observed_at")} for r in rows]


def _events_append(args: dict, ctx: ToolContext):
    log = ctx.extra["events"]
    row = log.append(entity_type=args["entity_type"], entity_id=args["entity_id"],
                     event_type=args["event_type"], payload=args["payload"],
                     source=f"agent:{ctx.agent.name}", source_ref=ctx.run_id,
                     observed_at=args.get("observed_at"))
    return {"event_id": row["event_id"], "ledger_index": row["ledger_index"],
            "ref": f"event:events:{row['event_id']}"}


def _agent_output_read(args: dict, ctx: ToolContext):
    row = ctx.engine.store.get_run(args["run_id"])
    if row is None:
        raise ToolError(f"no run {args['run_id']!r}")
    return {"run_id": row["run_id"], "agent": row["agent"], "status": row["status"],
            "output": row["output"], "ref": f"run:agent_runs:{row['run_id']}"}


_RUN_FIELDS = ("run_id", "agent", "role", "status", "input", "output", "failure_reasons", "provider", "model",
               "manifest_hash", "cost_usd", "latency_ms", "items_evaluated", "human_verdict", "verdict_source",
               "created_at")


def _trace_summary(iterations: list[dict]) -> list[dict]:
    out = []
    for it in iterations:
        for cand in it.get("candidates", []):
            out.append({
                "iteration": it.get("index"), "candidate": cand.get("index"), "accepted": bool(cand.get("accepted")),
                "tool_calls": [{"tool": c.get("tool"), "args": c.get("args"), "error": c.get("error")}
                               for c in cand.get("tool_calls", [])],
                "guardrails": [g for g in cand.get("guardrails", []) if not g.get("passed")],
                "verifier": cand.get("verifier"),
            })
    return out


def _agent_run_read(args: dict, ctx: ToolContext):
    row = ctx.engine.store.get_run(args["run_id"])
    if row is None:
        raise ToolError(f"no run {args['run_id']!r}")
    if row["pack"] != ctx.pack.name:
        raise ToolError(f"run {args['run_id']!r} belongs to another pack")
    out = {k: (str(row[k]) if k == "cost_usd" else row[k]) for k in _RUN_FIELDS}
    out["trace"] = _trace_summary(row["iterations"])
    out["ref"] = f"run:agent_runs:{row['run_id']}" if row["status"] == "succeeded" else None
    return out


def _runs_list(args: dict, ctx: ToolContext):
    rows = ctx.engine.store.list_runs(pack=ctx.pack.name, agent=args.get("agent"), status=args.get("status"),
                                      verdicted=args.get("verdicted"))
    rows = rows[-int(args.get("limit", 50)):]
    return [{k: row[k] for k in ("run_id", "agent", "role", "status", "input", "human_verdict", "verdict_source",
                                  "created_at")} for row in rows]


def _files_read(args: dict, ctx: ToolContext):
    path = ctx.access.check_file(args["path"], "read")
    if not path.is_file():
        raise ToolError(f"file not found: {args['path']}")
    text = path.read_text(encoding="utf-8")
    return {"path": args["path"], "lines": [
        {"n": i + 1, "text": line, "ref": f"file:{args['path']}:{i + 1}"}
        for i, line in enumerate(text.splitlines())]}


def _tables_read(args: dict, ctx: ToolContext):
    name = args["table"]
    spec = ctx.pack.tables.get(name)
    if spec is None:
        raise ToolError(f"no table {name!r} in pack {ctx.pack.name!r}")
    if "row_id" in args:
        row = ctx.pack.table_row(name, args["row_id"])
        rows = [] if row is None else [row]
    else:
        rows = ctx.pack.table_rows(name)[: int(args.get("limit", 1000))]
    return [{**r, "ref": f"table:{name}:{r[spec.id_field]}"} for r in rows]


def register_builtin_tools(reg: ToolRegistry) -> None:
    specs = [
        ToolSpec(id="events.query", effect="read", deterministic=True,
                 input_schema=_cfg("events.query")["input_schema"],
                 description=_cfg("events.query")["description"], fn=_events_query,
                 targets=lambda a: [Target("table", "events", "read")]),
        ToolSpec(id="events.append", effect="write", deterministic=True,
                 input_schema=_cfg("events.append")["input_schema"],
                 description=_cfg("events.append")["description"], fn=_events_append,
                 targets=lambda a: [Target("table", "events", "write")]),
        ToolSpec(id="agent_output.read", effect="read", deterministic=True,
                 input_schema=_cfg("agent_output.read")["input_schema"],
                 description=_cfg("agent_output.read")["description"], fn=_agent_output_read,
                 targets=lambda a: [Target("table", "agent_runs", "read")]),
        ToolSpec(id="agent_run.read", effect="read", deterministic=True,
                 input_schema=_cfg("agent_run.read")["input_schema"],
                 description=_cfg("agent_run.read")["description"], fn=_agent_run_read,
                 targets=lambda a: [Target("table", "agent_runs", "read")]),
        ToolSpec(id="runs.list", effect="read", deterministic=True,
                 input_schema=_cfg("runs.list")["input_schema"],
                 description=_cfg("runs.list")["description"], fn=_runs_list,
                 targets=lambda a: [Target("table", "agent_runs", "read")]),
        ToolSpec(id="files.read", effect="read", deterministic=True,
                 input_schema=_cfg("files.read")["input_schema"],
                 description=_cfg("files.read")["description"], fn=_files_read,
                 targets=lambda a: [Target("file", a["path"], "read")]),
        ToolSpec(id="tables.read", effect="read", deterministic=True,
                 input_schema=_cfg("tables.read")["input_schema"],
                 description=_cfg("tables.read")["description"], fn=_tables_read,
                 targets=lambda a: [Target("table", a["table"], "read")]),
    ]
    for s in specs:
        reg.register(s)


def register_agent_tools(reg: ToolRegistry, pack_name: str, agent_names: tuple[str, ...]) -> None:
    for child in agent_names:
        tool_id = f"agent.{pack_name}.{child}"

        def fn(args: dict, ctx: ToolContext, _child=child):
            if ctx.run_agent is None:
                raise ToolError("agent tools are only callable from inside a run")
            if ctx.depth >= 1:
                raise ToolError("agent calls are one level deep: a child may not call another agent")
            return ctx.run_agent(_child, args["input"])

        reg.register(ToolSpec(
            id=tool_id, effect="read", deterministic=False, input_schema=AGENT_TOOL_SCHEMA,
            description=f"Run the {child} agent of this pack on the given input and return its "
                        f"certified output with its run_id. Figures from it are cited as "
                        f"run:agent_runs:<run_id>.",
            fn=fn, targets=lambda a, _c=child: [Target("agent", _c, "read")]))
