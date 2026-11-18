"""Value-ranked planning: what the loop works on is a ranked, recorded choice, not the planner's unaudited taste.

A pack declares candidate inputs and their value the way it declares drift: ``@value(id=..., agent=...)``
on ``fn(vctx) -> [{"input": {...}, "value": number, "why": str}]`` (the value of a certified output,
e.g. the size of the decision it feeds).  The engine drops inputs the agent already has a succeeded
run on and agents the kill rule halts, divides value by the agent's expected cost (mean cost of its
recent runs), ranks, and hands the ranked list to the planner.  ``batch_resolves`` then refuses a
batch that passes over a higher-ranked input without naming a reason in ``skips``; every plan is
recorded as a ``<pack>.plan`` event with the ranking, the batch and each skip reason.  A pack with
no ``@value`` hook plans as before, recorded with basis ``none``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from engine.errors import ToolError

VALUE_ATTR = "__harness_value__"
COST_WINDOW_RUNS = 20


@dataclass
class ValueContext:
    pack: Any
    engine: Any
    read_table: Callable[[str], list[dict]]


@dataclass(frozen=True)
class ValueSpec:
    id: str
    agent: str
    fn: Callable[[ValueContext], list[dict]]


def value(*, id: str, agent: str):
    """Declare candidate inputs for ``agent`` with their value: ``fn(vctx) -> [{"input", "value", "why"}]``."""
    def deco(fn):
        setattr(fn, VALUE_ATTR, ValueSpec(id=id, agent=agent, fn=fn))
        return fn
    return deco


class ValueRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ValueSpec] = {}

    def register(self, spec: ValueSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate value id {spec.id!r}")
        self._specs[spec.id] = spec

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, VALUE_ATTR, None)
            if isinstance(spec, ValueSpec):
                self.register(spec)
                n += 1
        return n

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def candidates(self, vctx: ValueContext) -> list[dict]:
        out = []
        for vid in self.ids():
            spec = self._specs[vid]
            for c in spec.fn(vctx):
                if not isinstance(c, dict) or not isinstance(c.get("input"), dict) or isinstance(c.get("value"), bool) \
                        or not isinstance(c.get("value"), (int, float)) or not isinstance(c.get("why"), str):
                    raise ToolError(f"value {vid!r} must return [{{input: dict, value: number, why: str}}]")
                out.append({"agent": spec.agent, "input": c["input"], "value": float(c["value"]), "why": c["why"], "hook": vid})
        return out


def _key(agent: str, run_input: dict) -> str:
    return f"{agent}:{json.dumps(run_input, sort_keys=True)}"


def _expected_cost(engine, pack, agent: str) -> float:
    rows = engine.store.list_runs(pack=pack.name, agent=agent, limit=COST_WINDOW_RUNS, newest_first=True)
    costs = [Decimal(str(r["cost_usd"])) for r in rows]
    return float(sum(costs) / len(costs)) if costs and sum(costs) > 0 else 0.0


def ranked(engine, pack, *, killed: dict[str, str] | None = None) -> dict:
    """``{"basis": "value"|"none", "entries": [{rank, agent, input, value, expected_cost, score, why}]}``."""
    if pack.values is None or not pack.values.ids():
        return {"basis": "none", "entries": []}
    cands = pack.values.candidates(ValueContext(pack=pack, engine=engine, read_table=pack.table_rows))
    unknown = sorted({c["agent"] for c in cands} - set(pack.agent_names))
    if unknown:
        raise ToolError(f"value hooks name agents the pack does not have: {unknown}")
    done: dict[str, set[str]] = {}
    costs: dict[str, float] = {}
    entries, seen = [], set()
    for c in cands:
        if c["agent"] in (killed or {}):
            continue
        if c["agent"] not in done:
            done[c["agent"]] = {_key(c["agent"], r["input"]) for r in engine.store.list_runs(pack=pack.name, agent=c["agent"], status="succeeded")}
            costs[c["agent"]] = _expected_cost(engine, pack, c["agent"])
        k = _key(c["agent"], c["input"])
        if k in done[c["agent"]] or k in seen:
            continue
        seen.add(k)
        cost = costs[c["agent"]]
        entries.append({"agent": c["agent"], "input": c["input"], "value": c["value"], "expected_cost": round(cost, 8),
                        "score": c["value"] / cost if cost > 0 else c["value"], "why": c["why"]})
    entries.sort(key=lambda e: (-e["score"], e["agent"], json.dumps(e["input"], sort_keys=True)))
    cap = engine.config.autoloop_long_horizon["plan"]["max_ranked"]
    return {"basis": "value", "entries": [{"rank": i + 1, **e} for i, e in enumerate(entries[:cap])]}


def skip_problems(output: dict, run_input: dict, max_skip_without_reason: int) -> list[str]:
    """A batch of n items may pass over a ranked input among the top n only by naming it in ``skips`` with a reason."""
    ranking = run_input.get("ranked") or []
    batch = output.get("batch") if isinstance(output.get("batch"), list) else []
    if not ranking or not batch:
        return []
    chosen = {_key(i.get("agent", ""), i.get("input") or {}) for i in batch if isinstance(i, dict)}
    reasons = {_key(s.get("agent", ""), s.get("input") or {}): s.get("reason") for s in (output.get("skips") or []) if isinstance(s, dict)}
    unexplained = [e for e in ranking[:len(batch)] if _key(e["agent"], e["input"]) not in chosen
                   and not (isinstance(reasons.get(_key(e["agent"], e["input"])), str) and reasons[_key(e["agent"], e["input"])].strip())]
    if len(unexplained) > max_skip_without_reason:
        return [f"skips: the batch passes over ranked input #{e['rank']} {e['agent']} {json.dumps(e['input'], sort_keys=True)} "
                f"(value {e['value']}) without a reason; run it or name it in skips with a reason" for e in unexplained]
    return []


def plan_record(planner_run_id: str | None, ranking: dict, batch: list[dict], skips: list[dict], *, planner_suspended: bool) -> dict:
    ranks = {_key(e["agent"], e["input"]): e["rank"] for e in ranking["entries"]}
    return {"planner_run_id": planner_run_id, "basis": ranking["basis"],
            "ranked": [{k: e[k] for k in ("rank", "agent", "input", "value", "expected_cost", "score")} for e in ranking["entries"]],
            "batch": [{"agent": i["agent"], "input": i["input"], "rank": ranks.get(_key(i["agent"], i["input"]))} for i in batch],
            "skips": [{"agent": s.get("agent"), "input": s.get("input"), "reason": s.get("reason")} for s in skips],
            "planner_suspended": planner_suspended}
