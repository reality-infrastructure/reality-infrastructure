"""Curriculum: easy first, climb on evidence (JH-C11 wpA; Musk G-M16, the panel G-P10, Brown G-B5).

Every input has a tier, an ordinal difficulty (rung) >= 1: a golden or held-out case declares its
``tier``; any other input is tiered by the pack's ``@tier(agent=...)`` function (``modules.tiers`` in
pack.yaml); an input neither knows is tier 1.  An agent version starts at tier 1 and is promoted one
tier at a time when its pass rate over its latest runs at its current tier reaches
``curriculum.promote_at`` (``<pack>.tier_promoted``).  The sweep never hands an agent an input above
its promoted tier, and the planner's batch stays in the band from the frontier tier minus
``plan_frontier_window`` up to the promoted tier (``batch_resolves`` refuses the rest).

The frontier is read from the record: the agent's runs on golden and held-out inputs, scored against
their expected values (``engine.goldenview``).  Each autoloop cycle records ``<pack>.curriculum`` for a
tiered agent and ``<pack>.saturation`` when its golden set no longer challenges it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine import stats
from engine.config import load_yaml
from engine.errors import ToolError
from engine.eval import case_passes, load_golden
from engine.events import EventLog
from engine.rigor import EVAL_FILES, input_key, record_saturation, saturation

TIER_ATTR = "__harness_tier__"


@dataclass(frozen=True)
class TierSpec:
    agent: str
    fn: Callable[[dict], int]


def tier(*, agent: str):
    """Declare how a pack tiers an agent's inputs: ``fn(run_input) -> int >= 1``."""
    def deco(fn):
        setattr(fn, TIER_ATTR, TierSpec(agent=agent, fn=fn))
        return fn
    return deco


class TierRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, TierSpec] = {}

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, TIER_ATTR, None)
            if isinstance(spec, TierSpec):
                if spec.agent in self._specs:
                    raise ToolError(f"duplicate tier function for agent {spec.agent!r}")
                self._specs[spec.agent] = spec
                n += 1
        return n

    def agents(self) -> list[str]:
        return sorted(self._specs)

    def tier_of(self, agent: str, run_input: dict) -> int | None:
        spec = self._specs.get(agent)
        if spec is None:
            return None
        t = spec.fn(run_input)
        if isinstance(t, bool) or not isinstance(t, int) or t < 1:
            raise ToolError(f"tier function for {agent!r} returned {t!r}, not an integer >= 1")
        return t


def case_tiers(pack, agent: str) -> dict[str, int]:
    """{canonical input: tier} over the agent's golden and held-out cases that declare one."""
    out = {}
    for name in EVAL_FILES:
        path = pack.agent_dir(agent) / "eval" / name
        if path.is_file():
            for c in load_golden(path, pack_is_fixture=pack.fixture).cases:
                if c.tier is not None:
                    out[input_key(c.input)] = c.tier
    return out


def input_tier(pack, agent: str, run_input: dict, known: dict[str, int] | None = None) -> int:
    known = case_tiers(pack, agent) if known is None else known
    t = known.get(input_key(run_input))
    if t is not None:
        return t
    registry = getattr(pack, "tiers", None)
    t = registry.tier_of(agent, run_input) if registry is not None else None
    return 1 if t is None else t


def is_tiered(pack, agent: str) -> bool:
    registry = getattr(pack, "tiers", None)
    return bool(case_tiers(pack, agent)) or (registry is not None and agent in registry.agents())


def _version(pack, agent: str) -> str:
    return str(load_yaml(pack.agent_dir(agent) / "manifest.yaml").get("version"))


def promoted_tier(engine, pack, agent: str) -> int:
    """The tier the agent's current version has been promoted to (1 until a ``<pack>.tier_promoted`` says more)."""
    version = _version(pack, agent)
    best = 1
    for e in engine.store.query_events(event_type=f"{pack.name}.tier_promoted", limit=100000, ascending=True):
        p = e["payload"]
        if p["agent"] == agent and p["version"] == version:
            best = max(best, int(p["to_tier"]))
    return best


def band(engine, pack, agent: str) -> dict:
    """The tiers an agent may be handed now: up to its promoted tier, and (for the planner) no lower than the
    frontier minus the configured window."""
    from engine.goldenview import golden_view
    cfg = engine.config.curriculum
    hi = promoted_tier(engine, pack, agent)
    view = golden_view(engine, pack, agent, engine.store.list_runs(pack=pack.name, agent=agent))
    ladder = (view or {}).get("curriculum") or {}
    frontier = ladder.get("frontier_tier")
    lo = 1 if frontier is None else max(1, min(hi, frontier) - cfg["plan_frontier_window"])
    return {"promoted_tier": hi, "frontier_tier": frontier, "mastered_tier": ladder.get("mastered_tier"),
            "gaps": list(ladder.get("gaps") or []), "lo": lo, "hi": hi}


def band_problem(pack, agent: str, run_input: dict, agent_band: dict) -> str | None:
    t = input_tier(pack, agent, run_input)
    if t > agent_band["hi"]:
        return f"{agent} input is tier {t}, above its promoted tier {agent_band['hi']} (easy first: it climbs on evidence)"
    if t < agent_band["lo"]:
        return f"{agent} input is tier {t}, below the band {agent_band['lo']}-{agent_band['hi']} around its frontier"
    return None


def gate_inputs(engine, pack, agent: str, inputs: list[dict]) -> tuple[list[dict], list[dict]]:
    """(inputs at or below the agent's promoted tier, inputs held back)."""
    if not is_tiered(pack, agent):
        return list(inputs), []
    hi = promoted_tier(engine, pack, agent)
    known = case_tiers(pack, agent)
    allowed, held = [], []
    for inp in inputs:
        (allowed if input_tier(pack, agent, inp, known) <= hi else held).append(inp)
    return allowed, held


def promote(engine, pack, agent: str) -> dict | None:
    """Promote the agent's version one tier when its latest runs at its current tier pass often enough."""
    if not is_tiered(pack, agent):
        return None
    cfg, conf = engine.config.curriculum, engine.config.stats["confidence"]
    current = promoted_tier(engine, pack, agent)
    known = case_tiers(pack, agent)
    rows = [r for r in engine.store.list_runs(pack=pack.name, agent=agent)
            if r["parent_run_id"] is None and input_tier(pack, agent, r["input"], known) == current][-cfg["window_runs"]:]
    if len(rows) < cfg["min_runs"]:
        return None
    ok = sum(1 for r in rows if r["status"] == "succeeded")
    if ok / len(rows) < cfg["promote_at"]:
        return None
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.tier_promoted",
        payload={"agent": agent, "version": _version(pack, agent), "from_tier": current, "to_tier": current + 1,
                 "pass_rate": stats.rate(ok, len(rows), conf)}, source="pipeline:curriculum")


def audit(engine, pack, agents: list[str]) -> dict:
    """Once per autoloop cycle, for each agent with a golden set: promote if earned, record the curriculum of a
    tiered agent and the saturation of a set that no longer challenges it.  Returns {agent: {band, saturation}}."""
    cfg = engine.config.eval_rigor
    log = EventLog(engine, pack)
    out = {}
    for agent in agents:
        path = pack.agent_dir(agent) / "eval" / "golden.jsonl"
        if not path.is_file():
            continue
        golden = load_golden(path, pack_is_fixture=pack.fixture)
        promoted = promote(engine, pack, agent)
        b = band(engine, pack, agent)
        if is_tiered(pack, agent):
            log.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.curriculum",
                       payload={"agent": agent, "mastered_tier": b["mastered_tier"], "frontier_tier": b["frontier_tier"],
                                "gaps": b["gaps"], "promoted_tier": b["promoted_tier"]}, source="pipeline:curriculum")
        sat = saturation(engine, pack, agent, golden.cases, golden.compare, case_passes,
                         k=cfg["saturation_k"], max_share=cfg["max_saturated_share"])
        if sat["flagged"]:
            record_saturation(engine, pack, agent, sat)
        out[agent] = {"band": b, "promoted": None if promoted is None else promoted["payload"]["to_tier"], "saturation": sat}
    return out
