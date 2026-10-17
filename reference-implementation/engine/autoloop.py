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

The loop's law (config/engine.yaml ``autoloop``, on by default), from the three
interviews the operator read as a trader:
  held-out  (Schulman) an edit is adopted only if ``eval/holdout.jsonl``, which the
            loop never tunes on, does not fall either
  kill rule (Musk) an agent whose pass rate over its last runs collapses is halted:
            not planned, reported, until it recovers
  safety    (Brown) the judge is checked against the operator: above a disagreement
            rate its verdicts stop being recorded
  growth    (the panel) runs the operator marked followed become golden cases; the
            judge's own verdicts never do

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
from engine.drift import DriftContext
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


def _holdout_path(pack, agent: str) -> Path | None:
    """The held-out set, when it exists and holds at least one case (an empty one is a period not yet recorded)."""
    p = pack.agent_dir(agent) / "eval" / "holdout.jsonl"
    if not p.is_file():
        return None
    return p if load_golden(p, pack_is_fixture=pack.fixture).cases else None


# -- the loop's law -------------------------------------------------------------------------

def kill_rule(engine: Engine, pack) -> dict[str, str]:
    """{agent: why} for every worker/specialist/orchestrator whose pass rate over its last
    ``window_runs`` runs is below ``min_pass_rate`` once it has ``min_runs``."""
    cfg = engine.config.autoloop["kill"]
    killed: dict[str, str] = {}
    for name in sorted(pack.agent_names):
        if load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role") not in JUDGEABLE_ROLES:
            continue
        rows = engine.store.list_runs(pack=pack.name, agent=name, limit=int(cfg["window_runs"]), newest_first=True)
        if len(rows) < int(cfg["min_runs"]):
            continue
        ok = sum(1 for r in rows if r["status"] == "succeeded")
        rate = ok / len(rows)
        if rate < float(cfg["min_pass_rate"]):
            killed[name] = f"pass rate {rate:.2f} over the last {len(rows)} runs, below {cfg['min_pass_rate']}"
    return killed


def judge_safety(engine: Engine, pack) -> dict:
    """Two checks on the grader.  The operator's: how often a human, having looked at a run the judge
    adjudicated, said something else (compared = runs with an agent verdict event followed by a human one).
    The loop's own: how often the judge missed a honeypot, a succeeded run served to it with one figure
    altered (``<pack>.honeypot`` events).  Either rate above its threshold, after enough cases, suspends
    the judge: no agent verdict is recorded until a human looks."""
    cfg = engine.config.autoloop["judge"]
    pots = engine.store.query_events(event_type=f"{pack.name}.honeypot", limit=100000, ascending=True)
    planted = len(pots)
    missed = sum(1 for e in pots if not e["payload"]["hit"])
    miss_rate = (missed / planted) if planted else 0.0
    events = engine.store.query_events(event_type=f"{pack.name}.verdict", limit=100000, ascending=True)
    by_run: dict[str, list[dict]] = {}
    for e in events:
        by_run.setdefault(e["payload"]["run_id"], []).append(e)
    compared = disagreements = 0
    for run_id, evs in by_run.items():
        agent_v = None
        for e in evs:
            if e["source"].startswith("agent:"):
                agent_v = e["payload"]["verdict"]
            elif e["source"] == "human" and agent_v is not None:
                compared += 1
                disagreements += int(e["payload"]["verdict"] != agent_v)
                agent_v = None
    rate = (disagreements / compared) if compared else 0.0
    by_operator = compared >= int(cfg["min_compared"]) and rate > float(cfg["max_disagreement"])
    by_honeypots = planted >= int(cfg["min_planted"]) and miss_rate > float(cfg["max_missed"])
    return {"compared": compared, "disagreements": disagreements, "rate": round(rate, 4),
            "planted": planted, "missed": missed, "miss_rate": round(miss_rate, 4),
            "suspended": by_operator or by_honeypots, "suspended_by": "operator" if by_operator else "honeypots" if by_honeypots else None,
            "max_disagreement": float(cfg["max_disagreement"]), "min_compared": int(cfg["min_compared"]),
            "max_missed": float(cfg["max_missed"]), "min_planted": int(cfg["min_planted"])}


def _numeric_leaf(output, path: tuple = ()) -> tuple[str, object] | None:
    """The first numeric leaf of an output, depth first, skipping citations and confidence: what a honeypot alters."""
    if isinstance(output, bool):
        return None
    if isinstance(output, (int, float)):
        return ".".join(path), output
    if isinstance(output, dict):
        for k, v in output.items():
            if k in ("citations", "confidence"):
                continue
            found = _numeric_leaf(v, path + (k,))
            if found:
                return found
    if isinstance(output, list):
        for i, v in enumerate(output):
            found = _numeric_leaf(v, path + (str(i),))
            if found:
                return found
    return None


def plant_honeypots(runner: Runner, judge_name: str, rows: list[dict], k: int) -> list[dict]:
    """Serve the judge k succeeded runs with one figure altered and record whether it noticed.  A hit is a verdict
    of overridden or wrong whose reason names the altered field; the verdict is never recorded on the real run."""
    out = []
    for row in [r for r in rows if r["status"] == "succeeded" and r["role"] in JUDGEABLE_ROLES][-k:]:
        leaf = _numeric_leaf(row["output"])
        if leaf is None:
            continue
        path, value = leaf
        altered = value + 1 if isinstance(value, int) else round(value * 1.07 + 0.01, 6)
        runner.honeypots[row["run_id"]] = (path, altered)
        try:
            j = runner.run(judge_name, {"run_id": row["run_id"]})
        except EngineError as e:
            runner.honeypots.pop(row["run_id"], None)
            out.append({"target_run_id": row["run_id"], "judge_run_id": None, "path": path, "hit": False, "verdict": None, "error": str(e)[:200]})
            continue
        finally:
            runner.honeypots.pop(row["run_id"], None)
        verdict = j.output["verdict"] if j.status == "succeeded" else None
        field = path.split(".")[-1]
        hit = bool(verdict in ("overridden", "wrong") and j.status == "succeeded" and field in (j.output.get("reason") or ""))
        ev = EventLog(runner.engine, runner.pack).append(
            entity_type="agent_run", entity_id=j.run_id, event_type=f"{runner.pack.name}.honeypot",
            payload={"target_run_id": row["run_id"], "judge_run_id": j.run_id, "path": path, "hit": hit, "verdict": verdict},
            source=f"agent:{judge_name}", source_ref=j.run_id)
        out.append({"target_run_id": row["run_id"], "judge_run_id": j.run_id, "path": path, "hit": hit, "verdict": verdict, "event_id": ev["event_id"]})
    return out


def drift_readings(engine: Engine, pack) -> list[dict]:
    """Every drift function the pack declares, recorded as events; the loop refines and grows nothing while any says shifted."""
    if not pack.drift or not pack.drift.ids():
        return []
    readings = pack.drift.readings(DriftContext(pack=pack, engine=engine, read_table=pack.table_rows))
    log = EventLog(engine, pack)
    for r in readings:
        log.append(entity_type="agent_run", entity_id=pack.name, event_type=f"{pack.name}.drift",
                   payload={"id": r["id"], "shifted": r["shifted"], "why": r["why"], "measured": r["measured"]}, source="pipeline:autoloop")
    return readings


def grow_golden(engine: Engine, pack, *, since: str, until: str) -> list[dict]:
    """Runs the OPERATOR marked ``followed`` (never the judge) whose input is not yet a golden case
    become golden cases, with the compare fields copied from the certified output."""
    grown = []
    for name in sorted(pack.agent_names):
        path = pack.agent_dir(name) / "eval" / "golden.jsonl"
        if not path.is_file():
            continue
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        header = json.loads(lines[0])
        known = {json.dumps(json.loads(ln)["input"], sort_keys=True) for ln in lines[1:]}
        rows = engine.store.list_runs(pack=pack.name, agent=name, since=since, until=until, status="succeeded",
                                      verdicted=True, verdict_source="human")
        new = []
        for r in rows:
            key = json.dumps(r["input"], sort_keys=True)
            if r["human_verdict"] != "followed" or key in known:
                continue
            try:
                expected = {f.split(".")[0]: r["output"][f.split(".")[0]] for f in header["compare"]}
            except (KeyError, TypeError):
                continue
            case = {"id": f"run-{r['run_id']}", "provenance": f"grown by the loop: run {r['run_id']} ({name}) marked followed by the "
                                                             f"operator at {r['verdict_at']}: {r['verdict_reason']}",
                    "input": r["input"], "expected": expected}
            new.append(case)
            known.add(key)
        if new:
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                for c in new:
                    f.write(json.dumps(c) + "\n")
            grown.append({"agent": name, "added": len(new), "ids": [c["id"] for c in new]})
    return grown


def _golden_counts(pack) -> dict[str, int]:
    out = {}
    for name in sorted(pack.agent_names):
        path = pack.agent_dir(name) / "eval" / "golden.jsonl"
        if path.is_file():
            out[name] = len(load_golden(path, pack_is_fixture=pack.fixture).cases)
    return out


# -- plan ---------------------------------------------------------------------------------

def plan(runner: Runner, planner: str, *, week: str, report: dict, pending: list[dict], max_runs: int,
         killed: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    result = runner.run(planner, {"week": week, "max_runs": max_runs, "report": _slim_report(report),
                                  "pending": pending[:50], "golden": _golden_counts(runner.pack),
                                  "killed": dict(killed or {})})
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

def _target_cluster(engine: Engine, pack, report: dict) -> tuple[str, dict] | None:
    """The first failure cluster (the crank orders them by count) whose evidence runs belong to a
    worker, specialist or orchestrator: loop roles are never refined by the loop.  Falls back to
    the recommendation's own evidence when it names such a run."""
    candidates = list(report.get("failure_clusters") or [])
    rec_ev = (report.get("recommendation") or {}).get("evidence") or {}
    if rec_ev.get("runs"):
        candidates.insert(0, rec_ev)
    for cluster in candidates:
        for rid in cluster.get("runs") or []:
            row = engine.store.get_run(rid)
            if row and row["role"] in JUDGEABLE_ROLES:
                return row["agent"], cluster
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


def _evidence(engine: Engine, cluster: dict) -> list[dict]:
    out = []
    for rid in (cluster.get("runs") or [])[:3]:
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
    target = _target_cluster(engine, pack, report)
    if target is None:
        return {"status": "skipped", "why": "no failure cluster names a worker, specialist or orchestrator run to refine"}
    agent, cluster = target
    files = _text_files(pack.agent_dir(agent))
    change = rec["change"] if cluster is rec.get("evidence") else f"{rec['change']} Cluster: {cluster.get('cluster')} ({cluster.get('count')}x)."
    r = runner.run(refiner, {"agent": agent, "rung": rec["rung"], "rungs": list(rungs), "change": change,
                             "evidence": _evidence(engine, cluster), "files": files})
    if r.status != "succeeded":
        return {"status": "refiner_failed", "refiner_run_id": r.run_id, "agent": agent, "failure_reasons": list(r.failure_reasons)}
    out = r.output
    if out.get("file") is None:                                    # the refiner declined: no edit warranted
        return {"status": "declined", "agent": agent, "rung": out.get("rung"), "refiner_run_id": r.run_id, "why": out["why"]}
    use_holdout = engine.config.autoloop["holdout"] and _holdout_path(pack, agent) is not None
    before = run_eval(engine, pack, agent)
    before_h = run_eval(engine, pack, agent, golden_file="holdout.jsonl") if use_holdout else None
    new_text = files[out["file"]].replace(out["old"], out["new"], 1)
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-"))
    try:
        copy_root = tmp / "packs"
        shutil.copytree(packs_root / pack.name, copy_root / pack.name,
                        ignore=shutil.ignore_patterns("__pycache__", ".harness", "crank", "export"))
        (copy_root / pack.name / "agents" / agent / out["file"]).write_text(new_text, encoding="utf-8", newline="\n")
        pack_copy = load_pack(pack.name, copy_root)
        after = run_eval(engine, pack_copy, agent)
        after_h = run_eval(engine, pack_copy, agent, golden_file="holdout.jsonl") if use_holdout else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    adopted = adopt_decision(before, after, before_h, after_h)
    if adopted:
        (pack.agent_dir(agent) / out["file"]).write_text(new_text, encoding="utf-8", newline="\n")
    event = EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=r.run_id, event_type=f"{pack.name}.refinement",
        payload={"agent": agent, "rung": int(out["rung"]), "file": out["file"], "old_sha256": _sha(files[out["file"]]),
                 "new_sha256": _sha(new_text), "before_score": before["models"][0]["score"],
                 "after_score": after["models"][0]["score"], "adopted": adopted,
                 "refiner_run_id": r.run_id, "why": str(out["why"])[:1000],
                 "before_holdout": None if before_h is None else before_h["models"][0]["score"],
                 "after_holdout": None if after_h is None else after_h["models"][0]["score"]},
        source=f"agent:{refiner}", source_ref=r.run_id)
    return {"status": "adopted" if adopted else "rejected", "agent": agent, "file": out["file"], "rung": out["rung"],
            "before": before["summary"], "after": after["summary"],
            "before_holdout": None if before_h is None else before_h["summary"],
            "after_holdout": None if after_h is None else after_h["summary"],
            "holdout": "held-out set evaluated" if use_holdout else "no eval/holdout.jsonl for this agent: adoption rests on the golden set alone",
            "refiner_run_id": r.run_id, "event_id": event["event_id"], "why": out["why"]}


def adopt_decision(before: dict, after: dict, before_holdout: dict | None, after_holdout: dict | None) -> bool:
    """Adopt only if the golden score did not fall and still passes, AND (when a held-out set exists) the
    held-out score did not fall and still passes.  The held-out set is the benchmark the loop never tunes on."""
    b, a = Decimal(before["models"][0]["score"]), Decimal(after["models"][0]["score"])
    ok = bool(after["pass"] and a >= b)
    if before_holdout is not None and after_holdout is not None:
        bh, ah = Decimal(before_holdout["models"][0]["score"]), Decimal(after_holdout["models"][0]["score"])
        ok = ok and bool(after_holdout["pass"] and ah >= bh)
    return ok


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
    killed = kill_rule(engine, pack)
    safety = judge_safety(engine, pack)
    drift = drift_readings(engine, pack)
    result["safety"] = {"killed": killed, "judge": safety, "drift": drift}
    shifted = [d for d in drift if d["shifted"]]
    report = build_report(engine, pack, week)
    if do_plan and "planner" in agents:
        pending = [_run_summary(r) for r in unjudged(engine, pack, since=since, until=until)]
        batch, planned = plan(runner, agents["planner"], week=week, report=report, pending=pending, max_runs=cap, killed=killed)
        result["plan"] = {"run": planned, "batch": batch}
        result["act"] = act(runner, batch)
    if do_judge and "judge" in agents:
        if safety["suspended"]:
            result["judge"] = []
            result["judge_suspended"] = (f"suspended by {safety['suspended_by']}: the operator disagreed with {safety['disagreements']} of "
                                         f"{safety['compared']} agent verdicts ({safety['rate']:.0%}), honeypots missed {safety['missed']} of "
                                         f"{safety['planted']} ({safety['miss_rate']:.0%}): no agent verdict recorded this cycle")
        else:
            result["judge"] = judge(runner, agents["judge"], unjudged(engine, pack, since=since, until=until))
            k = int(engine.config.autoloop["judge"]["honeypots_per_cycle"])
            if k > 0:
                result["honeypots"] = plant_honeypots(runner, agents["judge"], engine.store.list_runs(pack=pack.name, since=since, until=until, status="succeeded"), k)
    report = build_report(engine, pack, week)
    result["crank"] = _slim_report(report)
    if shifted:
        why = "; ".join(f"{d['id']}: {d['why']}" for d in shifted)
        result["refine"] = {"status": "skipped", "why": f"drift: {why}; golden and held-out sets must be re-counted against the new record before any edit is adopted"}
        result["grow"] = []
        result["drift_hold"] = why
    else:
        if do_refine and "refiner" in agents:
            result["refine"] = refine(engine, pack, runner, agents["refiner"], report, packs_root=packs_root)
        if engine.config.autoloop["grow_golden"]:
            result["grow"] = grow_golden(engine, pack, since=since, until=until)
    if do_export:
        result["export"] = export_open(engine, pack, pack.root, week)
    result["safety"]["killed_after"] = kill_rule(engine, pack)
    return result


def render(result: dict) -> str:
    L = [f"# Autoloop — {result['pack']} — {result['week']}", "",
         f"loop agents: {result['loop_agents']}", ""]
    if "safety" in result:
        s = result["safety"]
        L += ["## The loop's law", ""]
        L += [f"- kill rule: {', '.join(f'{a} halted ({w})' for a, w in s['killed'].items()) or 'no agent halted'}"
              + (f"; after this cycle: {', '.join(f'{a} halted' for a in s['killed_after']) or 'none'}" if "killed_after" in s else "")]
        j = s["judge"]
        L += [f"- judge safety case: the operator reviewed {j['compared']} agent verdicts and disagreed with {j['disagreements']} "
              f"({j['rate']:.0%}; suspension above {j['max_disagreement']:.0%} after {j['min_compared']}); honeypots planted "
              f"{j.get('planted', 0)}, missed {j.get('missed', 0)} ({j.get('miss_rate', 0):.0%}; suspension above {j.get('max_missed', 0):.0%} "
              f"after {j.get('min_planted', 0)}): " + ("SUSPENDED" if j["suspended"] else "trusted")]
        if result.get("judge_suspended"):
            L += [f"  {result['judge_suspended']}"]
        if result.get("honeypots"):
            L += [f"- honeypots this cycle: " + ", ".join(f"{h['path']} -> {'hit' if h['hit'] else 'MISS'} ({h['verdict']})" for h in result["honeypots"])]
        for d in s.get("drift") or []:
            L += [f"- drift {d['id']}: {'SHIFTED' if d['shifted'] else 'steady'}: {d['why']}"]
        if result.get("drift_hold"):
            L += [f"  no edit adopted and no golden case grown while the distribution has moved: {result['drift_hold']}"]
        L += [""]
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
        L += ["", "## Refine", "", f"{r['status']}" + (f": {r['agent']} {r['file']} rung {r['rung']}; golden before {r['before']} after {r['after']}; held-out before {r.get('before_holdout')} after {r.get('after_holdout')} ({r.get('holdout')}); event {r['event_id']}" if r["status"] in ("adopted", "rejected") else f": {r.get('why') or r.get('failure_reasons')}")]
        if r.get("why") and r["status"] in ("adopted", "rejected"):
            L += ["", f"> {r['why']}"]
        if r["status"] == "declined":
            L += ["", f"The refiner (run {r['refiner_run_id']}) found no edit the evidence warrants; nothing changed and no golden evaluation was spent."]
    if "grow" in result:
        L += ["", "## Golden growth (operator-followed runs only)", ""]
        L += [f"- {g['agent']}: +{g['added']} cases ({', '.join(g['ids'][:5])}{'…' if g['added'] > 5 else ''})" for g in result["grow"]] or ["- nothing to add"]
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
