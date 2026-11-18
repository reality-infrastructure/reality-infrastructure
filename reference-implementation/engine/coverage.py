"""Input-distribution coverage (JH-C11 wpF, G-P12).

The panel: a distillation or an eval is only as good as the spread of realistic prompts behind it.  A
pack declares ``@featurize(id=...)`` functions (``modules.featurize`` in pack.yaml), each
``fn(agent, input) -> bucket | None``; an input's bucket is the join of every featurizer that applies.
The crank compares the bucket distribution of the week's live inputs with the agent's golden set, its
held-out set and its distillation exemplars and lists every live bucket holding at least
``coverage.min_bucket_share`` of inputs that a set does not cover (``<pack>.coverage`` per cycle).
``engine.distill`` picks exemplars round-robin across buckets instead of most recent first, and a
planner may schedule seeded synthetic inputs (``synthetic: true`` on a batch item): the loop records
each as ``<pack>.synthetic_input`` and never grows one into a golden set.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from engine.errors import ToolError

FEATURIZE_ATTR = "__harness_featurize__"


@dataclass(frozen=True)
class FeaturizeSpec:
    id: str
    fn: Callable[[str, dict], str | None]


def featurize(*, id: str):
    """Declare a featurizer: ``fn(agent, input) -> bucket label, or None when it does not apply``."""
    def deco(fn):
        setattr(fn, FEATURIZE_ATTR, FeaturizeSpec(id=id, fn=fn))
        return fn
    return deco


class FeaturizeRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, FeaturizeSpec] = {}

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, FEATURIZE_ATTR, None)
            if isinstance(spec, FeaturizeSpec):
                if spec.id in self._specs:
                    raise ToolError(f"duplicate featurize id {spec.id!r}")
                self._specs[spec.id] = spec
                n += 1
        return n

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def bucket(self, agent: str, run_input: dict) -> str | None:
        parts = []
        for fid in self.ids():
            v = self._specs[fid].fn(agent, run_input)
            if v is not None:
                parts.append(f"{fid}={v}")
        return ";".join(parts) or None


def _buckets(reg: FeaturizeRegistry, agent: str, inputs: list[dict]) -> Counter:
    return Counter(b for b in (reg.bucket(agent, i) for i in inputs) if b is not None)


def exemplar_inputs(pack, agent: str) -> list[dict] | None:
    path = pack.agent_dir(agent) / "distill" / "exemplars.jsonl"
    if not path.is_file():
        return None
    lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r["input"] for r in lines[1:]]


def report(engine, pack, runs: list[dict]) -> list[dict]:
    from engine.analytics import JUDGEABLE, golden_inputs
    reg = getattr(pack, "featurize", None)
    if reg is None or not reg.ids():
        return []
    floor = float(engine.config.analytics["coverage"]["min_bucket_share"])
    by_agent: dict[str, list[dict]] = {}
    for r in runs:
        if r["role"] in JUDGEABLE:
            by_agent.setdefault(r["agent"], []).append(r["input"])
    out = []
    for agent in sorted(by_agent):
        live = _buckets(reg, agent, by_agent[agent])
        if not live:
            continue
        total = sum(live.values())
        wanted = sorted(b for b, n in live.items() if n / total >= floor)
        sets = {"golden": golden_inputs(pack, agent), "holdout": golden_inputs(pack, agent, "holdout.jsonl"),
                "exemplars": exemplar_inputs(pack, agent)}
        covered = {k: (None if v is None else _buckets(reg, agent, v)) for k, v in sets.items()}
        out.append({"agent": agent, "live": dict(sorted(live.items())),
                    "sets": {k: (None if c is None else dict(sorted(c.items()))) for k, c in covered.items()},
                    "uncovered": {k: ([] if c is None or (k == "holdout" and not c) else [b for b in wanted if b not in c])
                                  for k, c in covered.items()}})
    return out


def stratify(pack, agent: str, rows: list[dict], k: int) -> list[dict]:
    """Up to k rows round-robin across input buckets, each bucket in the order its first row appears
    (rows arrive most recent first); rows no featurizer applies to form one bucket of their own."""
    reg = getattr(pack, "featurize", None)
    if reg is None or not reg.ids():
        return rows[:k]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(reg.bucket(agent, r["input"]) or "", []).append(r)
    out: list[dict] = []
    depth = 0
    while len(out) < k and any(len(g) > depth for g in groups.values()):
        for g in groups.values():
            if len(g) > depth and len(out) < k:
                out.append(g[depth])
        depth += 1
    return out


def render(report_: dict) -> list[str]:
    L = ["", "## Input coverage", ""]
    for c in report_["coverage"]:
        L.append(f"- {c['agent']}: live buckets {c['live']}")
        for k, missing in c["uncovered"].items():
            if missing:
                L.append(f"  - {k} does not cover: {', '.join(missing)}")
    if not report_["coverage"]:
        L.append("- the pack declares no featurizer")
    return L
