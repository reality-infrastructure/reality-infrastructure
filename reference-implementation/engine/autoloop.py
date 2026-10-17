"""The closed loop: the pack's own agents decide the data, the verdict and the training.

    python -m engine.autoloop <pack> --week 2026-W42 [--max-runs N] [--no-plan] [--no-judge]
                                     [--no-refine] [--no-export] [--db DSN] [--out DIR]

One cycle, in order, every step traced as runs and events like any other:

  plan     the pack's ``planner`` reads the week's crank report, the unverdicted runs
           and the golden counts, and returns a batch of (agent, input) to run next;
           ``batch_resolves`` keeps it to agents the pack can run, under the cap
  act      the batch runs
  judge    the pack's ``judge`` reads every run of the week that has no verdict and
           returns one; ``verdict_grounded`` keeps it from contradicting code; the
           verdict is recorded with source ``agent:<judge>`` (a human verdict on the
           same run outranks it)
  crank    the weekly report over the week's runs and verdicts
  refine   when the crank recommends a rung-1/2 change, the pack's ``refiner`` proposes
           ONE exact text edit to that agent's skills, workflow or prompt;
           ``edit_applies`` keeps it to those files; the loop runs the agent's golden set
           before and after on a copy of the pack and adopts the edit only when the score
           does not fall and still passes; adopted or not, a ``<pack>.refinement`` event
           records the hashes and both scores
  export   for each specialist whose verdict gate is open, the SFT dataset is written

The model proposes at every step; code decides at every step.  Nothing here
places an order, holds a key or trains a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from engine.config import load_yaml
from engine.crank import build_report, render as render_crank, week_bounds
from engine.errors import EngineError, GateError
from engine.eval import load_golden, run_eval
from engine.events import EventLog
from engine.export import export
from engine.guardrails import JUDGEABLE_ROLES
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import iso
from engine.store import Engine
from engine.verdicts import record_verdict

LOOP_ROLES = ("planner", "judge", "refiner")
TEXT_FILES = ("skills.md", "workflow.md")


def loop_agents(pack) -> dict[str, str]:
    """{role: agent name} for the pack's planner, judge and refiner (first of each by name)."""
    out: dict[str, str] = {}
    for name in sorted(pack.agent_names):
        role = load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role")
        if role in LOOP_ROLES and role not in out:
            out[role] = name
    return out


def _slim_report(report: dict) -> dict:
    return {k: report[k] for k in ("week", "run_count", "agents", "verdicts", "override_reasons",
                                   "failure_clusters", "recommendation")}


def _run_summary(row: dict) -> dict:
    return {"run_id": row["run_id"], "agent": row["agent"], "status": row["status"], "input": row["input"],
            "verdict": row["human_verdict"], "verdict_source": row.get("verdict_source"), "created_at": row["created_at"]}


def _golden_counts(pack) -> dict[str, int]:
    out = {}
    for name in sorted(pack.agent_names):
        path = pack.agent_dir(name) / "eval" / "golden.jsonl"
        if path.is_file():
            out[name] = len(load_golden(path, pack_is_fixture=pack.fixture).cases)
    return out


# -- plan ---------------------------------------------------------------------------------

def plan(runner: Runner, planner: str, *, week: str, report: dict, pending: list[dict], max_runs: int) -> tuple[list[dict], dict]:
    result = runner.run(planner, {"week": week, "max_runs": max_runs, "report": _slim_report(report),
                                  "pending": pending[:50], "golden": _golden_counts(runner.pack)})
    batch = list(result.output["batch"])[:max_runs] if result.status == "succeeded" else []
    return batch, result.as_dict()


# -- act ----------------------------------------------------------------------------------

def act(runner: Runner, batch: list[dict]) -> list[dict]:
    out = []
    for item in batch:
        try:
            r = runner.run(item["agent"], item["input"])
            out.append({"agent": item["agent"], "input": item["input"], "run_id": r.run_id, "status": r.status,
                        "cost_usd": str(r.cost_usd)})
        except EngineError as e:                       # an errored run is traced by the runner; the loop goes on
            out.append({"agent": item["agent"], "input": item["input"], "run_id": None, "status": "error", "error": str(e)})
    return out


# -- judge --------------------------------------------------------------------------------

def unjudged(engine: Engine, pack, *, since: str, until: str) -> list[dict]:
    rows = engine.store.list_runs(pack=pack.name, since=since, until=until, verdicted=False)
    return [r for r in rows if r["role"] in JUDGEABLE_ROLES]


def judge(runner: Runner, judge_name: str, rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        try:
            r = runner.run(judge_name, {"run_id": row["run_id"]})
        except EngineError as e:
            out.append({"run_id": row["run_id"], "agent": row["agent"], "judge_run_id": None, "status": "error", "error": str(e)})
            continue
        entry = {"run_id": row["run_id"], "agent": row["agent"], "judge_run_id": r.run_id, "status": r.status}
        if r.status == "succeeded":
            record_verdict(runner.engine, runner.pack, row["run_id"], r.output["verdict"], r.output["reason"],
                           source=f"agent:{judge_name}", source_ref=r.run_id)
            entry["verdict"] = r.output["verdict"]
        out.append(entry)
    return out


# -- refine -------------------------------------------------------------------------------

def _target_agent(engine: Engine, pack, report: dict) -> str | None:
    ev = (report.get("recommendation") or {}).get("evidence") or {}
    for rid in ev.get("runs") or []:
        row = engine.store.get_run(rid)
        if row and row["role"] in JUDGEABLE_ROLES:
            return row["agent"]
    return None


def _text_files(agent_dir: Path) -> dict[str, str]:
    files = {}
    for name in TEXT_FILES:
        p = agent_dir / name
        if p.is_file():
            files[name] = p.read_text(encoding="utf-8")
    for p in sorted((agent_dir / "prompts").glob("*.md")):
        files[f"prompts/{p.name}"] = p.read_text(encoding="utf-8")
    return files


def _evidence(engine: Engine, report: dict) -> list[dict]:
    ev = (report.get("recommendation") or {}).get("evidence") or {}
    out = []
    for rid in (ev.get("runs") or [])[:3]:
        row = engine.store.get_run(rid)
        if row:
            out.append({"run_id": rid, "agent": row["agent"], "status": row["status"], "input": row["input"],
                        "failure_reasons": row["failure_reasons"][:6], "verdict": row["human_verdict"],
                        "verdict_reason": row["verdict_reason"]})
    return out


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def refine(engine: Engine, pack, runner: Runner, refiner: str, report: dict, *, packs_root: Path) -> dict:
    rec = report.get("recommendation") or {}
    rungs = engine.config.autoloop_refine_rungs
    if rec.get("rung") not in rungs:
        return {"status": "skipped", "why": f"recommendation rung {rec.get('rung')!r} is not in {list(rungs)}"}
    agent = _target_agent(engine, pack, report)
    if agent is None:
        return {"status": "skipped", "why": "no evidence run names an agent to refine"}
    files = _text_files(pack.agent_dir(agent))
    r = runner.run(refiner, {"agent": agent, "rung": rec["rung"], "rungs": list(rungs), "change": rec["change"],
                             "evidence": _evidence(engine, report), "files": files})
    if r.status != "succeeded":
        return {"status": "refiner_failed", "refiner_run_id": r.run_id, "agent": agent, "failure_reasons": list(r.failure_reasons)}
    out = r.output
    before = run_eval(engine, pack, agent)
    new_text = files[out["file"]].replace(out["old"], out["new"], 1)
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-"))
    try:
        copy_root = tmp / "packs"
        shutil.copytree(packs_root / pack.name, copy_root / pack.name,
                        ignore=shutil.ignore_patterns("__pycache__", ".harness", "crank", "export"))
        (copy_root / pack.name / "agents" / agent / out["file"]).write_text(new_text, encoding="utf-8", newline="\n")
        after = run_eval(engine, load_pack(pack.name, copy_root), agent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    b, a = Decimal(before["models"][0]["score"]), Decimal(after["models"][0]["score"])
    adopted = bool(after["pass"] and a >= b)
    if adopted:
        (pack.agent_dir(agent) / out["file"]).write_text(new_text, encoding="utf-8", newline="\n")
    event = EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=r.run_id, event_type=f"{pack.name}.refinement",
        payload={"agent": agent, "rung": int(out["rung"]), "file": out["file"], "old_sha256": _sha(files[out["file"]]),
                 "new_sha256": _sha(new_text), "before_score": str(b), "after_score": str(a), "adopted": adopted,
                 "refiner_run_id": r.run_id, "why": str(out["why"])[:1000]},
        source=f"agent:{refiner}", source_ref=r.run_id)
    return {"status": "adopted" if adopted else "rejected", "agent": agent, "file": out["file"], "rung": out["rung"],
            "before": before["summary"], "after": after["summary"], "refiner_run_id": r.run_id,
            "event_id": event["event_id"], "why": out["why"]}


# -- export -------------------------------------------------------------------------------

def export_open(engine: Engine, pack, out_dir: Path, stamp: str) -> list[dict]:
    out = []
    for name in sorted(pack.agent_names):
        if load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role") != "specialist":
            continue
        path = out_dir / "export" / f"{name}-{stamp}-sft.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            n = export(engine, pack, name, "sft", path)
            out.append({"agent": name, "status": "exported", "rows": n, "path": str(path)})
        except GateError as e:
            out.append({"agent": name, "status": "gate_closed", "why": str(e)})
    return out


# -- one cycle ----------------------------------------------------------------------------

def cycle(engine: Engine, pack, week: str, *, packs_root: Path, max_runs: int | None = None,
          do_plan: bool = True, do_judge: bool = True, do_refine: bool = True, do_export: bool = True,
          runner: Runner | None = None) -> dict:
    runner = runner or Runner(engine, pack)
    agents = loop_agents(pack)
    start, end = week_bounds(week)
    since, until = iso(start), iso(end)
    cap = max_runs or engine.config.autoloop_max_runs
    result: dict = {"pack": pack.name, "week": week, "loop_agents": agents}
    report = build_report(engine, pack, week)
    if do_plan and "planner" in agents:
        pending = [_run_summary(r) for r in unjudged(engine, pack, since=since, until=until)]
        batch, planned = plan(runner, agents["planner"], week=week, report=report, pending=pending, max_runs=cap)
        result["plan"] = {"run": planned, "batch": batch}
        result["act"] = act(runner, batch)
    if do_judge and "judge" in agents:
        result["judge"] = judge(runner, agents["judge"], unjudged(engine, pack, since=since, until=until))
    report = build_report(engine, pack, week)
    result["crank"] = _slim_report(report)
    if do_refine and "refiner" in agents:
        result["refine"] = refine(engine, pack, runner, agents["refiner"], report, packs_root=packs_root)
    if do_export:
        result["export"] = export_open(engine, pack, pack.root, week)
    return result


def render(result: dict) -> str:
    L = [f"# Autoloop — {result['pack']} — {result['week']}", "",
         f"loop agents: {result['loop_agents']}", ""]
    if "plan" in result:
        p = result["plan"]["run"]
        L += ["## Plan", "", f"planner run {p['run_id']} status {p['status']}; batch of {len(result['plan']['batch'])}", ""]
        L += [f"- {a['agent']} {json.dumps(a['input'], sort_keys=True)} -> {a.get('run_id')} {a['status']}" for a in result.get("act", [])] or ["- nothing to run"]
    if "judge" in result:
        L += ["", "## Judge", ""]
        counts: dict[str, int] = {}
        for j in result["judge"]:
            counts[j.get("verdict") or j["status"]] = counts.get(j.get("verdict") or j["status"], 0) + 1
        L += [f"{len(result['judge'])} runs adjudicated: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))]
        L += [f"- {j['run_id']} ({j['agent']}): {j.get('verdict') or j['status']} by judge run {j.get('judge_run_id')}" for j in result["judge"]]
    c = result["crank"]
    L += ["", "## Crank", "", f"runs {c['run_count']}; verdicts {c['verdicts']}; recommendation rung {c['recommendation'].get('rung')}: {c['recommendation'].get('change')}"]
    if "refine" in result:
        r = result["refine"]
        L += ["", "## Refine", "", f"{r['status']}" + (f": {r['agent']} {r['file']} rung {r['rung']}; golden before {r['before']} after {r['after']}; event {r['event_id']}" if r["status"] in ("adopted", "rejected") else f": {r.get('why') or r.get('failure_reasons')}")]
        if r.get("why") and r["status"] in ("adopted", "rejected"):
            L += ["", f"> {r['why']}"]
    if "export" in result:
        L += ["", "## Export", ""] + [f"- {e['agent']}: {e['status']}" + (f" ({e['rows']} rows -> {e['path']})" if e["status"] == "exported" else f" ({e['why']})") for e in result["export"]]
    L += ["", "Every step above is a traced run or a ledger-bound event; a human verdict recorded later outranks any agent verdict here."]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.autoloop")
    p.add_argument("pack")
    p.add_argument("--week", required=True)
    p.add_argument("--max-runs", type=int)
    p.add_argument("--no-plan", action="store_true")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--no-refine", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--db")
    p.add_argument("--out", help="directory (default packs/<pack>/crank)")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            pack = load_pack(args.pack)
            result = cycle(engine, pack, args.week, packs_root=pack.root.parent, max_runs=args.max_runs,
                           do_plan=not args.no_plan, do_judge=not args.no_judge, do_refine=not args.no_refine,
                           do_export=not args.no_export)
            crank_dir = Path(args.out) if args.out else pack.root / "crank"
            crank_dir.mkdir(parents=True, exist_ok=True)
            (crank_dir / f"{args.week}.md").write_text(render_crank(build_report(engine, pack, args.week)), encoding="utf-8")
        finally:
            engine.close()
        path = crank_dir / f"autoloop-{args.week}.md"
        path.write_text(render(result), encoding="utf-8")
        (crank_dir / f"autoloop-{args.week}.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"autoloop report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
