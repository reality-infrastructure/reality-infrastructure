"""Ablation and attribution (JH-C11 wpC; Brown G-B2, Patel G-D14 ablation part).

    python -m engine.ablate <pack>/<agent> [--components grounding,memory,...] [--date YYYY-MM-DD] [--db DSN]

Brown: "I wouldn't even attribute 10% of the credit to multi-agent ... Things like multi-agent are flashy and new,
and that probably gets disproportionate credit"; Patel: "small-scale ablations ... to make them oh-so-slightly
better", and data improvements outweighing method improvements.  The agent's golden set (and its held-out set,
``eval.ablation_holdout``) is scored as it is, then once per component with that component removed:

- ``grounding:<kind>:<ref>``  one grounding source emptied           (class data)
- ``memory:long_term``        long-term memory off                   (class data)
- ``skills:<section>``        one ``## `` section of skills.md blank (class method; ``skills:*`` without sections)
- ``workflow:<section>``      one section of workflow.md blank       (class method)
- ``onboarding:*``            skills.md and workflow.md both blank   (class method)
- ``children``                an orchestrator without its child agents: the one-agent topology on the same inputs
                              (agent tools withdrawn from the model and from its access)  (class method)
- ``scaffold:*``              all of the above at once: the model alone (class scaffold)

``eval.ablations`` lists the kinds.  Each component's runs are an agent variant (engine.experiment), recorded
under a derived manifest hash so they never count as the agent's version.  Per component one ``<pack>.ablation``
event {component, kind, class, score_full, score_ablated, delta, intervals, held-out scores}.

The report attributes: credit shares of the full score (the model alone = the scaffold ablation's score, each
component = its delta, the interaction = what the sum of single deltas does not explain); data versus method,
from the ablation deltas and from the gains of adopted rung-1 (grounding) and rung-2 (harness) refinements; and
who directed the agent's outputs (Brown: "how much do you attribute to the human?"): its top-level runs by input
origin (planned by the loop's planner, started by a declared event, delegated by an orchestrator, or given by the
operator) with their succeeded and followed counts.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from decimal import Decimal
from pathlib import Path

from engine.errors import EngineError, EvalError
from engine.eval import run_eval
from engine.events import EventLog
from engine.experiment import Experiment, is_experiment_run
from engine.loop import Runner
from engine.manifest import AGENT_TOOL_PREFIX
from engine.packs import load_pack, parse_agent_ref
from engine.store import Engine

Q4 = Decimal("0.0001")
CLASS = {"grounding": "data", "memory": "data", "skills": "method", "workflow": "method", "onboarding": "method",
         "children": "method", "scaffold": "scaffold"}


def sections(text: str) -> list[str]:
    """The ``## `` headings of a markdown onboarding file, in order."""
    return [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]


def drop_section(text: str, heading: str) -> str:
    out, skipping = [], False
    for ln in text.splitlines(keepends=True):
        if ln.startswith("## "):
            skipping = ln[3:].strip() == heading
        elif ln.startswith("# "):
            skipping = False
        if not skipping:
            out.append(ln)
    return "".join(out)


def _without_children(agent):
    tools = tuple(t for t in agent.tools if not t.startswith(AGENT_TOOL_PREFIX))
    return dataclasses.replace(agent, tools=tools, model=dataclasses.replace(agent.model, tools=tools),
                               access=dataclasses.replace(agent.access, agents=frozenset(),
                                                          tools=frozenset(t for t in agent.access.tools
                                                                          if not t.startswith(AGENT_TOOL_PREFIX))))


def _scaffold_off(agent):
    agent = _without_children(agent)
    return dataclasses.replace(agent, grounding=(), memory={**agent.memory, "long_term": None}, skills="", workflow="")


def components(agent, kinds: tuple[str, ...]) -> list[dict]:
    """``[{id, kind, class, transform}]`` for the agent as it is loaded."""
    out = []

    def add(cid: str, kind: str, fn):
        out.append({"id": cid, "kind": kind, "class": CLASS[kind], "transform": fn})

    if "grounding" in kinds:
        for i, src in enumerate(agent.grounding):
            add(f"grounding:{src['kind']}:{src['ref']}", "grounding",
                lambda a, i=i: dataclasses.replace(a, grounding=tuple(s for j, s in enumerate(a.grounding) if j != i)))
    if "memory" in kinds and agent.memory.get("long_term") is not None:
        add("memory:long_term", "memory", lambda a: dataclasses.replace(a, memory={**a.memory, "long_term": None}))
    for kind in ("skills", "workflow"):
        if kind not in kinds:
            continue
        heads = sections(getattr(agent, kind))
        for h in heads:
            add(f"{kind}:{h}", kind, lambda a, h=h, k=kind: dataclasses.replace(a, **{k: drop_section(getattr(a, k), h)}))
        if not heads:
            add(f"{kind}:*", kind, lambda a, k=kind: dataclasses.replace(a, **{k: ""}))
    if "onboarding" in kinds:
        add("onboarding:*", "onboarding", lambda a: dataclasses.replace(a, skills="", workflow=""))
    if "children" in kinds and any(t.startswith(AGENT_TOOL_PREFIX) for t in agent.tools):
        add("children", "children", _without_children)
    if "scaffold" in kinds:
        add("scaffold:*", "scaffold", _scaffold_off)
    return out


def _score(rep: dict | None) -> Decimal | None:
    return None if rep is None else Decimal(rep["models"][0]["score"])


def _s(d: Decimal | None) -> str | None:
    return None if d is None else str(d.quantize(Q4))


def refinement_gains(engine: Engine, pack, agent: str) -> dict:
    """Golden (and held-out) gain of the agent's adopted refinements by rung: 1 = grounding (data), 2 = harness (method)."""
    out = {"1": {"adopted": 0, "golden_gain": Decimal(0), "holdout_gain": Decimal(0)},
           "2": {"adopted": 0, "golden_gain": Decimal(0), "holdout_gain": Decimal(0)}}
    for e in engine.store.query_events(event_type=f"{pack.name}.refinement", limit=100000, ascending=True):
        p = e["payload"]
        if p["agent"] != agent or not p["adopted"] or str(p["rung"]) not in out:
            continue
        row = out[str(p["rung"])]
        row["adopted"] += 1
        row["golden_gain"] += Decimal(p["after_score"]) - Decimal(p["before_score"])
        if p.get("before_holdout") is not None and p.get("after_holdout") is not None:
            row["holdout_gain"] += Decimal(p["after_holdout"]) - Decimal(p["before_holdout"])
    return {k: {"adopted": v["adopted"], "golden_gain": _s(v["golden_gain"]), "holdout_gain": _s(v["holdout_gain"])}
            for k, v in out.items()}


def output_origins(engine: Engine, pack, agent: str) -> dict:
    """Who directed each top-level output of the agent: the loop's planner, a declared event, an orchestrator, or
    the operator; with how many succeeded and how many the operator (or the judge) marked followed."""
    runs = [r for r in engine.store.list_runs(pack=pack.name) if not is_experiment_run(r)]
    planned: list[tuple[str, str]] = []
    for r in runs:
        if r["role"] == "planner" and r["status"] == "succeeded":
            planned += [(r["created_at"], json.dumps({"agent": i.get("agent"), "input": i.get("input")}, sort_keys=True))
                        for i in (r["output"] or {}).get("batch") or [] if isinstance(i, dict)]
    triggered = {e["payload"].get("run_id") for e in engine.store.query_events(
        event_type=f"{pack.name}.trigger_dispatch", limit=100000, ascending=True)}
    out = {o: {"runs": 0, "succeeded": 0, "followed": 0} for o in ("operator", "planned", "triggered", "delegated")}
    for r in runs:
        if r["agent"] != agent:
            continue
        key = json.dumps({"agent": agent, "input": r["input"]}, sort_keys=True)
        origin = ("delegated" if r["parent_run_id"] else "triggered" if r["run_id"] in triggered
                  else "planned" if any(at <= r["created_at"] and k == key for at, k in planned) else "operator")
        row = out[origin]
        row["runs"] += 1
        row["succeeded"] += int(r["status"] == "succeeded")
        row["followed"] += int(r["human_verdict"] == "followed")
    followed = sum(v["followed"] for v in out.values())
    for v in out.values():
        v["share_of_followed"] = None if not followed else round(v["followed"] / followed, 4)
    return out


def ablate(engine: Engine, pack, agent_name: str, *, kinds: tuple[str, ...] | None = None) -> dict:
    cfg = engine.config.experiments
    kinds = tuple(kinds or cfg["ablations"])
    unknown = sorted(set(kinds) - set(CLASS))
    if unknown:
        raise EvalError(f"unknown ablation kind(s) {unknown}; known: {sorted(CLASS)}")
    agent = Runner(engine, pack).agent(agent_name)
    origins = output_origins(engine, pack, agent_name)          # before this ablation's own eval runs exist
    use_holdout = cfg["ablation_holdout"] and (agent.dir / "eval" / "holdout.jsonl").is_file()
    full = run_eval(engine, pack, agent_name)
    full_h = run_eval(engine, pack, agent_name, golden_file="holdout.jsonl") if use_holdout else None
    f, fh = _score(full), _score(full_h)
    log = EventLog(engine, pack)
    rows = []
    for comp in components(agent, kinds):
        exp = Experiment(label="ablation", variants={agent_name: comp["transform"]}, variant_id=f"ablate:{comp['id']}")
        ab = run_eval(engine, pack, agent_name, experiment=exp)
        ab_h = run_eval(engine, pack, agent_name, golden_file="holdout.jsonl", experiment=exp) if use_holdout else None
        a, ah = _score(ab), _score(ab_h)
        payload = {"agent": agent_name, "manifest_hash": agent.hash, "component": comp["id"], "kind": comp["kind"],
                   "class": comp["class"], "score_full": _s(f), "score_ablated": _s(a), "delta": _s(f - a),
                   "interval_full": full["models"][0]["interval"], "interval_ablated": ab["models"][0]["interval"],
                   "holdout_full": _s(fh), "holdout_ablated": _s(ah),
                   "holdout_delta": None if fh is None or ah is None else _s(fh - ah)}
        ev = log.append(entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.ablation",
                        payload=payload, source="pipeline:eval")
        rows.append({**payload, "event_id": ev["event_id"], "summary": ab["summary"]})
    singles = [r for r in rows if r["class"] != "scaffold"]
    bare = next((Decimal(r["score_ablated"]) for r in rows if r["class"] == "scaffold"), None)
    credit = None
    if f > 0:
        credit = {"components": {r["component"]: _s(Decimal(r["delta"]) / f) for r in singles}}
        if bare is not None:
            credit["model_alone"] = _s(bare / f)
            credit["interaction"] = _s((f - bare - sum(Decimal(r["delta"]) for r in singles)) / f)
    by_class = {c: _s(sum((Decimal(r["delta"]) for r in singles if r["class"] == c), Decimal(0))) for c in ("data", "method")}
    return {"agent": agent.ref, "manifest_hash": agent.hash, "score_full": _s(f), "holdout_full": _s(fh),
            "full_summary": full["summary"], "components": rows, "credit": credit,
            "data_vs_method": {"ablation": by_class, "refinements": refinement_gains(engine, pack, agent_name)},
            "origins": origins}


def write_report(agent_dir: Path, report: dict, date: str) -> tuple[Path, Path]:
    eval_dir = agent_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    js, md = eval_dir / f"ablation-{date}.json", eval_dir / f"ablation-{date}.md"
    js.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [f"# Ablation — {report['agent']} — {date}", "", f"manifest_hash: `{report['manifest_hash']}`  ",
             f"full: {report['score_full']} (held-out {report['holdout_full']})", "",
             "| component | class | ablated | delta | held-out delta |", "|---|---|---|---|---|"]
    lines += [f"| `{r['component']}` | {r['class']} | {r['score_ablated']} | {r['delta']} | {r['holdout_delta']} |"
              for r in report["components"]]
    lines += ["", f"credit: `{json.dumps(report['credit'], sort_keys=True)}`  ",
              f"data vs method: `{json.dumps(report['data_vs_method'], sort_keys=True)}`  ",
              f"output origins: `{json.dumps(report['origins'], sort_keys=True)}`"]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md, js


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.ablate")
    p.add_argument("agent_ref")
    p.add_argument("--components", help="comma-separated kinds (default: eval.ablations)")
    p.add_argument("--date", help="report date stamp (default: today on the engine clock)")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            from engine.integrity import safeguards
            safeguards(engine, pack, "eval", agent_name)
            rep = ablate(engine, pack, agent_name,
                         kinds=tuple(k.strip() for k in args.components.split(",")) if args.components else None)
            md, _ = write_report(pack.agent_dir(agent_name), rep, args.date or engine.clock.now().date().isoformat())
        finally:
            engine.close()
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for r in rep["components"]:
        print(f"{r['component']}: {r['score_ablated']} (delta {r['delta']})")
    print(f"report written: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
