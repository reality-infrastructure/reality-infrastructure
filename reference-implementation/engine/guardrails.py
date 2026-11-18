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
    engine: Any = None              # engine.store.Engine; the loop-role guardrails read runs through it
    honeypots: dict | None = None   # run_id -> planted alteration(s): what a judge was actually served
    tool_calls: list | None = None  # the candidate's tool calls, set before its guardrails run


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


# ---------------------------------------------------------------------------
# The closed loop's roles (engine.autoloop): the model proposes a verdict, a batch
# or an edit; these checks keep each proposal inside what code can confirm.  No
# verdict may contradict a deterministic check, no batch may name an agent or
# input the pack cannot run, no edit may touch anything but onboarding text.
# ---------------------------------------------------------------------------

LOOP_VERDICTS = ("followed", "overridden", "wrong", "n/a")
JUDGEABLE_ROLES = ("worker", "specialist", "orchestrator")
EDITABLE_FILES = ("skills.md", "workflow.md")
EDITABLE_DIRS = ("prompts",)


@guardrail(id="verdict_grounded")
def verdict_grounded(output, gctx: GuardrailContext) -> list[str]:
    """A judge's verdict is about the run it was asked to judge and never contradicts code:
    a run that failed its guardrails or verifier may only be 'wrong' or 'n/a'; an override
    or 'wrong' on a succeeded run must name a field of that run's output; a judge judges
    workers, specialists and orchestrators only, and never itself."""
    if not isinstance(output, dict):
        return ["output must be an object"]
    want = gctx.run_input.get("run_id")
    if output.get("run_id") != want:
        return [f"run_id: judged {output.get('run_id')!r}, asked to judge {want!r}"]
    if gctx.engine is None:
        return []
    row = gctx.engine.store.get_run(str(want))
    if row is None:
        return [f"no run {want!r} to judge"]
    problems = []
    if row["role"] not in JUDGEABLE_ROLES:
        problems.append(f"a judge adjudicates {'/'.join(JUDGEABLE_ROLES)} runs; {want} is a {row['role']} run")
    verdict, reason = output.get("verdict"), output.get("reason")
    if verdict not in LOOP_VERDICTS:
        problems.append(f"verdict must be one of {LOOP_VERDICTS}, got {verdict!r}")
    if not isinstance(reason, str) or not reason.strip():
        problems.append("reason must be a non-empty string")
    if row["status"] != "succeeded" and verdict in ("followed", "overridden"):
        problems.append(f"run {want} failed its checks ({row['status']}); a verdict of {verdict!r} contradicts code, use 'wrong' or 'n/a'")
    if row["status"] == "succeeded" and verdict in ("overridden", "wrong") and isinstance(reason, str) and isinstance(row["output"], dict):
        keys = [k for k in row["output"] if k != "citations"]
        if not any(k in reason for k in keys):
            problems.append(f"an override on a succeeded run must name the output field it disputes (one of {keys})")
        elif gctx.engine.config.integrity["judge"]["require_correction"]:
            from engine.integrity import correction_problems, served_output
            problems += correction_problems(served_output(row, gctx.honeypots), output.get("correction"), reason)
    return problems


@guardrail(id="batch_resolves")
def batch_resolves(output, gctx: GuardrailContext) -> list[str]:
    """A planner's batch names only agents the pack can run on object inputs, without
    duplicates, within the cap the loop was given."""
    if not isinstance(output, dict) or not isinstance(output.get("batch"), list):
        return ["batch must be a list"]
    problems = []
    cap = gctx.run_input.get("max_runs")
    if isinstance(cap, int) and len(output["batch"]) > cap:
        problems.append(f"batch has {len(output['batch'])} items; the cap is {cap}")
    seen = set()
    for i, item in enumerate(output["batch"]):
        if not isinstance(item, dict) or not isinstance(item.get("agent"), str) or not isinstance(item.get("input"), dict):
            problems.append(f"batch/{i}: must be {{agent, input}} with an object input")
            continue
        name = item["agent"]
        if gctx.pack is not None and name not in gctx.pack.agent_names:
            problems.append(f"batch/{i}: no agent {name!r} in this pack")
            continue
        if name in (gctx.run_input.get("killed") or {}):
            problems.append(f"batch/{i}: {name} is halted by the kill rule ({(gctx.run_input.get('killed') or {}).get(name)}); it is not scheduled until it recovers")
            continue
        if gctx.pack is not None:
            from engine.config import load_yaml
            role = load_yaml(gctx.pack.agent_dir(name) / "manifest.yaml").get("role")
            if role not in JUDGEABLE_ROLES:
                problems.append(f"batch/{i}: {name} is a {role}; a planner schedules {'/'.join(JUDGEABLE_ROLES)} runs only")
            band = (gctx.run_input.get("curriculum") or {}).get(name)
            if band:
                from engine.curriculum import band_problem
                outside = band_problem(gctx.pack, name, item["input"], band)
                if outside:
                    problems.append(f"batch/{i}: {outside}")
        key = (name, json.dumps(item["input"], sort_keys=True))
        if key in seen:
            problems.append(f"batch/{i}: duplicate of an earlier item")
        seen.add(key)
    if gctx.engine is not None and gctx.pack is not None:
        from engine.integrity import batch_concentration
        problems += batch_concentration(gctx.engine, gctx.pack, output["batch"])
    return problems + _batch_long_horizon(output, gctx) + _batch_steering(output["batch"], gctx.run_input)


@guardrail(id="no_forbidden_reads")
def no_forbidden_reads(output, gctx: GuardrailContext) -> list[str]:
    """A candidate never reads an answer key or an expected-output file (config integrity.forbidden_reads),
    even where its access reaches one: passing by reading the answer is a cheat, not a solve."""
    from engine.integrity import forbidden_reads
    return forbidden_reads(gctx)


def _batch_steering(batch: list, run_input: dict) -> list[str]:
    """The crank's steering (engine.constraint, engine.analytics): while the binding constraint is an agent's
    lost runs, ``constraint_share`` of the batch goes to that agent; while the window repeats itself, at least
    ``min_novel_share`` of the batch is unlike any golden case of its agent."""
    items = [b for b in batch if isinstance(b, dict) and isinstance(b.get("input"), dict)]
    if not items:
        return []
    problems = []
    share = run_input.get("constraint_share")
    agent = (run_input.get("constraint") or {}).get("agent")
    if isinstance(share, (int, float)) and agent:
        got = sum(1 for b in items if b.get("agent") == agent) / len(items)
        if got < share:
            problems.append(f"batch: {got:.0%} of items go to {agent}, the binding constraint "
                            f"({run_input['constraint'].get('top')}); at least {share:.0%} must")
    novelty = run_input.get("novelty") or {}
    floor = novelty.get("min_novel_share")
    if isinstance(floor, (int, float)):
        known = {a: {json.dumps(i, sort_keys=True) for i in ins} for a, ins in (novelty.get("golden_inputs") or {}).items()}
        novel = sum(1 for b in items if json.dumps(b["input"], sort_keys=True) not in known.get(b.get("agent"), set()))
        if novel / len(items) < floor:
            problems.append(f"batch: {novel} of {len(items)} items are unlike any golden case while the window repeats "
                            f"itself ({', '.join(novelty.get('repeating') or [])}); at least {floor:.0%} must be novel")
    return problems


@guardrail(id="edit_applies")
def edit_applies(output, gctx: GuardrailContext) -> list[str]:
    """A refiner's edit is one exact replacement in one onboarding or prompt text file the
    loop handed it, on a rung the loop allows, for the agent the loop named.  A refiner may
    decline (``file`` null, ``old`` and ``new`` empty) when the evidence warrants no edit; the
    ``why`` then carries the reason and the loop records a declined refinement."""
    if not isinstance(output, dict):
        return ["output must be an object"]
    problems = []
    files = gctx.run_input.get("files") or {}
    rungs = tuple(gctx.run_input.get("rungs") or (1, 2))
    if output.get("agent") != gctx.run_input.get("agent"):
        problems.append(f"agent: edit names {output.get('agent')!r}, the loop asked about {gctx.run_input.get('agent')!r}")
    if output.get("rung") not in rungs:
        problems.append(f"rung must be one of {list(rungs)}, got {output.get('rung')!r}")
    if output.get("file") is None:
        if output.get("old") or output.get("new"):
            problems.append("a declined edit (file null) carries no old or new text")
        return problems
    path = output.get("file")
    if not isinstance(path, str) or path not in files:
        return problems + [f"file must be one of the files handed to the refiner {sorted(files)}, got {path!r}"]
    base = path.replace("\\", "/")
    if not (base in EDITABLE_FILES or (base.split("/")[0] in EDITABLE_DIRS and base.endswith(".md"))):
        problems.append(f"file {path!r} is not editable at rungs 1-2 (skills.md, workflow.md, prompts/*.md only)")
    old, new = output.get("old"), output.get("new")
    if not isinstance(old, str) or not old:
        problems.append("old must be a non-empty string copied from the file")
    elif files[path].count(old) != 1:
        problems.append(f"old must occur exactly once in {path}; it occurs {files[path].count(old)} times")
    if not isinstance(new, str) or new == old:
        problems.append("new must differ from old")
    from engine.forecast import refiner_problems
    return problems + refiner_problems(output, gctx.run_input, bool(gctx.run_input.get("forecast_required")))


BUILTIN_IDS = ("schema_valid", "no_invented_keys", "citations_resolve",
               "no_fabrication", "bounded_size", "cited_values_match",
               "verdict_grounded", "batch_resolves", "edit_applies", "case_certified",
               "no_forbidden_reads")


def builtin_registry() -> GuardrailRegistry:
    import engine.guardrails as me
    reg = GuardrailRegistry()
    reg.register_module(me)
    return reg


# -- JH-C11 wpI: the long-horizon record ---------------------------------------------------------

def _batch_long_horizon(output: dict, gctx: GuardrailContext) -> list[str]:
    """What the loop told the planner it must respect: the value ranking (engine.value), each agent's
    reputation cap (engine.reputation) and, when required, a p_pass per item (engine.forecast)."""
    from engine.forecast import planner_problems
    from engine.reputation import cap_problems
    from engine.value import skip_problems
    ri = gctx.run_input
    return (skip_problems(output, ri, int(ri.get("max_skip_without_reason") or 0)) + cap_problems(output, ri)
            + planner_problems(output, bool(ri.get("forecast_required"))))


@guardrail(id="case_certified")
def case_certified(output, gctx: GuardrailContext) -> list[str]:
    """A curator's proposal: at most ``max_cases`` cases for the agent the loop named, each with an id, an
    object input no golden or held-out case already has, an expected output carrying every compared field,
    and a reason.  Whether each expected output is correct and the case discriminating is certified by code
    afterwards, case by case (engine.curate)."""
    if not isinstance(output, dict) or not isinstance(output.get("cases"), list):
        return ["cases must be a list"]
    ri = gctx.run_input
    problems = []
    if output.get("agent") != ri.get("agent"):
        problems.append(f"agent: proposal names {output.get('agent')!r}, the loop asked for {ri.get('agent')!r}")
    cap = ri.get("max_cases")
    if isinstance(cap, int) and len(output["cases"]) > cap:
        problems.append(f"{len(output['cases'])} cases proposed; the cap is {cap}")
    known = set(ri.get("known_inputs") or [])
    roots = sorted({str(f).split(".")[0] for f in ri.get("compare") or []})
    ids, inputs = set(), set()
    for i, c in enumerate(output["cases"]):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"] or not isinstance(c.get("input"), dict) \
                or not isinstance(c.get("expected"), dict) or not isinstance(c.get("why"), str) or not c["why"].strip():
            problems.append(f"cases/{i}: must be {{id, input: object, expected: object, why}}")
            continue
        missing = [r for r in roots if r not in c["expected"]]
        if missing:
            problems.append(f"cases/{i}: expected lacks compared fields {missing}")
        key = json.dumps(c["input"], sort_keys=True)
        if key in known:
            problems.append(f"cases/{i}: input {key} is already a golden or held-out case")
        if key in inputs or c["id"] in ids:
            problems.append(f"cases/{i}: duplicate of an earlier case")
        inputs.add(key)
        ids.add(c["id"])
    return problems


# -- JH-C11 wpC: point-in-time backtests ----------------------------------------------------------------

@guardrail(id="no_future_citation")
def no_future_citation(output, gctx: GuardrailContext) -> list[str]:
    """A run held to a case's ``as_of`` (engine.experiment) may not cite a record observed after it.  The
    engine adds this guardrail to every run of a backtest case; outside one it passes."""
    from engine.experiment import future_citations
    return future_citations(output, gctx)
