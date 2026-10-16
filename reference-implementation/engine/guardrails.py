"""Guardrails: deterministic output checks.  Failure = run failed, output discarded.

Built-ins (engine): schema_valid, no_invented_keys, citations_resolve,
no_fabrication, bounded_size, cited_values_match.  Packs add their own with
the ``@guardrail`` decorator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from engine.citations import CitationResolver, iter_citations
from engine.errors import CitationError, ToolError
from engine.schema import declared_keys, resolve_pointer, traceable_pointers, validation_errors

GUARDRAIL_ATTR = "__harness_guardrail__"


@dataclass
class GuardrailContext:
    agent: Any                      # engine.manifest.Agent
    output_schema: dict
    resolver: CitationResolver
    run_input: dict
    pack: Any
    max_output_bytes: int


@dataclass(frozen=True)
class GuardrailResult:
    id: str
    passed: bool
    messages: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"id": self.id, "passed": self.passed, "messages": list(self.messages)}


@dataclass(frozen=True)
class GuardrailSpec:
    id: str
    fn: Callable[[Any, GuardrailContext], list[str]]


def guardrail(*, id: str):
    """Declare a guardrail: ``fn(output, gctx) -> list[str]`` of violations (empty = pass)."""
    def deco(fn):
        setattr(fn, GUARDRAIL_ATTR, GuardrailSpec(id=id, fn=fn))
        return fn
    return deco


class GuardrailRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, GuardrailSpec] = {}

    def register(self, spec: GuardrailSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate guardrail id {spec.id!r}")
        self._specs[spec.id] = spec

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, GUARDRAIL_ATTR, None)
            if isinstance(spec, GuardrailSpec):
                self.register(spec)
                n += 1
        return n

    def has(self, gid: str) -> bool:
        return gid in self._specs

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def run(self, ids: list[str], output: Any, gctx: GuardrailContext) -> list[GuardrailResult]:
        results = []
        for gid in ids:
            spec = self._specs.get(gid)
            if spec is None:
                raise ToolError(f"unknown guardrail {gid!r}")
            try:
                messages = tuple(str(m) for m in spec.fn(output, gctx))
            except CitationError as e:
                messages = (str(e),)
            results.append(GuardrailResult(id=gid, passed=not messages, messages=messages))
        return results


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

@guardrail(id="schema_valid")
def schema_valid(output, gctx: GuardrailContext) -> list[str]:
    return validation_errors(gctx.output_schema, output)


@guardrail(id="no_invented_keys")
def no_invented_keys(output, gctx: GuardrailContext) -> list[str]:
    keys = declared_keys(gctx.output_schema)
    if keys is None or not isinstance(output, dict):
        return []
    extra = sorted(set(output) - keys)
    return [f"invented key {k!r}" for k in extra]


@guardrail(id="citations_resolve")
def citations_resolve(output, gctx: GuardrailContext) -> list[str]:
    problems = []
    for path, cite in iter_citations(output):
        try:
            resolved = gctx.resolver.resolve(cite)
            if resolved.citation.field is not None:
                resolved.value()
        except CitationError as e:
            where = "/".join(path) or "<root>"
            problems.append(f"{where}: {e}")
    return problems


def _vouches(cites, owner: dict, field_name: str) -> bool:
    """A citation covers *field_name* when it names that field, or when it names a
    source field the owner does not carry (the owner copied it under another name)."""
    if not isinstance(cites, list):
        return False
    for c in cites:
        if not isinstance(c, dict) or not isinstance(c.get("field"), str):
            continue
        if c["field"] == field_name or c["field"] not in owner:
            return True
    return False


@guardrail(id="no_fabrication")
def no_fabrication(output, gctx: GuardrailContext) -> list[str]:
    """Every traceable field is null or its owner carries a citation that vouches for it."""
    problems = []
    for pointer in traceable_pointers(gctx.output_schema):
        for path, owner, value in resolve_pointer(output, pointer):
            if value is None:
                continue
            if not isinstance(owner, dict) or not _vouches(owner.get("citations"), owner, pointer[-1]):
                problems.append(f"{'/'.join(path)}: traceable field without a citation")
    return problems


@guardrail(id="bounded_size")
def bounded_size(output, gctx: GuardrailContext) -> list[str]:
    size = len(json.dumps(output, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if size > gctx.max_output_bytes:
        return [f"output is {size} bytes; limit {gctx.max_output_bytes}"]
    return []


def _same_number(a, b) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError, TypeError):
        return False


@guardrail(id="cited_values_match")
def cited_values_match(output, gctx: GuardrailContext) -> list[str]:
    """A field that is cited must equal the value at the cited source.

    This is what lets an orchestrator state numbers without doing math: every
    cited field is a copy of a certified figure, checked here, not trusted.
    """
    problems = []
    traceable_names = {p[-1] for p in traceable_pointers(gctx.output_schema)}
    for path, cite in iter_citations(output):
        field_name = cite.get("field")
        if not isinstance(field_name, str):
            continue
        owner = output
        for part in path:
            owner = owner[int(part)] if isinstance(owner, list) else owner[part]
        if not isinstance(owner, dict):
            continue
        if field_name in owner:
            stated_key = field_name
        else:
            # the owner copied the source field under another name: it must be
            # the owner's single traceable field without a same-name citation
            same_named = {c.get("field") for c in owner.get("citations", []) if isinstance(c, dict)}
            candidates = [k for k in owner if k in traceable_names and k not in same_named]
            if len(candidates) != 1:
                continue
            stated_key = candidates[0]
        stated = owner[stated_key]
        try:
            source_value = gctx.resolver.resolve(cite).value()
        except CitationError:
            continue  # citations_resolve reports unresolvable refs
        if stated == source_value or (
                isinstance(stated, (int, float, str)) and _same_number(stated, source_value)):
            continue
        where = "/".join(path + (stated_key,))
        problems.append(f"{where}: stated {stated!r} but {cite['ref']}#{field_name} holds {source_value!r}")
    return problems


BUILTIN_IDS = ("schema_valid", "no_invented_keys", "citations_resolve",
               "no_fabrication", "bounded_size", "cited_values_match")


def builtin_registry() -> GuardrailRegistry:
    import engine.guardrails as me
    reg = GuardrailRegistry()
    reg.register_module(me)
    return reg
