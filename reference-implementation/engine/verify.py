"""Proposer / Verifier contract.

The load-bearing rule of the engine: the model proposes and explains;
deterministic code certifies.  Never the reverse.  A specialist manifest must
name a verifier; the verifier recomputes every figure it can and reports
mismatches as violations.  Its result is also an observation in the run's
RI judgement log (engine.judgement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engine.citations import CitationResolver
from engine.errors import ToolError

VERIFIER_ATTR = "__harness_verifier__"


@dataclass
class VerifyContext:
    pack: Any
    agent: Any
    run_input: dict
    resolver: CitationResolver
    read_table: Callable[[str], list[dict]]


@dataclass(frozen=True)
class VerifyResult:
    certified: bool
    violations: tuple[str, ...] = ()
    recomputed: dict = field(default_factory=dict)

    @staticmethod
    def ok(recomputed: dict | None = None) -> "VerifyResult":
        return VerifyResult(True, (), dict(recomputed or {}))

    @staticmethod
    def fail(violations: list[str], recomputed: dict | None = None) -> "VerifyResult":
        return VerifyResult(False, tuple(violations), dict(recomputed or {}))

    def as_dict(self) -> dict:
        return {"certified": self.certified, "violations": list(self.violations),
                "recomputed": self.recomputed}


@dataclass(frozen=True)
class VerifierSpec:
    id: str
    fn: Callable[[dict, VerifyContext], VerifyResult]


def verifier(*, id: str):
    """Declare a verifier: ``fn(proposal, vctx) -> VerifyResult``."""
    def deco(fn):
        setattr(fn, VERIFIER_ATTR, VerifierSpec(id=id, fn=fn))
        return fn
    return deco


class VerifierRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, VerifierSpec] = {}

    def register(self, spec: VerifierSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate verifier id {spec.id!r}")
        self._specs[spec.id] = spec

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, VERIFIER_ATTR, None)
            if isinstance(spec, VerifierSpec):
                self.register(spec)
                n += 1
        return n

    def has(self, vid: str) -> bool:
        return vid in self._specs

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def run(self, vid: str, proposal: dict, vctx: VerifyContext) -> VerifyResult:
        spec = self._specs.get(vid)
        if spec is None:
            raise ToolError(f"unknown verifier {vid!r}")
        result = spec.fn(proposal, vctx)
        if not isinstance(result, VerifyResult):
            raise ToolError(f"verifier {vid!r} returned {type(result).__name__}, not VerifyResult")
        return result
