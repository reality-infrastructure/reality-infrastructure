"""Drift: the pack's own measure of whether the world the golden sets came from still exists.

A pack declares drift functions the way it declares guardrails: ``@drift(id=...)`` on a
function ``fn(dctx) -> dict`` that reads the pack's tables and whatever record it keeps and
returns ``{"shifted": bool, "why": str, "measured": {...}}``.  The loop asks every one of them
before it refines or grows a golden set; when any says the distribution has moved, the
loop keeps judging and planning but adopts no edit and grows no set until the sets are
re-counted against the new world, and it records the reading as a ``<pack>.drift`` event.
The panel's point: the inner loop is optimized on a distribution; when the outer one moves,
every score on the old one is a score on a dead regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from engine.errors import ToolError

DRIFT_ATTR = "__harness_drift__"


@dataclass
class DriftContext:
    pack: Any
    engine: Any
    read_table: Callable[[str], list[dict]]


@dataclass(frozen=True)
class DriftSpec:
    id: str
    fn: Callable[[DriftContext], dict]


def drift(*, id: str):
    """Declare a drift reading: ``fn(dctx) -> {"shifted": bool, "why": str, "measured": dict}``."""
    def deco(fn):
        setattr(fn, DRIFT_ATTR, DriftSpec(id=id, fn=fn))
        return fn
    return deco


class DriftRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, DriftSpec] = {}

    def register(self, spec: DriftSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate drift id {spec.id!r}")
        self._specs[spec.id] = spec

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, DRIFT_ATTR, None)
            if isinstance(spec, DriftSpec):
                self.register(spec)
                n += 1
        return n

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def readings(self, dctx: DriftContext) -> list[dict]:
        out = []
        for did in self.ids():
            r = self._specs[did].fn(dctx)
            if not isinstance(r, dict) or not isinstance(r.get("shifted"), bool) or not isinstance(r.get("why"), str):
                raise ToolError(f"drift {did!r} must return {{shifted: bool, why: str, measured: dict}}")
            out.append({"id": did, "shifted": r["shifted"], "why": r["why"], "measured": dict(r.get("measured") or {})})
        return out
