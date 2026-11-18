"""Generic tools the engine ships.  Descriptions and schemas come from config/tools.yaml.

- events.query / events.append   the event log, through EventLog (declared types only)
- agent_output.read              a prior certified run's output
- agent_run.read / runs.list     a prior run in full (for a judge) / the run list (for a planner)
- files.read                     a granted file
- tables.read                    a pack table
- agent.<pack>.<name>            call another agent (orchestrator only, one level deep); ``inputs`` fans out
- siblings.message                  message a sibling run of the same fan-out group (JH-C11 G-B3)
- notes.write                    a working note carried to the next iteration (JH-C11 G-B4)
- scratch.write / scratch.read   findings shared by the workers of one sweep or fan-out (JH-C11 G-B4)
- reasoning.read                 a run's captured reasoning (role monitor only)

Judged roles never read the grader's runs, honeypot/trap events or judge files; only a monitor reads
reasoning and monitor events (engine.integrity).
"""

from __future__ import annotations

from engine.access import Target
from engine.config import load_config
from engine import integrity
from engine.errors import AccessDenied, ToolError
from engine.tools import ToolContext, ToolRegistry, ToolSpec

AGENT_TOOL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "input": {"type": "object"},
        "inputs": {"type": "array", "minItems": 1, "items": {"type": "object"},
                   "description": "independent parts run in parallel (fan-out); give this or input"},
        "clarifies": {"type": "string", "description": "run_id of a child that asked a question; input answers it"},
    },
}


def _cfg(tool_id: str) -> dict:
    doc = load_config().tools.get(tool_id)
    if doc is None:
        raise ToolError(f"config/tools.yaml has no entry for {tool_id!r}")
    return doc


def _events_query(args: dict, ctx: ToolContext):
    log = ctx.extra["events"]
    integrity.guard_event_type(ctx, args.get("event_type"))
    rows = log.query(entity_type=args.get("entity_type"), entity_id=args.get("entity_id"),
                     event_type=args.get("event_type"), since=args.get("since"),
                     limit=int(args.get("limit", 50)))
    rows = integrity.visible_events(ctx, rows)
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


def _events_append_check(args: dict, ctx: ToolContext) -> dict:
    """A staged events.append is validated at once, so the model sees a bad payload before certification."""
    log = ctx.extra["events"]
    log.validate(args["event_type"], args["payload"], args["entity_type"], f"agent:{ctx.agent.name}")
    if not isinstance(args["entity_id"], str) or not args["entity_id"]:
        raise ToolError("entity_id must be a non-empty string")
    if args.get("observed_at") is not None:
        from engine.runtime import parse_iso
        try:
            parse_iso(args["observed_at"])
        except ValueError as e:
            raise ToolError(f"observed_at {args['observed_at']!r} is not ISO-8601") from e
    return {"event_type": args["event_type"], "entity_id": args["entity_id"]}


def _agent_message(args: dict, ctx: ToolContext):
    bus = ctx.extra.get("bus")
    if ctx.engine.config.run_loop["messaging"] == "off":
        raise ToolError("messaging is off (config/engine.yaml loop.messaging)")
    if bus is None:
        raise ToolError("this run has no siblings: it is not part of a fan-out group")
    return bus.post(ctx, args["to"], args["text"])


def _notes_write(args: dict, ctx: ToolContext):
    cand = ctx.extra.get("candidate")
    if cand is None:
        raise ToolError("notes are written by a candidate")
    cap = ctx.engine.config.run_loop["max_notes_chars"]
    used = sum(len(n) for n in cand.notes)
    if used + len(args["text"]) > cap:
        raise ToolError(f"notes budget of {cap} characters exhausted")
    cand.notes.append(args["text"])
    return {"noted": len(cand.notes)}


def _scratch_scope(ctx: ToolContext) -> str:
    scope = ctx.extra.get("scratch_scope")
    if scope is None:
        raise ToolError("this run has no shared scratch: it is not part of a sweep or fan-out that shares one")
    return scope


def _scratch_check(args: dict, ctx: ToolContext) -> dict:
    return {"scope": _scratch_scope(ctx)}


def _scratch_write(args: dict, ctx: ToolContext):
    scope = _scratch_scope(ctx)
    row = ctx.extra["events"].append(
        entity_type="agent_run", entity_id=scope, event_type=f"{ctx.pack.name}.scratch",
        payload={"scope": scope, "run_id": ctx.run_id, "agent": ctx.agent.name, "text": args["text"]},
        source=f"agent:{ctx.agent.name}", source_ref=ctx.run_id)
    return {"event_id": row["event_id"], "ref": f"event:events:{row['event_id']}"}


def _scratch_read(args: dict, ctx: ToolContext):
    from engine.runctx import scratch_entries
    return scratch_entries(ctx, _scratch_scope(ctx))


def _agent_output_read(args: dict, ctx: ToolContext):
    row = ctx.engine.store.get_run(args["run_id"])
    if row is None:
        raise ToolError(f"no run {args['run_id']!r}")
    integrity.guard_run(ctx, row)
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
    integrity.guard_run(ctx, row)
    out = {k: (str(row[k]) if k == "cost_usd" else row[k]) for k in _RUN_FIELDS}
    if out["output"] is not None:                                # a planted alteration: the judge must catch it
        out["output"] = integrity.served_output(row, ctx.extra.get("honeypots"))
    out["trace"] = _trace_summary(row["iterations"])
    out["ref"] = f"run:agent_runs:{row['run_id']}" if row["status"] == "succeeded" else None
    return integrity.reasoning_guard(out, "agent_run.read")


def _runs_list(args: dict, ctx: ToolContext):
    rows = ctx.engine.store.list_runs(pack=ctx.pack.name, agent=args.get("agent"), status=args.get("status"),
                                      verdicted=args.get("verdicted"))
    rows = integrity.visible_runs(ctx, rows)[-int(args.get("limit", 50)):]
    return [{k: row[k] for k in ("run_id", "agent", "role", "status", "input", "human_verdict", "verdict_source",
                                  "created_at")} for row in rows]


def _files_read(args: dict, ctx: ToolContext):
    integrity.guard_file(ctx, args["path"])
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


def _reasoning_read(args: dict, ctx: ToolContext):
    if ctx.agent.role != "monitor":
        raise AccessDenied("table", "agent_runs:reasoning", "read", ctx.agent.name)
    row = ctx.engine.store.get_run(args["run_id"])
    if row is None or row["pack"] != ctx.pack.name:
        raise ToolError(f"no run {args['run_id']!r} in this pack")
    return {"run_id": row["run_id"], "agent": row["agent"], "status": row["status"], "output": row["output"],
            "texts": integrity.run_reasoning(row)}


def register_builtin_tools(reg: ToolRegistry) -> None:
    specs = [
        ToolSpec(id="events.query", effect="read", deterministic=True,
                 input_schema=_cfg("events.query")["input_schema"],
                 description=_cfg("events.query")["description"], fn=_events_query,
                 targets=lambda a: [Target("table", "events", "read")]),
        ToolSpec(id="events.append", effect="write", deterministic=True,
                 input_schema=_cfg("events.append")["input_schema"],
                 description=_cfg("events.append")["description"], fn=_events_append,
                 targets=lambda a: [Target("table", "events", "write")], prepare=_events_append_check),
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
        ToolSpec(id="siblings.message", effect="write", deterministic=False,
                 input_schema=_cfg("siblings.message")["input_schema"],
                 description=_cfg("siblings.message")["description"], fn=_agent_message, staged=False,
                 targets=lambda a: []),
        ToolSpec(id="notes.write", effect="write", deterministic=True,
                 input_schema=_cfg("notes.write")["input_schema"],
                 description=_cfg("notes.write")["description"], fn=_notes_write, staged=False,
                 targets=lambda a: []),
        ToolSpec(id="scratch.write", effect="write", deterministic=True,
                 input_schema=_cfg("scratch.write")["input_schema"],
                 description=_cfg("scratch.write")["description"], fn=_scratch_write, prepare=_scratch_check,
                 targets=lambda a: []),
        ToolSpec(id="scratch.read", effect="read", deterministic=True,
                 input_schema=_cfg("scratch.read")["input_schema"],
                 description=_cfg("scratch.read")["description"], fn=_scratch_read,
                 targets=lambda a: [Target("table", "events", "read")]),
        ToolSpec(id="reasoning.read", effect="read", deterministic=True,
                 input_schema=_cfg("reasoning.read")["input_schema"],
                 description=_cfg("reasoning.read")["description"], fn=_reasoning_read,
                 targets=lambda a: [Target("table", "agent_runs", "read")]),
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
            if ("input" in args) == ("inputs" in args):
                raise ToolError("give exactly one of input (one child) or inputs (a fan-out)")
            if "inputs" in args:
                if "clarifies" in args:
                    raise ToolError("clarifies answers one child; it does not combine with inputs")
                return ctx.run_agent(_child, None, inputs=args["inputs"])
            return ctx.run_agent(_child, args["input"], clarifies=args.get("clarifies"))

        reg.register(ToolSpec(
            id=tool_id, effect="read", deterministic=False, input_schema=AGENT_TOOL_SCHEMA,
            description=f"Run the {child} agent of this pack on the given input and return its "
                        f"certified output with its run_id. Figures from it are cited as "
                        f"run:agent_runs:<run_id>.",
            fn=fn, targets=lambda a, _c=child: [Target("agent", _c, "read")]))
