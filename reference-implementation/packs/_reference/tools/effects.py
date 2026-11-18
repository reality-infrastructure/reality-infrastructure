"""Fixture tools that reach outside the run: an outbound command through the adapter gateway, and two tools
that run in the process sandbox (engine/sandbox.py).  They exist so the engine's ruin guard, effect staging and
sandbox are proven on the reference pack; none of this is behaviour for a real domain."""

from __future__ import annotations

import os
import socket

from engine.adapters.base import Command
from engine.tools import tool


@tool(
    id="_reference.records.notify",
    effect="external",
    adapter_slot="records_feed",
    deterministic=False,
    description="Send an outbound command about a record through the records_feed slot.",
    input_schema={"type": "object", "additionalProperties": False, "required": ["record_id", "action"],
                  "properties": {"record_id": {"type": "string"}, "action": {"type": "string"},
                                 "amount": {"type": "number", "minimum": 0}}},
)
def notify(args: dict, ctx) -> dict:
    params = {"amount": args["amount"]} if "amount" in args else {}
    result = ctx.adapters.command("records_feed", Command(entity_id=args["record_id"], action=args["action"],
                                                          params=params, flags={"disclosure": True}),
                                  source_ref=ctx.run_id, agent=ctx.agent.name)
    return result.as_dict()


@tool(
    id="_reference.sandbox.connect",
    effect="read",
    deterministic=False,
    sandbox=True,
    description="Open a TCP connection to host:port from the sandbox and report whether it connected.",
    input_schema={"type": "object", "additionalProperties": False, "required": ["host", "port"],
                  "properties": {"host": {"type": "string"}, "port": {"type": "integer"}}},
)
def connect(args: dict, ctx) -> dict:
    # deliberately declares no network target: the in-process access check never sees the host
    with socket.create_connection((args["host"], args["port"]), timeout=5):
        return {"connected": True, "host": args["host"]}


@tool(
    id="_reference.sandbox.scribble",
    effect="read",
    deterministic=True,
    sandbox=True,
    description="Write size bytes to a file in the run's workspace and report the workspace contents.",
    input_schema={"type": "object", "additionalProperties": False, "required": ["name", "size"],
                  "properties": {"name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}}},
)
def scribble(args: dict, ctx) -> dict:
    path = os.path.join(ctx.workspace, args["name"])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("x" * args["size"])
    return {"files": sorted(os.listdir(ctx.workspace)), "pid": os.getpid(), "env": sorted(os.environ)}
