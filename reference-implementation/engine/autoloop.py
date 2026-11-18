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

The long-horizon record (JH-C11 wpI): before the steps, due forward claims are resolved
(engine.outcome) and due dated forecasts scored (engine.forecast), and a halted agent gets
probation runs (engine.reputation); the plan is ranked by the pack's @value hooks and capped
by each agent's reputation tier (engine.value); the planner's p_pass and the refiner's
p_adopt, deltas and dated target are scored, and a poorly calibrated role is suspended; after
refine the ``curator`` proposes cases code admits only when correct and discriminating
(engine.curate); at the end every agent's reputation is recorded.

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

from engine import curriculum, rigor, stats
from engine.analytics import novelty_for_planner, record_cycle
from engine.attribution import inherited_blame
from engine.blame import blame_week
from engine.config import load_yaml
from engine.constraint import planner_input
from engine.crank import build_report, render as render_crank, week_bounds
from engine.drift import DriftContext
from engine.errors import EngineError, GateError
from engine.eval import load_golden, run_eval
from engine.events import EventLog
from engine.export import export
from engine.guardrails import JUDGEABLE_ROLES
from engine import integrity
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import iso
from engine.store import Engine
from engine import curate as curator_step, forecast, outcome, reputation, value
from engine import governance, incidents
from engine.outcome import proven_wrong, resolved_hits

LOOP_ROLES = ("planner", "judge", "refiner", "curator")
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
    outcome_kills = engine.config.outcomes["enabled"] and engine.config.outcomes["kill_on_outcome"]
    killed: dict[str, str] = {}
    for name in sorted(pack.agent_names):
        if load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role") not in JUDGEABLE_ROLES:
            continue
        rows = engine.store.list_runs(pack=pack.name, agent=name, limit=int(cfg["window_runs"]), newest_first=True)
        if len(rows) < int(cfg["min_runs"]):
            continue
        ok = sum(1 for r in rows if r["status"] == "succeeded" and not (outcome_kills and proven_wrong(r)))
        blamed = inherited_blame(engine, pack, {r["run_id"] for r in rows if r["status"] == "succeeded"})
        ok = max(0.0, ok - float(engine.config.analytics["attribution"]["inherited_weight"]) * len(blamed))   # blame a cited child inherits
        rate = ok / len(rows)
        st = engine.config.stats
        if stats.decide(ok, len(rows), float(cfg["min_pass_rate"]), side="below", confidence=st["confidence"], on_bounds=st["gate_on_bounds"]):
            lo, hi = stats.wilson(ok, len(rows), st["confidence"])
            killed[name] = (f"pass rate {rate:.2f} over the last {len(rows)} runs, below {cfg['min_pass_rate']} "
                            f"({st['confidence']:.0%} interval {lo:.4f}-{hi:.4f}{', gated on the upper bound' if st['gate_on_bounds'] else ''}"
                            f"{f'; {len(blamed)} succeeded runs carry blame inherited from an orchestrator' if blamed else ''})")
    from engine.risk import ruin_halts             # JH-C11 G-NCD5: one ruinous loss halts whatever the average
    for name, why in ruin_halts(engine, pack).items():
        killed[name] = why
    for name, why in integrity.monitor_halts(engine, pack).items():
        killed.setdefault(name, why)
    for name, why in governance.integrity_halts(engine, pack).items():   # JH-C11 G-NAB9: integrity halts at once
        killed.setdefault(name, why)
    incidents.record_halts(engine, pack, killed)                         # JH-C11 G-B15: every halt is an incident
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
    st = engine.config.stats
    by_operator = compared >= int(cfg["min_compared"]) and stats.decide(
        disagreements, compared, float(cfg["max_disagreement"]), side="above", confidence=st["confidence"], on_bounds=st["gate_on_bounds"])
    by_honeypots = planted >= int(cfg["min_planted"]) and stats.decide(
        missed, planted, float(cfg["max_missed"]), side="above", confidence=st["confidence"], on_bounds=st["gate_on_bounds"])
    col = integrity.collusion(engine, pack)
    gi = governance.judge_integrity(engine, pack)                       # JH-C11 G-NAB9: a missed honeypot is an integrity breach
    out = {"compared": compared, "disagreements": disagreements, "rate": round(rate, 4),
            "planted": planted, "missed": missed, "miss_rate": round(miss_rate, 4), "collusion": col,
            "suspended": by_operator or by_honeypots or col["suspended"],
            "suspended_by": "operator" if by_operator else "honeypots" if by_honeypots else "collusion" if col["suspended"] else None,
            "max_disagreement": float(cfg["max_disagreement"]), "min_compared": int(cfg["min_compared"]),
            "max_missed": float(cfg["max_missed"]), "min_planted": int(cfg["min_planted"]),
            "rate_interval": stats.rate(disagreements, compared, st["confidence"]),
            "miss_rate_interval": stats.rate(missed, planted, st["confidence"]), "gate_on_bounds": st["gate_on_bounds"]}
    if gi["halted"]:
        out.update(suspended=True, suspended_by=out["suspended_by"] or "integrity", integrity=gi["why"])
    incidents.record_judge(engine, pack, out)                            # JH-C11 G-B15
    return out


def plant_honeypots(runner: Runner, judge_name: str, rows: list[dict], k: int) -> list[dict]:
    """Serve the judge k succeeded runs with figures altered, in graded tiers, and record whether it noticed
    (engine.integrity.plant_honeypots).  The verdict is never recorded on the real run."""
    return integrity.plant_honeypots(runner, judge_name, rows, k)


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
    synthetic = {e["payload"]["run_id"] for e in engine.store.query_events(event_type=f"{pack.name}.synthetic_input", limit=1000000)}
    for name in sorted(pack.agent_names):
        path = pack.agent_dir(name) / "eval" / "golden.jsonl"
        if not path.is_file():
            continue
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        header = json.loads(lines[0])
        known = {json.dumps(json.loads(ln)["input"], sort_keys=True) for ln in lines[1:]}
        rows = engine.store.list_runs(pack=pack.name, agent=name, since=since, until=until, status="succeeded",
                                      verdicted=True, verdict_source="human")
        eligible = resolved_hits(engine, pack, name)          # an agent making forward claims grows only from claims the world proved
        new = []
        for r in rows:
            key = json.dumps(r["input"], sort_keys=True)
            if (r["human_verdict"] != "followed" or key in known or (eligible is not None and r["run_id"] not in eligible)
                    or r["run_id"] in synthetic):
                continue
            try:
                expected = {f.split(".")[0]: r["output"][f.split(".")[0]] for f in header["compare"]}
            except (KeyError, TypeError):
                continue
            case = {"id": f"run-{r['run_id']}", "provenance": f"grown by the loop: run {r['run_id']} ({name}) marked followed by the "
                                                             f"operator at {r['verdict_at']}: {r['verdict_reason']}",
                    "input": r["input"], "expected": expected}
            integrity.reasoning_guard(case, "golden growth")
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
         killed: dict[str, str] | None = None, ranking: dict | None = None, suspended: str | None = None,
         bands: dict[str, dict] | None = None, extra: dict | None = None) -> tuple[list[dict], dict]:
    """The planner's batch, under the pack's value ranking and each agent's reputation cap.  A planner suspended
    for poor foresight (engine.forecast) is replaced by the ranking itself.  Every plan is a ``<pack>.plan`` event.
    ``bands`` ({agent: curriculum band}) reach the planner as ``curriculum``; ``batch_resolves`` refuses an item
    outside its agent's band.  ``extra`` carries the crank analytics the planner is steered by: the binding
    constraint (and the share of the batch it must get while it binds), the golden inputs and novelty floor, the
    operator's directive."""
    engine, pack = runner.engine, runner.pack
    ranking = ranking or {"basis": "none", "entries": []}
    caps = reputation.agent_caps(engine, pack, max_runs)
    lh = engine.config.autoloop_long_horizon
    if suspended:
        batch, counts = [], {}
        for e in ranking["entries"]:
            if len(batch) < max_runs and counts.get(e["agent"], 0) < caps.get(e["agent"], max_runs):
                batch.append({"agent": e["agent"], "input": e["input"]})
                counts[e["agent"]] = counts.get(e["agent"], 0) + 1
        planned = {"run_id": None, "status": "suspended", "why": suspended, "forecasts": [], "skips": []}
    else:
        result = runner.run(planner, {"week": week, "max_runs": max_runs, "report": _slim_report(report),
                                      "pending": pending[:50], "golden": _golden_counts(pack),
                                      "killed": dict(killed or {}), "ranked": ranking["entries"], "caps": caps,
                                      "max_skip_without_reason": lh["plan"]["max_skip_without_reason"],
                                      "forecast_required": lh["taste"]["require_forecast"],
                                      "curriculum": dict(bands or {}), **(extra or {})})
        raw = list(result.output["batch"])[:max_runs] if result.status == "succeeded" else []
        batch = [{"agent": i["agent"], "input": i["input"], **({"synthetic": True} if i.get("synthetic") else {})} for i in raw]
        planned = {**result.as_dict(), "forecasts": raw, "skips": list(result.output.get("skips") or []) if result.status == "succeeded" else []}
    EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=planned["run_id"] or pack.name, event_type=f"{pack.name}.plan",
        payload=value.plan_record(planned["run_id"], ranking, batch, planned["skips"], planner_suspended=bool(suspended)),
        source=f"agent:{planner}" if planned["run_id"] else "pipeline:autoloop", source_ref=planned["run_id"])
    return batch, planned


# -- act ----------------------------------------------------------------------------------

def act(runner: Runner, batch: list[dict], *, budget_usd: Decimal | None = None, spent: Decimal = Decimal(0),
        planner_run_id: str | None = None) -> list[dict]:
    """Run the batch; with a budget, nothing new starts once the cycle's spend reaches it."""
    out = []
    for item in batch:
        if budget_usd is not None and spent >= budget_usd:
            out.append({"agent": item["agent"], "input": item["input"], "run_id": None, "status": "skipped_budget",
                        "error": f"the cycle's budget ${budget_usd} is spent (${spent})"})
            continue
        try:
            r = runner.run(item["agent"], item["input"])
            out.append({"agent": item["agent"], "input": item["input"], "run_id": r.run_id, "status": r.status,
                        "cost_usd": str(r.cost_usd)})
            spent += r.cost_usd
            if item.get("synthetic") and planner_run_id:      # a seeded synthetic input: recorded, never grown into golden
                runner.events.append(entity_type="agent_run", entity_id=r.run_id, event_type=f"{runner.pack.name}.synthetic_input",
                                     payload={"run_id": r.run_id, "agent": item["agent"], "planner_run_id": planner_run_id,
                                              "input": item["input"]}, source="pipeline:autoloop", source_ref=planner_run_id)
                out[-1]["synthetic"] = True
        except EngineError as e:                       # an errored run is traced by the runner; the loop goes on
            out.append({"agent": item["agent"], "input": item["input"], "run_id": None, "status": "error", "error": str(e)})
    return out


# -- judge --------------------------------------------------------------------------------

def unjudged(engine: Engine, pack, *, since: str, until: str) -> list[dict]:
    rows = engine.store.list_runs(pack=pack.name, since=since, until=until, verdicted=False)
    return [r for r in rows if r["role"] in JUDGEABLE_ROLES]


def judge(runner: Runner, judge_name: str, rows: list[dict]) -> list[dict]:
    """Each run adjudicated by the judge, or by the panel when the pack has one (engine.integrity.adjudicate)."""
    return [integrity.adjudicate(runner, judge_name, row) for row in rows]


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


def refine(engine: Engine, pack, runner: Runner, refiner: str, report: dict, *, packs_root: Path,
           directive: str | None = None) -> dict:
    rec = report.get("recommendation") or {}
    rungs = engine.config.autoloop_refine_rungs
    if rec.get("rung") not in rungs:
        return {"status": "skipped", "why": f"recommendation rung {rec.get('rung')!r} is not in {list(rungs)}"}
    target = _target_cluster(engine, pack, report)
    if target is None:
        return {"status": "skipped", "why": "no failure cluster names a worker, specialist or orchestrator run to refine"}
    agent, cluster = target
    min_runs = engine.config.autoloop["refine_min_cluster_runs"]
    if len(set(cluster.get("runs") or [])) < min_runs:
        return {"status": "skipped", "agent": agent, "why": f"the target cluster was seen in {len(set(cluster.get('runs') or []))} runs; "
                                                           f"a refinement needs at least {min_runs} (small noisy evidence does not drive an edit)"}
    held = governance.refine_hold(engine, pack, agent)                  # JH-C11 wpD: leash, policy, red flags, eval-live, proxy
    if held:
        return {"status": held["status"], "agent": agent, "why": held["why"]}
    objective = rigor.objective_hash(pack, runner.agent(agent))
    mismatch = rigor.objective_mismatch(engine, pack, agent, objective)
    if mismatch:
        return {"status": "skipped", "agent": agent, "why": mismatch}
    gate = integrity.intervention_gate(engine, pack, cluster)
    if gate["refused"]:
        return {"status": "monitor_cap", "agent": agent, "why": f"the evidence cites monitor-flagged runs {gate['runs']}; "
                f"{gate['count']} reasoning-motivated interventions this window, the cap is {gate['cap']}"}
    files = _text_files(pack.agent_dir(agent))
    change = rec["change"] if cluster is rec.get("evidence") else f"{rec['change']} Cluster: {cluster.get('cluster')} ({cluster.get('count')}x)."
    steer = {"constraint": rec["constraint"]} if rec.get("constraint") else {}
    if directive:
        steer["directive"] = directive
    r = runner.run(refiner, {"agent": agent, "rung": rec["rung"], "rungs": list(rungs), "change": change,
                             "evidence": integrity.reasoning_guard(_evidence(engine, cluster), "refiner evidence"), "files": files, "week": report["week"], **steer,
                             "forecast_required": engine.config.autoloop_long_horizon["taste"]["require_forecast"]})
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
    refusals = rigor.adoption_refusals(before, after, before_h, after_h)
    refusals += governance.adoption_refusals(engine, pack, agent, before, after)   # JH-C11 G-M14: sim-to-real gap
    adopted = adopted and not refusals
    if adopted:
        (pack.agent_dir(agent) / out["file"]).write_text(new_text, encoding="utf-8", newline="\n")
    event = EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=r.run_id, event_type=f"{pack.name}.refinement",
        payload={"agent": agent, "rung": int(out["rung"]), "file": out["file"], "old_sha256": _sha(files[out["file"]]),
                 "new_sha256": _sha(new_text), "before_score": before["models"][0]["score"],
                 "after_score": after["models"][0]["score"], "adopted": adopted,
                 "refiner_run_id": r.run_id, "why": str(out["why"])[:1000],
                 "before_holdout": None if before_h is None else before_h["models"][0]["score"],
                 "after_holdout": None if after_h is None else after_h["models"][0]["score"],
                 "objective_hash": before["objective_hash"], "samples": before["samples"],
                 "before_pass_at_k": before["models"][0]["pass_at_k"], "after_pass_at_k": after["models"][0]["pass_at_k"],
                 "before_interval": before["models"][0]["interval"], "after_interval": after["models"][0]["interval"],
                 "before_strata": before["models"][0]["strata"], "after_strata": after["models"][0]["strata"],
                 "refusals": refusals, "directive_sha256": _sha(directive) if directive else None,
                 "addresses_directive": out.get("addresses_directive") if directive else None},
        source=f"agent:{refiner}", source_ref=r.run_id)
    if gate["motivated"]:
        integrity.record_intervention(engine, pack, gate, agent, event["event_id"])
    scored = None
    if isinstance(out.get("forecast"), dict):
        scored = forecast.score_refinement(engine, pack, refiner, r.run_id, agent, out["forecast"], adopted=adopted,
                                           golden_delta=_score_delta(before, after), holdout_delta=_score_delta(before_h, after_h))
    return {"forecast": scored, "tiers": {"before": curator_step.tier_scores(pack, agent, before),
                                          "after": curator_step.tier_scores(pack, agent, after)},
            "status": "adopted" if adopted else "rejected", "agent": agent, "file": out["file"], "rung": out["rung"],
            "before": before["summary"], "after": after["summary"],
            "before_holdout": None if before_h is None else before_h["summary"],
            "after_holdout": None if after_h is None else after_h["summary"],
            "holdout": "held-out set evaluated" if use_holdout else "no eval/holdout.jsonl for this agent: adoption rests on the golden set alone",
            "refiner_run_id": r.run_id, "event_id": event["event_id"], "why": out["why"], "refusals": refusals}


def _score_delta(before: dict | None, after: dict | None) -> float | None:
    if before is None or after is None:
        return None
    return float(Decimal(after["models"][0]["score"]) - Decimal(before["models"][0]["score"]))


def adopt_decision(before: dict, after: dict, before_holdout: dict | None, after_holdout: dict | None) -> bool:
    """Adopt only if the golden score did not fall and still passes, AND (when a held-out set exists) the
    held-out score did not fall and still passes.  The held-out set is the benchmark the loop never tunes on."""
    b, a = Decimal(before["models"][0]["score"]), Decimal(after["models"][0]["score"])
    ok = bool(after["pass"] and a >= b)
    if before_holdout is not None and after_holdout is not None:
        bh, ah = Decimal(before_holdout["models"][0]["score"]), Decimal(after_holdout["models"][0]["score"])
        ok = ok and bool(after_holdout["pass"] and ah >= bh)
    return ok and not rigor.adoption_refusals(before, after, before_holdout, after_holdout)


def read_directive(engine: Engine, pack) -> str | None:
    """The operator's directive file (``autoloop.directive_file`` in the pack root), verbatim, or None."""
    p = pack.root / engine.config.analytics["directive_file"]
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8")
    return text if text.strip() else None


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
          do_curate: bool | None = None, runner: Runner | None = None, directive: str | None = None) -> dict:
    """``do_curate`` defaults to ``do_refine``: both write the pack's files (an adopted edit, an admitted case)."""
    from engine.sizing import require_budget
    budget = engine.config.autoloop_budget_usd
    require_budget(pack, budget, "an autoloop cycle")
    began = engine.clock.now()
    runner = runner or Runner(engine, pack)
    do_curate = do_refine if do_curate is None else do_curate
    directive = directive if directive is not None else read_directive(engine, pack)
    agents = loop_agents(pack)
    start, end = week_bounds(week)
    since, until = iso(start), iso(end)
    cap = max_runs or engine.config.autoloop_max_runs
    result: dict = {"pack": pack.name, "week": week, "loop_agents": agents}
    if engine.config.outcomes["enabled"] and engine.config.outcomes["resolve_each_cycle"]:
        result["outcomes"] = outcome.resolve_due(engine, pack)
    result["forecasts"] = {"resolved": forecast.resolve_due(engine, pack)}
    killed = kill_rule(engine, pack)
    probation = reputation.probation(runner, killed, lambda a: a in kill_rule(engine, pack)) if killed else []
    if probation:
        killed = kill_rule(engine, pack)
    safety = judge_safety(engine, pack)
    drift = drift_readings(engine, pack)
    result["safety"] = {"killed": killed, "judge": safety, "drift": drift, "probation": probation}
    shifted = [d for d in drift if d["shifted"]]
    judgeable = [n for n in sorted(pack.agent_names) if load_yaml(pack.agent_dir(n) / "manifest.yaml").get("role") in JUDGEABLE_ROLES]
    result["curriculum"] = curriculum.audit(engine, pack, judgeable)
    taste = forecast.role_scores(engine, pack)
    result["taste"] = taste
    guard = integrity.safeguards(engine, pack, "autoloop")
    result["safety"]["review"] = guard["review"]
    if guard["review"]["over"]:
        integrity.review_gate(engine, pack, "autoloop")
        result["plan_paused"] = (f"{guard['review']['backlog']} sampled agent verdicts wait for a human (cap "
                                 f"{guard['review']['max_backlog']}): no new work is planned until the operator reviews them")
    gov = governance.before_plan(engine, pack)                           # JH-C11 wpD: the leash and stale policy hold the plan
    result["governance"] = {"plan": {k: gov[k] for k in ("hold", "status")}, "leash": gov["leash"], "policy": gov["policy"]["policies"]}
    report = build_report(engine, pack, week)
    if do_plan and "planner" in agents and not guard["review"]["over"] and not gov["hold"]:
        pending = [_run_summary(r) for r in unjudged(engine, pack, since=since, until=until)]
        t = taste["planner"]
        batch, planned = plan(runner, agents["planner"], week=week, report=report, pending=pending, max_runs=cap, killed=killed,
                              ranking=value.ranked(engine, pack, killed=killed),
                              bands={a: v["band"] for a, v in result["curriculum"].items()},
                              suspended=(f"planner suspended: mean Brier {t['brier']} over {t['scored']} forecasts above {t['max_brier']}; "
                                         f"the engine planned by value") if t["suspended"] else None,
                              extra={**planner_input(report["constraint"], killed), "novelty": novelty_for_planner(engine, pack, report),
                                     **({"directive": directive} if directive else {})})
        result["plan"] = {"run": planned, "batch": batch}
        result["act"] = act(runner, batch, budget_usd=budget, spent=Decimal(str(planned.get("cost_usd") or 0)),
                             planner_run_id=planned["run_id"])   # a suspended planner spent nothing
        if planned["run_id"]:
            result["plan"]["scored"] = forecast.score_plan(engine, pack, agents["planner"], planned["run_id"], planned["forecasts"], result["act"])
        result["traps"] = integrity.plant_traps(runner, week, killed)
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
                rows = engine.store.list_runs(pack=pack.name, since=since, until=until, status="succeeded")
                result["honeypots"] = [h for j in integrity.panel_members(engine, pack, agents["judge"])
                                       for h in plant_honeypots(runner, j, rows, k)]
    result["monitor"] = integrity.monitor_step(runner, since=since, until=until)
    result["cheat_rate"] = integrity.cheat_rate(engine, pack, week, result.get("honeypots") or [], result.get("traps") or [])
    result["blame"] = blame_week(engine, pack, week)
    report = build_report(engine, pack, week)
    result["crank"] = _slim_report(report)
    result["constraint"] = {k: report["constraint"][k] for k in ("top", "next", "window_top", "previous_top", "moved", "binding_agent")}
    change = governance.before_change(engine, pack)                      # JH-C11 wpD: leash, stale policy, red flags
    result["governance"].update(change={k: change[k] for k in ("hold", "status")}, red_flags=change["red_flags"]["flags"])
    if shifted:
        why = "; ".join(f"{d['id']}: {d['why']}" for d in shifted)
        result["refine"] = {"status": "skipped", "why": f"drift: {why}; golden and held-out sets must be re-counted against the new record before any edit is adopted"}
        result["grow"] = []
        result["drift_hold"] = why
    elif change["hold"]:
        result["refine"] = {"status": change["status"], "why": change["hold"]}
        result["grow"] = []
    else:
        if do_refine:                                    # the judge's learning is its refinement: --no-refine skips both
            result["judge_learning"] = integrity.judge_learning(engine, pack, runner, agents, packs_root=packs_root,
                                                                refine=not (result["cheat_rate"] or {}).get("halt"))
        if do_refine and "refiner" in agents and (result["cheat_rate"] or {}).get("halt"):
            c = result["cheat_rate"]
            result["refine"] = {"status": "skipped", "why": f"cheat rate rose from {c['previous']} to {c['rate']} (above "
                                f"{c['max_cheat_rate']}): no edit is adopted while the class of cheat is not going down"}
        elif do_refine and "refiner" in agents:
            t = taste["refiner"]
            result["refine"] = ({"status": "skipped", "why": f"refiner suspended: mean Brier {t['brier']} over {t['scored']} forecasts "
                                                              f"above {t['max_brier']}; an edit needs a human until its foresight recovers"}
                                if t["suspended"] else refine(engine, pack, runner, agents["refiner"], report, packs_root=packs_root,
                                                directive=directive))
        if do_curate and "curator" in agents and engine.config.autoloop_long_horizon["curate"]["enabled"]:
            target = curator_step.target_agent(pack, (result.get("refine") or {}).get("agent"))
            if target is not None:
                result["curate"] = curator_step.curate(engine, pack, runner, agents["curator"], target)
        if engine.config.autoloop["grow_golden"]:
            result["grow"] = grow_golden(engine, pack, since=since, until=until)
        if engine.config.integrity["loop"]["grow_from_corrections"]:
            result["regressions"] = integrity.grow_regressions(engine, pack, since=since, until=until)
    if do_export:
        result["export"] = export_open(engine, pack, pack.root, week)
    result["safety"]["killed_after"] = kill_rule(engine, pack)
    result["governance"]["after"] = governance.after_cycle(engine, pack, week, result)
    result["reputation"] = reputation.update(engine, pack, week, killed=result["safety"]["killed_after"],
                                             judge_agent=agents.get("judge"), judge_suspended=safety["suspended"])
    result["cycle_seconds"] = round((engine.clock.now() - began).total_seconds(), 6)
    result["integrity"] = {"collusion": integrity.record_collusion(engine, pack), "delegation": integrity.record_delegations(engine, pack),
                           "monitorability": integrity.monitorability(engine, pack, week, since=since, until=until),
                           "review_sla": integrity.review_sla(engine, pack)}
    spent = engine.store.list_runs(pack=pack.name, since=iso(began))
    result["directive_sha256"] = _sha(directive) if directive else None
    result["analytics_events"] = record_cycle(engine, pack, week, report, started=began, cycle_runs=len(spent),
                                              cycle_cost=sum((Decimal(str(r["cost_usd"])) for r in spent), Decimal(0)))
    return result


def render(result: dict) -> str:
    L = [f"# Autoloop — {result['pack']} — {result['week']}", "",
         f"loop agents: {result['loop_agents']}", ""]
    L += _render_governance(result.get("governance"))
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
        for a, c in sorted((result.get("curriculum") or {}).items()):
            b, sat = c["band"], c["saturation"]
            L += [f"- curriculum {a}: promoted tier {b['promoted_tier']}" + (f" (promoted to {c['promoted']} this cycle)" if c["promoted"] else "")
                  + f", frontier {b['frontier_tier']}, mastered {b['mastered_tier']}" + (f", rung gaps {b['gaps']}" if b["gaps"] else "")
                  + f"; golden saturated {sat['share']}" + (" -- SATURATED: harder cases wanted" if sat["flagged"] else "")]
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
    if result.get("constraint"):
        k = result["constraint"]
        L += [f"constraint: {(k['top'] or {}).get('id')} (next {(k['next'] or {}).get('id')}; previous {k['previous_top']}"
              + ("; MOVED" if k["moved"] else "") + ")" + (f"; the planner's batch is weighted to {k['binding_agent']}" if k["binding_agent"] else "")]
    if result.get("blame"):
        L += ["blame: " + ", ".join(f"{b['run_id']} {b['origin']} ({b['item'][:80]})" for b in result["blame"])]
    if "refine" in result:
        r = result["refine"]
        L += ["", "## Refine", "", f"{r['status']}" + (f": {r['agent']} {r['file']} rung {r['rung']}; golden before {r['before']} after {r['after']}; held-out before {r.get('before_holdout')} after {r.get('after_holdout')} ({r.get('holdout')}); event {r['event_id']}" if r["status"] in ("adopted", "rejected") else f": {r.get('why') or r.get('failure_reasons')}")]
        if r.get("why") and r["status"] in ("adopted", "rejected"):
            L += ["", f"> {r['why']}"]
        L += [f"- refused: {why}" for why in r.get("refusals") or []]
        if r["status"] == "declined":
            L += ["", f"The refiner (run {r['refiner_run_id']}) found no edit the evidence warrants; nothing changed and no golden evaluation was spent."]
    if "grow" in result:
        L += ["", "## Golden growth (operator-followed runs only)", ""]
        L += [f"- {g['agent']}: +{g['added']} cases ({', '.join(g['ids'][:5])}{'…' if g['added'] > 5 else ''})" for g in result["grow"]] or ["- nothing to add"]
    if "export" in result:
        L += ["", "## Export", ""] + [f"- {e['agent']}: {e['status']}" + (f" ({e['rows']} rows -> {e['path']})" if e["status"] == "exported" else f" ({e['why']})") for e in result["export"]]
    L += _render_long_horizon(result)
    if result.get("cycle_seconds") is not None:
        L += ["", f"cycle time: {result['cycle_seconds']} s from the first gate to the last step"]
    if "integrity" in result:
        L += ["", "## Integrity", ""]
        if result.get("plan_paused"):
            L += [f"- review backlog: {result['plan_paused']}"]
        L += ["- traps: " + (", ".join(f"{t['agent']} " + (("READ (disclosed)" if t["disclosed"] else "READ (concealed)") if t.get("read") else "not read")
                                       for t in result.get("traps") or []) or "none planted")]
        c = result.get("cheat_rate")
        L += ["- cheat rate: " + (f"{c['rate']} (previous {c['previous']})" + ("; refinement halted" if c["halt"] else "") if c else "nothing planted")]
        L += [f"- monitor: {len(result.get('monitor') or [])} runs read, "
              f"{sum(1 for m in result.get('monitor') or [] if m.get('flag') not in (None, 'none'))} flagged"]
        L += ["- regression cases grown: " + (", ".join(f"{g['agent']} +{g['added']}" for g in result.get("regressions") or []) or "none")]
        L += [f"- judge {j['judge']}: score on its own misses {j['score']} over {j['cases']} cases"
              + (f"; edit {j['refine']['status']}" if j.get("refine") else "") for j in result.get("judge_learning") or []]
        L += [f"- delegation {d['agent']}: {d['decision']} (operator ${d['operator_cost']}/review, agent ${d['agent_cost']}/item, "
              f"agreement {d['agreement']})" for d in result["integrity"]["delegation"]]
    L += ["", "Every step above is a traced run or a ledger-bound event; a human verdict recorded later outranks any agent verdict here."]
    return "\n".join(L) + "\n"


def _render_governance(gov: dict | None) -> list[str]:
    """JH-C11 wpD at the head of the report: red flags, the leash, stale policies, holds, open incidents."""
    if not gov:
        return []
    L = governance.render_top({"red_flags": gov.get("red_flags") or [], "leash": gov.get("leash"), "policies": gov.get("policy") or [],
                               "open_incidents": (gov.get("after") or {}).get("open_incidents") or []})
    return L + [f"- {step} HELD ({gov[step]['status']}): {gov[step]['hold']}" for step in ("plan", "change")
                if (gov.get(step) or {}).get("hold")] + [""]


def _render_long_horizon(result: dict) -> list[str]:
    """Outcomes resolved, probation, the plan's ranking, the loop roles' scored taste, the curator, and reputation."""
    L = ["", "## The long record", ""]
    o = result.get("outcomes")
    if o is not None:
        L += [f"- outcomes: {len(o['resolved'])} resolved ({sum(r['hit'] for r in o['resolved'])} hit), "
              f"{len(o['awaiting'])} due and awaiting the world, {o['not_due']} not yet due"]
    f = result.get("forecasts") or {}
    L += [f"- dated forecasts resolved this cycle: " + (", ".join(f"{r['made_by']} {r['metric']} {r['target']} by {r['due']} -> "
                                                                   f"{r['actual']} {'HIT' if r['hit'] else 'MISS'}" for r in f.get("resolved") or []) or "none")]
    for p in (result.get("safety") or {}).get("probation") or []:
        L += [f"- probation: {p['agent']} ran {len(p['runs'])} golden inputs, {p['passed']} passed; " + ("halt LIFTED" if p["lifted"] else "still halted")]
    for role, t in (result.get("taste") or {}).items():
        L += [f"- {role} foresight: {t['scored']} scored, mean Brier {t['brier']}: " + ("SUSPENDED" if t["suspended"] else "trusted")]
    if "plan" in result:
        run = result["plan"]["run"]
        L += [f"- plan: {'the engine planned by value (' + run['why'] + ')' if run['status'] == 'suspended' else 'planner run ' + str(run['run_id'])}; "
              f"skips with reasons: {len(run.get('skips') or [])}"]
    r = result.get("refine") or {}
    if r.get("forecast"):
        L += [f"- refiner forecast: Brier {r['forecast']['brier']}, golden delta error {r['forecast']['golden_delta_abs_error']}"
              + ("; dated target recorded" if r["forecast"].get("target_event_id") else "")]
    if r.get("tiers"):
        L += [f"- golden score per tier: before {r['tiers']['before']} after {r['tiers']['after']}"]
    c = result.get("curate")
    if c:
        L += [f"- curator ({c.get('agent')}): {c['status']}" + (f"; {len(c['cases'])} proposed, admitted {c['admitted'] or 'none'}, "
                                                                f"awaiting the operator {c['queued'] or 'none'}" if c["status"] == "curated" else "")]
    for rep in result.get("reputation") or []:
        L += [f"- reputation {rep['agent']}: {rep['previous_tier']} -> {rep['tier']} (score {rep['score']}; {rep['why']})"]
    return L


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.autoloop")
    p.add_argument("pack")
    p.add_argument("--week", required=True)
    p.add_argument("--max-runs", type=int)
    p.add_argument("--no-plan", action="store_true")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--no-refine", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--no-curate", action="store_true")
    p.add_argument("--directive", help="a file whose text is the operator's directive this cycle (default: the pack's directive file)")
    p.add_argument("--db")
    p.add_argument("--out", help="directory (default packs/<pack>/crank)")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            from engine.schedule import store_lease
            pack = load_pack(args.pack)
            with store_lease(engine, "engine.autoloop", packs=[pack]):
                result = cycle(engine, pack, args.week, packs_root=pack.root.parent, max_runs=args.max_runs,
                               do_plan=not args.no_plan, do_judge=not args.no_judge, do_refine=not args.no_refine,
                               do_export=not args.no_export, do_curate=not (args.no_curate or args.no_refine),
                               directive=Path(args.directive).read_text(encoding="utf-8") if args.directive else None)
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
