"""Crank analytics: what the weekly report measures beyond pass rates and failure clusters (JH-C11 wpF).

Every function here reads the store (runs, events) and the pack's files and returns plain data; none
writes.  ``extend_report`` adds the sections to ``crank.build_report``; ``render_sections`` renders them;
``record_cycle`` (called by ``engine.autoloop.cycle``) writes the per-cycle events the sections imply.

  yield         outcomes, not volume: followed runs per dollar, cost per followed run, items on followed
                runs only, and the operator's touches per hundred runs with its trend (Naval)
  autonomy      share of verdicts, planned runs, refinements and golden cases made by the loop's agents
                versus the operator, week over week (Patel)
  learning      each agent's score per adopted iteration against cumulative runs; a repetition index
                that flags a window adding runs without iterations (Naval)
  iteration     what extra iterations and candidates buy: success by iteration index and tool-call count,
  yield         cost spent after the first iteration, and a loop-setting recommendation (the panel)
  diversity     distinct output values per distinct input, repeated n-grams in free text, and the
                judge's followed share against the operator's spot checks (the panel)
  audit sample  raw runs per worker/specialist chosen by a seeded hash of (week, run_id), never by an
                agent, shown without any summary (Musk's skip-level review)
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from engine.config import load_yaml
from engine.errors import EngineError
from engine.eval import load_golden
from engine.guardrails import JUDGEABLE_ROLES
from engine.runtime import parse_iso

JUDGEABLE = JUDGEABLE_ROLES
SAMPLED_ROLES = ("worker", "specialist")
_SKIP_FIELDS = ("citations", "confidence")
_WS = re.compile(r"\s")


# -- shared helpers -----------------------------------------------------------------------------

def week_of(ts: str) -> str:
    y, w, _ = parse_iso(ts).isocalendar()
    return f"{y}-W{w:02d}"


def shift_week(week: str, n: int) -> str:
    from engine.crank import week_bounds
    from datetime import timedelta
    start, _ = week_bounds(week)
    y, w, _ = (start + timedelta(weeks=n)).isocalendar()
    return f"{y}-W{w:02d}"


def week_runs(engine, pack, week: str, **kw) -> list[dict]:
    from engine.crank import week_bounds
    from engine.runtime import iso
    start, end = week_bounds(week)
    return engine.store.list_runs(pack=pack.name, since=iso(start), until=iso(end), **kw)


def week_events(engine, pack, suffix: str, week: str | None = None) -> list[dict]:
    from engine.crank import week_bounds
    from engine.runtime import iso
    kw = {}
    if week is not None:
        start, end = week_bounds(week)
        kw = {"since": iso(start), "until": iso(end)}
    return engine.store.query_events(event_type=f"{pack.name}.{suffix}", limit=100000, ascending=True, **kw)


def run_context(row: dict) -> dict | None:
    """The working context the run's first candidate was handed (the first user message of its trace)."""
    for it in row.get("iterations") or []:
        for cand in it.get("candidates") or []:
            msgs = cand.get("messages") or []
            if not msgs:
                continue
            try:
                return json.loads(msgs[0]["content"][0]["text"])["context"]
            except (KeyError, IndexError, TypeError, ValueError):
                return None
    return None


def accepted_candidate(row: dict) -> tuple[int, dict] | None:
    for it in row.get("iterations") or []:
        for cand in it.get("candidates") or []:
            if cand.get("accepted"):
                return int(it["index"]), cand
    return None


def role_of(pack, agent: str) -> str | None:
    try:
        return load_yaml(pack.agent_dir(agent) / "manifest.yaml").get("role")
    except EngineError:
        return None


def golden_cases(pack, agent: str, file: str = "golden.jsonl") -> tuple:
    """The agent's cases in an eval file; none when the file is absent or holds no case yet."""
    path = pack.agent_dir(agent) / "eval" / file
    if not path.is_file():
        return ()
    try:
        return load_golden(path, pack_is_fixture=pack.fixture).cases
    except EngineError:
        return ()


def golden_inputs(pack, agent: str, file: str = "golden.jsonl") -> list[dict]:
    return [c.input for c in golden_cases(pack, agent, file)]


def _q(d: Decimal, places: str) -> str:
    return str(d.quantize(Decimal(places)))


def _baseline(engine, pack, agent: str) -> int | None:
    from engine.manifest import load_agent
    try:
        return load_agent(pack, agent, config=engine.config, enforce_economics=False).manual_baseline_items
    except EngineError:
        return None


# -- yield (G-NAB6) -------------------------------------------------------------------------------

def _touch_rate(rows: list[dict]) -> str | None:
    if not rows:
        return None
    human = sum(1 for r in rows if r.get("verdict_source") == "human" and r["human_verdict"])
    return _q(Decimal(human * 100) / len(rows), "0.01")


def outcome_yield(engine, pack, week: str, runs: list[dict], trend_weeks: int = 4) -> list[dict]:
    """Per agent: what the spend bought in outcomes the operator or the judge marked followed."""
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_agent[r["agent"]].append(r)
    out = []
    for name in sorted(by_agent):
        rows = by_agent[name]
        cost = sum((Decimal(str(r["cost_usd"])) for r in rows), Decimal(0))
        followed = [r for r in rows if r["human_verdict"] == "followed"]
        items = sum(int(r["items_evaluated"] or 0) for r in followed)
        baseline = _baseline(engine, pack, name)
        humans = sum(1 for r in rows if r.get("verdict_source") == "human" and r["human_verdict"])
        trend = []
        for k in range(trend_weeks - 1, -1, -1):
            w = shift_week(week, -k)
            trend.append({"week": w, "human_verdicts_per_100_runs": _touch_rate(rows if k == 0 else week_runs(engine, pack, w, agent=name))})
        out.append({
            "agent": name, "runs": len(rows), "followed": len(followed),
            "followed_per_usd": None if cost == 0 else _q(Decimal(len(followed)) / cost, "0.01"),
            "cost_per_followed": None if not followed else _q(cost / len(followed), "0.00000001"),
            "followed_items": items,
            "followed_scale_ratio": None if not baseline else _q(Decimal(items) / baseline, "0.01"),
            "human_verdicts_per_100_runs": _touch_rate(rows),
            "human_verdicts_per_followed": None if not followed else _q(Decimal(humans) / len(followed), "0.01"),
            "touch_trend": trend,
        })
    return out


# -- autonomy (G-D2) --------------------------------------------------------------------------------

def _share(agent_n: int, human_n: int) -> dict:
    total = agent_n + human_n
    return {"agent": agent_n, "human": human_n, "agent_share": None if not total else round(agent_n / total, 4)}


def _autonomy_week(engine, pack, week: str) -> dict:
    verdicts = week_events(engine, pack, "verdict", week)
    v_agent = sum(1 for e in verdicts if e["source"].startswith("agent:"))
    refinements = week_events(engine, pack, "refinement", week)
    r_agent = sum(1 for e in refinements if e["source"].startswith("agent:"))
    runs = week_runs(engine, pack, week)
    planned: list[tuple[str, str, str]] = []
    for r in runs:
        if r["role"] == "planner" and r["status"] == "succeeded":
            for item in (r["output"] or {}).get("batch") or []:
                planned.append((r["created_at"], item["agent"], json.dumps(item["input"], sort_keys=True)))
    p_agent = p_human = 0
    for r in runs:
        if r["role"] not in JUDGEABLE or r["parent_run_id"]:
            continue
        key = json.dumps(r["input"], sort_keys=True)
        if any(at <= r["created_at"] and a == r["agent"] and k == key for at, a, k in planned):
            p_agent += 1
        else:
            p_human += 1
    return {"verdicts": _share(v_agent, len(verdicts) - v_agent), "planned_runs": _share(p_agent, p_human),
            "refinements": _share(r_agent, len(refinements) - r_agent)}


def autonomy(engine, pack, week: str) -> dict:
    """Who did the work this week, the loop's agents or the operator, and how that moved since last week."""
    now, prev = _autonomy_week(engine, pack, week), _autonomy_week(engine, pack, shift_week(week, -1))
    g_loop = g_human = 0
    for name in sorted(pack.agent_names):
        for c in golden_cases(pack, name):
            if (c.provenance or "").startswith("grown by the loop"):
                g_loop += 1
            else:
                g_human += 1
    trend = {}
    for k in now:
        a, b = now[k]["agent_share"], prev[k]["agent_share"]
        trend[k] = None if a is None or b is None else round(a - b, 4)
    return {**now, "golden_cases": _share(g_loop, g_human), "previous_week": prev, "trend": trend}


# -- learning curve and repetition (G-NAB5) ------------------------------------------------------

def learning_curve(engine, pack) -> dict[str, list[dict]]:
    """Per agent, the golden and held-out score after every adopted iteration, against cumulative runs."""
    out: dict[str, list[dict]] = {}
    for e in week_events(engine, pack, "refinement"):
        p = e["payload"]
        if not p["adopted"]:
            continue
        curve = out.setdefault(p["agent"], [])
        if not curve:
            curve.append({"iteration": 0, "week": week_of(e["observed_at"]), "golden": p["before_score"],
                          "holdout": p.get("before_holdout"), "cumulative_runs": None})
        n = len(engine.store.list_runs(pack=pack.name, agent=p["agent"], until=e["observed_at"]))
        curve.append({"iteration": len(curve), "week": week_of(e["observed_at"]), "golden": p["after_score"],
                      "holdout": p.get("after_holdout"), "cumulative_runs": n})
    return out


def repetition(engine, pack, week: str, runs: list[dict]) -> list[dict]:
    """Distinct inputs per run for each agent; a window below the floor with no adopted iteration repeats itself."""
    cfg = engine.config.analytics
    adopted = Counter(e["payload"]["agent"] for e in week_events(engine, pack, "refinement", week) if e["payload"]["adopted"])
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["role"] in JUDGEABLE:
            by_agent[r["agent"]].append(r)
    out = []
    for name in sorted(by_agent):
        rows = by_agent[name]
        distinct = len({r["input_hash"] for r in rows})
        index = round(distinct / len(rows), 4)
        out.append({"agent": name, "runs": len(rows), "distinct_inputs": distinct, "repetition_index": index,
                    "adopted_iterations": adopted[name],
                    "repeating": len(rows) >= cfg["repetition_min_runs"] and index < cfg["repetition_floor"] and adopted[name] == 0})
    return out


def novelty_for_planner(engine, pack, report: dict) -> dict:
    """What the planner is handed about novelty: every agent's golden inputs, and the floor when the window repeats."""
    out: dict = {"golden_inputs": {n: golden_inputs(pack, n) for n in sorted(pack.agent_names) if role_of(pack, n) in JUDGEABLE}}
    repeating = [r["agent"] for r in report.get("repetition") or [] if r["repeating"]]
    if repeating:
        out["min_novel_share"] = engine.config.analytics["min_novel_share"]
        out["repeating"] = repeating
    return out


# -- iteration and horizon yield (G-P17) ------------------------------------------------------

def iteration_yield(engine, pack, runs: list[dict]) -> list[dict]:
    from engine.manifest import load_agent
    min_runs = engine.config.analytics["yield_min_runs"]
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["role"] in JUDGEABLE:
            by_agent[r["agent"]].append(r)
    out = []
    for name in sorted(by_agent):
        rows = by_agent[name]
        reached: Counter = Counter()
        success_at: Counter = Counter()
        success_cand: Counter = Counter()
        by_tools: Counter = Counter()
        steps, late_cost = [], Decimal(0)
        exhausted = 0
        for r in rows:
            its = [it for it in r["iterations"] if it.get("candidates")]
            for it in its:
                reached[int(it["index"])] += 1
                if int(it["index"]) >= 2:
                    late_cost += sum((Decimal(str(pc["cost_usd"])) for c in it["candidates"] for pc in c.get("provider_calls") or []), Decimal(0))
            acc = accepted_candidate(r) if r["status"] == "succeeded" else None
            if acc:
                i, cand = acc
                success_at[i] += 1
                success_cand[int(cand["index"])] += 1
                steps.append(i)
                n = len(cand.get("tool_calls") or [])
                by_tools["0" if n == 0 else "1-3" if n <= 3 else "4-10" if n <= 10 else ">10"] += 1
            elif its:
                exhausted += 1
        try:
            loop = load_agent(pack, name, config=engine.config, enforce_economics=False).loop
        except EngineError:
            continue
        max_it, width = int(loop["max_iterations"]), int(loop["search_width"])
        rec = None
        if len(rows) >= min_runs and success_at:
            top = max(success_at)
            if top < max_it and any(reached[i] for i in range(top + 1, max_it + 1)):
                rec = {"rung": 2, "knob": "max_iterations", "from": max_it, "to": top,
                       "change": f"Rung 2 (harness): {name} never succeeds after iteration {top} in {len(rows)} runs; "
                                 f"iterations {top + 1}..{max_it} cost ${_q(late_cost, '0.00000001')} and converted nothing. "
                                 f"Cut loop.max_iterations from {max_it} to {top}."}
            elif top == max_it and exhausted:
                rec = {"rung": 2, "knob": "max_iterations", "from": max_it, "to": max_it + 1,
                       "change": f"Rung 2 (harness): {name} still converts on its last iteration ({success_at[top]} runs) while "
                                 f"{exhausted} runs exhaust it. Raise loop.max_iterations from {max_it} to {max_it + 1}."}
            elif width > 1 and set(success_cand) == {0}:
                rec = {"rung": 2, "knob": "search_width", "from": width, "to": 1,
                       "change": f"Rung 2 (harness): every success of {name} came from candidate 0; cut loop.search_width from {width} to 1."}
        out.append({"agent": name, "runs": len(rows), "max_iterations": max_it, "search_width": width,
                    "reached_iteration": {str(k): v for k, v in sorted(reached.items())},
                    "success_by_iteration": {str(k): v for k, v in sorted(success_at.items())},
                    "success_by_candidate": {str(k): v for k, v in sorted(success_cand.items())},
                    "success_by_tool_calls": dict(sorted(by_tools.items())),
                    "median_steps_to_success": None if not steps else median(steps),
                    "cost_after_first_iteration": _q(late_cost, "0.00000001"),
                    "recommendation": rec})
    return out


# -- diversity / mode collapse (G-P7) ----------------------------------------------------------

def _leaves(obj, path: tuple = ()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _SKIP_FIELDS:
                continue
            yield from _leaves(v, path + (k,))
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaves(v, path + ("*",))
    else:
        yield ".".join(path), obj


def _trigrams(text: str) -> list[tuple]:
    words = text.split()
    return [tuple(words[i:i + 3]) for i in range(len(words) - 2)]


def output_diversity(rows: list[dict], cfg: dict) -> list[dict]:
    """Per output field: distinct per-run values over distinct inputs; for free-text fields also the share of
    word trigrams that repeat across outputs.  A free-text field below the distinct floor is a mode collapse."""
    rows = [r for r in rows if r["status"] == "succeeded" and isinstance(r["output"], (dict, list))]
    n_in = len({r["input_hash"] for r in rows})
    if not rows or n_in == 0:
        return []
    per_field: dict[str, list[str]] = defaultdict(list)
    texts: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        vals: dict[str, list] = defaultdict(list)
        for path, v in _leaves(r["output"]):
            vals[path].append(v)
        for path, vs in vals.items():
            per_field[path].append(json.dumps(vs, sort_keys=True))
            texts[path].extend(v for v in vs if isinstance(v, str) and _WS.search(v))
    out = []
    for path in sorted(per_field):
        ratio = round(min(1.0, len(set(per_field[path])) / n_in), 4)
        free = bool(texts[path])
        grams = [g for t in texts[path] for g in _trigrams(t)]
        repeat = None if not grams else round(1 - len(set(grams)) / len(grams), 4)
        collapse = free and n_in >= int(cfg["min_runs"]) and ratio < float(cfg["min_distinct_ratio"])
        out.append({"field": path, "distinct_ratio": ratio, "ngram_repeat": repeat, "free_text": free,
                    "mode_collapse": collapse})
    return out


def diversity(engine, pack, week: str, runs: list[dict]) -> list[dict]:
    cfg = engine.config.analytics["diversity"]
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["role"] in JUDGEABLE:
            by_agent[r["agent"]].append(r)
    verdicts = week_events(engine, pack, "verdict", week)
    judge_by_run: dict[str, str] = {}
    human_by_run: dict[str, str] = {}
    for e in verdicts:
        (judge_by_run if e["source"].startswith("agent:") else human_by_run)[e["payload"]["run_id"]] = e["payload"]["verdict"]
    out = []
    for name in sorted(by_agent):
        rows = by_agent[name]
        ids = {r["run_id"] for r in rows}
        judged = [v for rid, v in judge_by_run.items() if rid in ids]
        followed_share = None if not judged else round(judged.count("followed") / len(judged), 4)
        spot_disagree = sum(1 for rid, v in judge_by_run.items() if rid in ids and v == "followed"
                            and human_by_run.get(rid) in ("overridden", "wrong"))
        fields = output_diversity(rows, cfg)
        skew = (followed_share is not None and len(judged) >= int(cfg["min_runs"])
                and followed_share > float(cfg["max_judge_followed_share"]) and spot_disagree > 0)
        collapsed = [f["field"] for f in fields if f["mode_collapse"]]
        rec = None
        if collapsed or skew:
            what = (f"free-text field(s) {', '.join(collapsed)} repeat across distinct inputs" if collapsed else
                    f"the judge marks {followed_share:.0%} followed while the operator overrode {spot_disagree} of its followed runs")
            rec = {"rung": 2, "change": f"Rung 2 (harness): {name}: {what}. Vary the worked examples in skills.md and require "
                                        f"the output to state what is specific to its input."}
        out.append({"agent": name, "fields": fields, "judge_followed_share": followed_share, "judge_verdicts": len(judged),
                    "spot_check_disagreements": spot_disagree, "mode_collapse": collapsed, "verdict_skew": skew,
                    "recommendation": rec})
    return out


# -- skip-level audit sample (G-M10) ------------------------------------------------------------

def audit_seed(week: str) -> str:
    return hashlib.sha256(f"audit:{week}".encode()).hexdigest()[:16]


def audit_sample(engine, week: str, runs: list[dict]) -> dict:
    """``audit_sample_per_agent`` raw runs per worker/specialist, child runs included, chosen by the hash of
    (seed, run_id): deterministic for a week, different next week, and no agent chooses them."""
    k = engine.config.analytics["audit_sample_per_agent"]
    seed = audit_seed(week)
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["role"] in SAMPLED_ROLES:
            by_agent[r["agent"]].append(r)
    picks = []
    for name in sorted(by_agent):
        ranked = sorted(by_agent[name], key=lambda r: hashlib.sha256(f"{seed}:{r['run_id']}".encode()).hexdigest())
        for r in ranked[:k]:
            picks.append({"agent": name, "run_id": r["run_id"], "parent_run_id": r["parent_run_id"], "status": r["status"],
                          "input": r["input"], "output": r["output"], "failure_reasons": r["failure_reasons"][:10],
                          "verdict": r["human_verdict"], "verdict_source": r.get("verdict_source"),
                          "verdict_reason": r["verdict_reason"]})
    return {"week": week, "seed": seed, "per_agent": k, "runs": picks}


# -- the report hook -------------------------------------------------------------------------------

def extend_report(engine, pack, week: str, runs: list[dict], report: dict) -> None:
    """Add every wpF section to a crank report in place (crank.build_report calls this last)."""
    from engine import attribution, blame, constraint, coverage, freshness, velocity, vendors
    report["yield"] = outcome_yield(engine, pack, week, runs)
    report["autonomy"] = autonomy(engine, pack, week)
    report["learning_curve"] = learning_curve(engine, pack)
    report["repetition"] = repetition(engine, pack, week, runs)
    report["iteration_yield"] = iteration_yield(engine, pack, runs)
    report["diversity"] = diversity(engine, pack, week, runs)
    report["audit_sample"] = audit_sample(engine, week, runs)
    report["attribution"] = attribution.report(engine, pack, week, runs)
    report["blame"] = blame.report(engine, pack, week)
    report["coverage"] = coverage.report(engine, pack, runs)
    report["stale_grounding"] = freshness.report(engine, pack, week)
    report["vendor_record"] = vendors.scorecard(engine, pack, week)
    report["velocity"] = velocity.ledger(engine, pack, week)
    report["speed"] = velocity.speed(engine, pack, week)
    report["resources"] = constraint.resources(engine, pack, runs)
    report["constraint"] = constraint.identify(engine, pack, week, runs, report)
    constraint.steer_recommendation(report)
    _weigh_yield(report)


def _weigh_yield(report: dict) -> None:
    """The recommendation weighs outcomes: with no failure or override to fix, an agent that ran at volume
    without one followed outcome is the change; every recommendation carries the yield it was made against."""
    rec = report["recommendation"]
    rows = report["yield"]
    if rec.get("rung") is None:
        idle = [y for y in rows if y["followed"] == 0 and y["runs"] >= 5 and any(o["followed"] for o in rows)]
        if idle:
            y = max(idle, key=lambda y: y["runs"])
            report["recommendation"] = {"rung": 1, "change": f"Rung 1 (grounding): {y['agent']} ran {y['runs']} times this week and "
                                        f"no run was marked followed while other agents' were. Ground it on what its followed "
                                        f"peers cite, or stop scheduling it.", "evidence": {"yield": y}}
            rec = report["recommendation"]
    rec["yield"] = [{k: y[k] for k in ("agent", "followed", "followed_per_usd", "cost_per_followed")} for y in rows]


def _fmt(v) -> str:
    return "—" if v is None else str(v)


def render_sections(report: dict) -> list[str]:
    from engine import attribution, blame, constraint, coverage, freshness, velocity, vendors
    L: list[str] = []
    L += constraint.render(report)
    L += ["", "## Yield (followed outcomes, not volume)", "",
          "| agent | runs | followed | followed/USD | cost/followed | followed items | followed scale_ratio | human verdicts/100 runs | trend |",
          "|---|---|---|---|---|---|---|---|---|"]
    for y in report["yield"]:
        trend = " → ".join(_fmt(t["human_verdicts_per_100_runs"]) for t in y["touch_trend"])
        L.append(f"| {y['agent']} | {y['runs']} | {y['followed']} | {_fmt(y['followed_per_usd'])} | {_fmt(y['cost_per_followed'])} | "
                 f"{y['followed_items']} | {_fmt(y['followed_scale_ratio'])} | {_fmt(y['human_verdicts_per_100_runs'])} | {trend} |")
    a = report["autonomy"]
    L += ["", "## Autonomy (loop agents vs operator)", ""]
    for k in ("verdicts", "planned_runs", "refinements", "golden_cases"):
        s = a[k]
        L.append(f"- {k}: agent {s['agent']}, human {s['human']}, agent share {_fmt(s['agent_share'])}"
                 + (f" (week over week {a['trend'][k]:+})" if a["trend"].get(k) is not None else ""))
    L += ["", "## Learning curve and repetition", ""]
    for name, curve in sorted(report["learning_curve"].items()):
        L.append(f"- {name}: " + " → ".join(f"it{c['iteration']} golden {c['golden']} held-out {_fmt(c['holdout'])}"
                                             + (f" @ {c['cumulative_runs']} runs" if c["cumulative_runs"] is not None else "") for c in curve))
    for r in report["repetition"]:
        L.append(f"- {r['agent']}: repetition index {r['repetition_index']} ({r['distinct_inputs']} distinct of {r['runs']} runs, "
                 f"{r['adopted_iterations']} adopted iterations)" + (" — REPEATING: hours without iterations" if r["repeating"] else ""))
    L += ["", "## Iteration and horizon yield", ""]
    for y in report["iteration_yield"]:
        L.append(f"- {y['agent']}: {y['runs']} runs; success by iteration {y['success_by_iteration']} of reached "
                 f"{y['reached_iteration']}; by candidate {y['success_by_candidate']}; by tool calls {y['success_by_tool_calls']}; "
                 f"median steps {_fmt(y['median_steps_to_success'])}; cost after iteration 1 ${y['cost_after_first_iteration']}")
        if y["recommendation"]:
            L.append(f"  - {y['recommendation']['change']}")
    L += ["", "## Output diversity", ""]
    for d in report["diversity"]:
        flags = (["MODE COLLAPSE: " + ", ".join(d["mode_collapse"])] if d["mode_collapse"] else []) + (["VERDICT SKEW"] if d["verdict_skew"] else [])
        free = [f for f in d["fields"] if f["free_text"]]
        L.append(f"- {d['agent']}: judge followed share {_fmt(d['judge_followed_share'])} over {d['judge_verdicts']}; "
                 + "; ".join(f"{f['field']} distinct {f['distinct_ratio']} n-gram repeat {_fmt(f['ngram_repeat'])}" for f in free)
                 + (f" — {' / '.join(flags)}" if flags else ""))
    L += attribution.render(report)
    L += blame.render(report)
    L += coverage.render(report)
    L += freshness.render(report)
    L += vendors.render(report)
    L += velocity.render(report)
    s = report["audit_sample"]
    L += ["", f"## Skip-level audit sample (seed {s['seed']}, {s['per_agent']} per worker/specialist, raw)", ""]
    for p in s["runs"]:
        L.append(f"- {p['agent']} {p['run_id']}" + (f" (child of {p['parent_run_id']})" if p["parent_run_id"] else "")
                 + f" {p['status']}; verdict {_fmt(p['verdict'])} ({_fmt(p['verdict_source'])}): {_fmt(p['verdict_reason'])}")
        L.append(f"  - input `{json.dumps(p['input'], sort_keys=True)}`")
        L.append(f"  - output `{json.dumps(p['output'], sort_keys=True)[:600]}`")
        for f in p["failure_reasons"][:3]:
            L.append(f"  - failure: {f}")
    return L


# -- per-cycle events (called by engine.autoloop.cycle) -----------------------------------------

def record_cycle(engine, pack, week: str, report: dict, *, started, cycle_cost: Decimal, cycle_runs: int) -> dict:
    """Write the cycle's analytic events: the constraint, velocity per agent, the audit sample, coverage gaps,
    mode collapses, and the cycle's own wall time and cost."""
    from engine.events import EventLog
    from engine.runtime import iso
    log = EventLog(engine, pack)
    src = "pipeline:autoloop"
    out: dict = {}
    c = report["constraint"]
    out["constraint"] = log.append(entity_type="agent_run", entity_id=pack.name, event_type=f"{pack.name}.constraint",
                                   payload=c["event"], source=src)["event_id"]
    out["velocity"] = []
    for v in report["velocity"]["agents"]:
        if v["proposed"]:
            out["velocity"].append(log.append(entity_type="agent_run", entity_id=v["agent"], event_type=f"{pack.name}.velocity",
                                              payload={k: v[k] for k in ("agent", "weeks", "adopted", "proposed", "gain_per_edit",
                                                                         "cost_per_gain_point", "trend")}, source=src)["event_id"])
    s = report["audit_sample"]
    out["audit_sample"] = log.append(entity_type="agent_run", entity_id=pack.name, event_type=f"{pack.name}.audit_sample",
                                     payload={"week": week, "run_ids": [p["run_id"] for p in s["runs"]], "seed": s["seed"]},
                                     source=src)["event_id"]
    for cov in report["coverage"]:
        if cov["uncovered"]["golden"] or cov["uncovered"]["holdout"] or cov["uncovered"]["exemplars"]:
            log.append(entity_type="agent_run", entity_id=cov["agent"], event_type=f"{pack.name}.coverage",
                       payload={"agent": cov["agent"], "week": week, "buckets": cov["live"], "uncovered": cov["uncovered"]}, source=src)
    for d in report["diversity"]:
        for f in d["fields"]:
            if f["mode_collapse"]:
                log.append(entity_type="agent_run", entity_id=d["agent"], event_type=f"{pack.name}.diversity",
                           payload={"agent": d["agent"], "field": f["field"], "distinct_ratio": f["distinct_ratio"],
                                    "ngram_repeat": f["ngram_repeat"], "week": week, "flag": "mode_collapse"}, source=src)
        if d["verdict_skew"]:
            log.append(entity_type="agent_run", entity_id=d["agent"], event_type=f"{pack.name}.diversity",
                       payload={"agent": d["agent"], "field": "verdict", "distinct_ratio": 1 - d["judge_followed_share"],
                                "ngram_repeat": None, "week": week, "flag": "verdict_skew"}, source=src)
    finished = engine.clock.now()
    hours = round((finished - started).total_seconds() / 3600, 6)
    out["cycle"] = log.append(entity_type="agent_run", entity_id=pack.name, event_type=f"{pack.name}.cycle",
                              payload={"week": week, "started": iso(started), "finished": iso(finished),
                                       "cost_usd": str(cycle_cost), "runs": cycle_runs, "hours": hours}, source=src)["event_id"]
    return out
