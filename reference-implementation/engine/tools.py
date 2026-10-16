"""Tool registry.

A tool is a plain function with a declared id, effect, determinism flag,
argument schema and a *targets* function that names what a call will touch.
The registry validates arguments, runs the access checks on every target, and
only then executes.  Nothing reaches a tool body without passing access.py.

Pack modules declare tools with the ``@tool`` decorator; the decorator attaches
the spec to the function and packs.py collects it on import.  No global
registry, no import-time side effects.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.access import AccessPolicy, Target
from engine.errors import ToolError
from engine.schema import validation_errors

EFFECTS = frozenset({"read", "write", "external"})
TOOL_ATTR = "__harness_tool__"


@dataclass(frozen=True)
class ToolSpec:
    id: str
    effect: str
    deterministic: bool
    input_schema: dict
    description: str
    fn: Callable[[dict, "ToolContext"], Any]
    targets: Callable[[dict], list[Target]]
    adapter_slot: str | None = None

    @property
    def provider_name(self) -> str:
        """Provider-safe name: ids carry dots, provider tool names may not."""
        return self.id.replace(".", "__")

    def definition(self) -> dict:
        return {
            "name": self.provider_name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def tool(*, id: str, effect: str, deterministic: bool, input_schema: dict,
         description: str, targets: Callable[[dict], list[Target]] | None = None,
         adapter_slot: str | None = None):
    """Declare a tool.  ``fn(args: dict, ctx: ToolContext) -> JSON-able``."""
    if effect not in EFFECTS:
        raise ToolError(f"tool {id!r}: effect must be one of {sorted(EFFECTS)}")
    if effect == "external" and not adapter_slot:
        raise ToolError(f"tool {id!r}: external tools must name an adapter_slot")

    def deco(fn):
        sig = inspect.signature(fn)
        if len(sig.parameters) != 2:
            raise ToolError(f"tool {id!r}: fn must take (args, ctx)")
        spec = ToolSpec(
            id=id, effect=effect, deterministic=deterministic,
            input_schema=input_schema, description=description, fn=fn,
            targets=targets or (lambda args: []), adapter_slot=adapter_slot,
        )
        setattr(fn, TOOL_ATTR, spec)
        return fn
    return deco


@dataclass
class ToolContext:
    """Everything a tool body may touch.  Built per run by loop.py."""
    engine: Any                     # engine.store.Engine (store, ledger, clock, ids, config)
    pack: Any                       # engine.packs.Pack
    agent: Any                      # engine.manifest.Agent
    run_id: str
    access: AccessPolicy
    registry: "ToolRegistry"
    recorder: Callable[[dict], None]       # appends a tool-call record to the trace
    adapters: Any = None            # engine.adapters.base.AdapterGateway
    depth: int = 0
    parent_run_id: str | None = None
    run_agent: Callable[..., dict] | None = None   # orchestrator -> child agent
    extra: dict = field(default_factory=dict)

    def call(self, tool_id: str, args: dict, *, origin: str = "agent") -> Any:
        return self.registry.call(tool_id, args, self, origin=origin)


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._by_provider_name: dict[str, str] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate tool id {spec.id!r}")
        if spec.provider_name in self._by_provider_name:
            raise ToolError(f"tool {spec.id!r} collides on provider name {spec.provider_name!r}")
        self._specs[spec.id] = spec
        self._by_provider_name[spec.provider_name] = spec.id

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, TOOL_ATTR, None)
            if isinstance(spec, ToolSpec):
                self.register(spec)
                n += 1
        return n

    def has(self, tool_id: str) -> bool:
        return tool_id in self._specs

    def get(self, tool_id: str) -> ToolSpec:
        try:
            return self._specs[tool_id]
        except KeyError:
            raise ToolError(f"unknown tool {tool_id!r}") from None

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def id_for_provider_name(self, name: str) -> str | None:
        return self._by_provider_name.get(name)

    def definitions(self, tool_ids: list[str]) -> list[dict]:
        return [self.get(t).definition() for t in tool_ids]

    def call(self, tool_id: str, args: dict, ctx: ToolContext, *, origin: str = "agent") -> Any:
        """Validate, access-check, execute, record.  Every outcome is traced."""
        spec = self.get(tool_id)
        record: dict = {"tool": tool_id, "origin": origin, "args": args}
        errs = validation_errors(spec.input_schema, args)
        if errs:
            record["error"] = "invalid_args: " + "; ".join(errs)
            ctx.recorder(record)
            raise ToolError(f"tool {tool_id!r} invalid args: " + "; ".join(errs))
        try:
            # The manifest allowlist governs what the MODEL may call.  Reads the
            # engine makes on the manifest's behalf (grounding, memory) skip the
            # allowlist but never the target checks.
            if origin == "agent":
                ctx.access.check_tool(tool_id)
            for target in spec.targets(args):
                ctx.access.check(target)
            if spec.effect == "external":
                if ctx.adapters is None:
                    raise ToolError(f"tool {tool_id!r} is external but no adapter gateway is bound")
                ctx.adapters.require_slot(spec.adapter_slot)
            result = spec.fn(args, ctx)
        except Exception as e:  # noqa: BLE001 - every failure is traced, then re-raised
            record["error"] = f"{type(e).__name__}: {e}"
            ctx.recorder(record)
            raise
        record["result"] = result
        ctx.recorder(record)
        return result
