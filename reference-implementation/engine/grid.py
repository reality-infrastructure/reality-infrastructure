"""Factorial ablation matrix with residual (JH-C11 wpC, the panel G-P23).

    python -m engine.grid <pack>/<agent> [--date YYYY-MM-DD] [--db DSN]

The panel: "we trained all the recipes ... pairwise with all the data sets ... You do the whole grid ... the data
seems to explain something like a 12.0x ... the architecture improvements explain something like a 3.7x", and
then "so where's that missing 100x coming from?"  A grid crosses every level of every declared factor, scores
each cell on the golden set (and the held-out set, ``eval.grid.holdout``), and reports each factor's effect and
the residual: the full change (every factor at its last level against every factor at its first) minus the sum of
the factors' one-at-a-time effects.  A nonzero residual is the interaction no single factor explains.

Factors are declared per agent in ``eval/grid.yaml`` (first level = where the change starts, last = where it ends;
one level holds a factor constant)::

    factors:
      model:     [provider/a, provider/b]                 # model strings
      prompt:    [prompts/system.md, prompts/system-b.md] # system prompt files, relative to the agent directory
      grounding: [all, none, [table:sheets]]              # all | none | the kind:ref sources kept
      skills:    [skills.md, skills-b.md]                 # onboarding file versions
      workflow:  [workflow.md, workflow-b.md]

``eval.grid.factors`` lists the factor kinds the engine crosses; ``eval.grid.max_cells`` refuses a grid larger
than it.  Every cell is an agent variant (engine.experiment).  The grid is written to ``eval/grid-<date>.{md,json}``
next to the parity matrix; it records no event.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import sys
from decimal import Decimal
from pathlib import Path

from engine.config import load_yaml
from engine.errors import EngineError, EvalError
from engine.eval import run_eval
from engine.experiment import Experiment
from engine.loop import Runner
from engine.manifest import _front_matter
from engine.packs import load_pack, parse_agent_ref
from engine.providers import parse_model_string
from engine.store import Engine

Q4 = Decimal("0.0001")


def _label(level) -> str:
    return level if isinstance(level, str) else "+".join(level) if level else "none"


def load_factors(engine: Engine, agent) -> dict[str, list]:
    path = agent.dir / "eval" / "grid.yaml"
    if not path.is_file():
        raise EvalError(f"{agent.ref}: no eval/grid.yaml declaring the grid's factors")
    doc = load_yaml(path).get("factors")
    allowed = engine.config.experiments["grid"]["factors"]
    if not isinstance(doc, dict) or not doc:
        raise EvalError(f"{path}: factors must map factor kinds to lists of levels")
    out = {}
    for kind in allowed:                                   # config order: the cell order is stable
        if kind not in doc:
            continue
        levels = doc[kind]
        if not isinstance(levels, list) or not levels:
            raise EvalError(f"{path}: factor {kind!r} needs a list of at least one level")
        for lv in levels:
            if kind == "model":
                parse_model_string(str(lv))
            elif kind == "grounding":
                if not (lv in ("all", "none") or (isinstance(lv, list) and all(isinstance(x, str) for x in lv))):
                    raise EvalError(f"{path}: grounding level {lv!r} must be all, none or a list of kind:ref")
            elif not (isinstance(lv, str) and (agent.dir / lv).is_file()):
                raise EvalError(f"{path}: {kind} level {lv!r} is not a file in {agent.dir}")
        out[kind] = levels
    unknown = sorted(set(doc) - set(allowed))
    if unknown:
        raise EvalError(f"{path}: factor kind(s) {unknown} are not in eval.grid.factors {list(allowed)}")
    return out


def _transform(agent_dir: Path, cell: dict):
    def apply(a):
        changes = {}
        if "prompt" in cell:
            changes["model"] = dataclasses.replace(a.model, system_prompt=(agent_dir / cell["prompt"]).read_text(encoding="utf-8"))
        if "grounding" in cell:
            lv = cell["grounding"]
            changes["grounding"] = a.grounding if lv == "all" else () if lv == "none" else \
                tuple(s for s in a.grounding if f"{s['kind']}:{s['ref']}" in lv)
        if "skills" in cell:
            changes["skills"] = (agent_dir / cell["skills"]).read_text(encoding="utf-8")
        if "workflow" in cell:
            path = agent_dir / cell["workflow"]
            changes["workflow"] = _front_matter(path.read_text(encoding="utf-8"), path)[1]
        return dataclasses.replace(a, **changes)
    return apply


def _mean(xs: list[Decimal]) -> Decimal:
    return sum(xs, Decimal(0)) / len(xs)


def effects(factors: dict[str, list], cells: list[dict], key: str) -> dict:
    """One-at-a-time and grid-averaged effects per factor level, the full change and the residual."""
    def score(levels: dict) -> Decimal | None:
        for c in cells:
            if all(_label(c["levels"][f]) == _label(levels[f]) for f in factors):
                return None if c[key] is None else Decimal(c[key])
        return None

    base = {f: lv[0] for f, lv in factors.items()}
    full = {f: lv[-1] for f, lv in factors.items()}
    b, t = score(base), score(full)
    if b is None or t is None:
        return {"available": False}
    per, single_sum = {}, Decimal(0)
    for f, levels in factors.items():
        per[f] = {}
        at_base = [Decimal(c[key]) for c in cells if _label(c["levels"][f]) == _label(levels[0])]
        for lv in levels[1:]:
            one = score({**base, f: lv}) - b
            at_lv = [Decimal(c[key]) for c in cells if _label(c["levels"][f]) == _label(lv)]
            per[f][_label(lv)] = {"one_at_a_time": str(one.quantize(Q4)),
                                  "averaged": str((_mean(at_lv) - _mean(at_base)).quantize(Q4))}
        if len(levels) > 1:
            single_sum += Decimal(per[f][_label(levels[-1])]["one_at_a_time"])
    total = t - b
    return {"available": True, "base": str(b.quantize(Q4)), "full": str(t.quantize(Q4)),
            "total_change": str(total.quantize(Q4)), "sum_of_main_effects": str(single_sum.quantize(Q4)),
            "residual": str((total - single_sum).quantize(Q4)), "factors": per}


def run_grid(engine: Engine, pack, agent_name: str) -> dict:
    cfg = engine.config.experiments["grid"]
    agent = Runner(engine, pack).agent(agent_name)
    factors = load_factors(engine, agent)
    n = 1
    for levels in factors.values():
        n *= len(levels)
    if n > cfg["max_cells"]:
        raise EvalError(f"{agent.ref}: the grid has {n} cells, above eval.grid.max_cells {cfg['max_cells']}")
    use_holdout = cfg["holdout"] and (agent.dir / "eval" / "holdout.jsonl").is_file()
    cells = []
    for combo in itertools.product(*factors.values()):
        levels = dict(zip(factors, combo))
        model = str(levels.get("model", agent.model.model_string))
        label = ";".join(f"{f}={_label(lv)}" for f, lv in levels.items())
        exp = Experiment(label="grid", variants={agent_name: _transform(agent.dir, levels)}, variant_id=f"grid:{label}")
        rep = run_eval(engine, pack, agent_name, models=[model], experiment=exp)
        rep_h = run_eval(engine, pack, agent_name, models=[model], golden_file="holdout.jsonl", experiment=exp) if use_holdout else None
        cells.append({"cell": label, "levels": levels, "golden": rep["models"][0]["score"],
                      "golden_interval": rep["models"][0]["interval"], "summary": rep["summary"],
                      "holdout": None if rep_h is None else rep_h["models"][0]["score"]})
    return {"agent": agent.ref, "manifest_hash": agent.hash,
            "factors": {f: [_label(lv) for lv in levels] for f, levels in factors.items()},
            "cells": cells, "golden": effects(factors, cells, "golden"),
            "holdout": effects(factors, cells, "holdout") if use_holdout else None}


def write_grid(agent_dir: Path, report: dict, date: str) -> tuple[Path, Path]:
    eval_dir = agent_dir / "eval"
    js, md = eval_dir / f"grid-{date}.json", eval_dir / f"grid-{date}.md"
    js.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    g = report["golden"]
    lines = [f"# Factorial grid — {report['agent']} — {date}", "", f"manifest_hash: `{report['manifest_hash']}`", "",
             "| cell | golden | held-out |", "|---|---|---|"]
    lines += [f"| `{c['cell']}` | {c['golden']} | {c['holdout']} |" for c in report["cells"]]
    if g.get("available"):
        lines += ["", f"base {g['base']} -> full {g['full']}: total change {g['total_change']}, sum of one-at-a-time "
                      f"effects {g['sum_of_main_effects']}, residual {g['residual']}", "",
                  "| factor | level | one at a time | grid-averaged |", "|---|---|---|---|"]
        lines += [f"| {f} | `{lv}` | {e['one_at_a_time']} | {e['averaged']} |"
                  for f, levels in g["factors"].items() for lv, e in levels.items()]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md, js


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.grid")
    p.add_argument("agent_ref")
    p.add_argument("--date", help="grid date stamp (default: today on the engine clock)")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            from engine.integrity import safeguards
            safeguards(engine, pack, "eval", agent_name)
            rep = run_grid(engine, pack, agent_name)
            md, _ = write_grid(pack.agent_dir(agent_name), rep, args.date or engine.clock.now().date().isoformat())
        finally:
            engine.close()
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    g = rep["golden"]
    print(f"grid written: {md}")
    if g.get("available"):
        print(f"total change {g['total_change']} = sum of main effects {g['sum_of_main_effects']} + residual {g['residual']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
