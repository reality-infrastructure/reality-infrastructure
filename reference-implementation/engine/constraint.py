"""The binding constraint: the one thing capping throughput this cycle, re-identified every cycle (JH-C11 wpF).

Musk's question is not "what fails most often" but "what limits output": a small failure cluster can
sit beside a tool budget that eats most candidates.  ``identify`` classifies every lost run of the week
(and of the trailing ``constraint.window_weeks``) by what ended it: access denied, provider or engine
error, tool budget exhausted, max_tokens stop, refusal, memory truncation, guardrail, verifier; adds the
pack-level limiters (adapter latency breaches per slot, an unjudged backlog nobody is clearing, budget
spent, cost per run rising against the trailing window); ranks them by runs lost, then dollars lost;
and names the top one THE constraint and the second the next one.  It also builds the funnel per agent
(input, proposed, guardrails pass, certified, judged, followed, golden) so the drop at each step shows.

``resources`` is the report side of Patel's throughput question: where the wall-clock goes (provider
calls versus the engine's own tools, checks and store), how many runs overlap, how much of the budget
is spent and how much of the work waits on a verdict, and which of those binds.

The loop acts on it: the planner is handed the constraint and, once it has cost ``min_lost_runs`` runs
of one agent, ``batch_resolves`` requires ``constraint_share`` of the batch to go to that agent; the
refiner is pointed at the constraint's agent rather than the most frequent cluster; a ``<pack>.constraint``
event per cycle carries the previous top so a moved constraint is visible.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal

from engine.analytics import JUDGEABLE, golden_inputs, role_of, run_context, shift_week, week_events, week_runs
from engine.runtime import parse_iso

AGENT_KINDS = ("access_denied", "provider_error", "error", "tool_budget", "max_tokens", "refusal",
               "memory_truncation", "guardrail", "verifier")
HARNESS_KINDS = ("tool_budget", "max_tokens", "refusal", "memory_truncation")


def _cands(row: dict) -> list[dict]:
    return [c for it in row.get("iterations") or [] for c in it.get("candidates") or []]


def loss_kind(row: dict) -> str | None:
    """What ended a failed run; None for a run that succeeded."""
    status = row["status"]
    if status == "succeeded":
        return None
    if status == "access_denied":
        return "access_denied"
    if status == "error":
        return "provider_error" if any("ProviderError" in r for r in row["failure_reasons"]) else "error"
    cands = _cands(row)
    if any("tool budget" in m for c in cands for m in c.get("failure_reasons") or []):
        return "tool_budget"
    if any(pc.get("stop_reason") == "max_tokens" for c in cands for pc in c.get("provider_calls") or []):
        return "max_tokens"
    if any("refused" in m for c in cands for m in c.get("failure_reasons") or []):
        return "refusal"
    ctx = run_context(row)
    if ctx and ctx.get("truncation"):
        return "memory_truncation"
    return "verifier" if status == "failed_verifier" else "guardrail"


def _limiters(engine, pack, runs: list[dict], weeks: list[str], judge_suspended: bool) -> list[dict]:
    lim: dict[str, dict] = {}

    def add(kind: str, component: str, agent: str | None, runs_lost: int, usd: Decimal, run_id: str | None = None) -> None:
        key = f"{kind}:{component}"
        e = lim.setdefault(key, {"id": key, "kind": kind, "component": component, "agent": agent,
                                 "lost_runs": 0, "lost_usd": Decimal(0), "runs": []})
        e["lost_runs"] += runs_lost
        e["lost_usd"] += usd
        if run_id and len(e["runs"]) < 10:
            e["runs"].append(run_id)

    for r in runs:
        kind = loss_kind(r)
        if kind:
            add(kind, r["agent"], r["agent"], 1, Decimal(str(r["cost_usd"])), r["run_id"])
    for w in weeks:
        for e in week_events(engine, pack, "latency_breach", w):
            add("latency", e["payload"]["slot"], None, 1, Decimal(0))
    has_judge = any(role_of(pack, n) == "judge" for n in pack.agent_names)
    if judge_suspended or not has_judge:
        backlog = [r for r in runs if r["role"] in JUDGEABLE and not r["human_verdict"]]
        for r in backlog:
            add("verdict_backlog", "operator", None, 1, Decimal(0), r["run_id"])
    total = sum((Decimal(str(r["cost_usd"])) for r in runs), Decimal(0))
    budget = engine.config.sweep["budget_usd"]
    if budget is not None and total >= Decimal(str(budget)):
        add("budget", "sweep", None, 0, total - Decimal(str(budget)))
    return sorted(lim.values(), key=lambda e: (-e["lost_runs"], -e["lost_usd"], e["id"]))


def _cost_trend(engine, pack, week: str, runs: list[dict], window: int) -> dict | None:
    rise = float(engine.config.analytics["constraint"]["cost_rise"])
    prior = [r for k in range(1, window + 1) for r in week_runs(engine, pack, shift_week(week, -k))]
    if not runs or not prior:
        return None
    now = sum((Decimal(str(r["cost_usd"])) for r in runs), Decimal(0)) / len(runs)
    before = sum((Decimal(str(r["cost_usd"])) for r in prior), Decimal(0)) / len(prior)
    if before > 0 and now > before * Decimal(str(rise)):
        return {"id": "cost_trend:runs", "kind": "cost_trend", "component": "runs", "agent": None, "lost_runs": 0,
                "lost_usd": (now - before) * len(runs), "runs": [], "per_run_now": str(now), "per_run_before": str(before)}
    return None


def funnel(pack, runs: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    gold: dict[str, set] = {}
    for r in runs:
        if r["role"] not in JUDGEABLE:
            continue
        if r["agent"] not in gold:
            gold[r["agent"]] = {json.dumps(i, sort_keys=True) for i in golden_inputs(pack, r["agent"])}
        f = out.setdefault(r["agent"], {"input": 0, "proposed": 0, "guardrails_pass": 0, "certified": 0,
                                        "judged": 0, "followed": 0, "golden": 0})
        cands = _cands(r)
        f["input"] += 1
        f["proposed"] += int(any(c.get("output") is not None for c in cands))
        f["guardrails_pass"] += int(any(c.get("guardrails") and all(g["passed"] for g in c["guardrails"]) for c in cands))
        f["certified"] += int(r["status"] == "succeeded")
        f["judged"] += int(bool(r["human_verdict"]))
        f["followed"] += int(r["human_verdict"] == "followed")
        f["golden"] += int(r["human_verdict"] == "followed" and json.dumps(r["input"], sort_keys=True) in gold[r["agent"]])
    return out


def candidate_shares(runs: list[dict]) -> dict[str, dict]:
    """Per agent, the share of candidates that ended on the tool budget, a max_tokens stop or a refusal."""
    tot: Counter = Counter()
    hit: dict[str, Counter] = defaultdict(Counter)
    for r in runs:
        for c in _cands(r):
            tot[r["agent"]] += 1
            msgs = c.get("failure_reasons") or []
            hit[r["agent"]]["tool_budget"] += int(any("tool budget" in m for m in msgs))
            hit[r["agent"]]["refusal"] += int(any("refused" in m for m in msgs))
            hit[r["agent"]]["max_tokens"] += int(any(pc.get("stop_reason") == "max_tokens" for pc in c.get("provider_calls") or []))
    return {a: {k: round(hit[a][k] / tot[a], 4) for k in ("tool_budget", "max_tokens", "refusal")} for a in sorted(tot)}


def _public(lim: dict | None) -> dict | None:
    if lim is None:
        return None
    return {**lim, "lost_usd": str(Decimal(lim["lost_usd"]).quantize(Decimal("0.00000001")))}


def identify(engine, pack, week: str, runs: list[dict], report: dict) -> dict:
    from engine.autoloop import judge_safety
    cfg = engine.config.analytics["constraint"]
    window = int(cfg["window_weeks"])
    suspended = judge_safety(engine, pack)["suspended"]
    week_lim = _limiters(engine, pack, runs, [week], suspended)
    trend = _cost_trend(engine, pack, week, runs, window)
    if trend:
        week_lim = sorted(week_lim + [trend], key=lambda e: (-e["lost_runs"], -e["lost_usd"], e["id"]))
    weeks = [shift_week(week, -k) for k in range(window - 1, -1, -1)]
    trailing_runs = [r for w in weeks for r in (runs if w == week else week_runs(engine, pack, w))]
    window_lim = _limiters(engine, pack, trailing_runs, weeks, suspended)
    prev = engine.store.query_events(event_type=f"{pack.name}.constraint", limit=1)
    previous_top = prev[0]["payload"]["top"] if prev else None
    top = week_lim[0] if week_lim else None
    nxt = week_lim[1] if len(week_lim) > 1 else None
    binding = bool(top and top["kind"] in AGENT_KINDS and top["agent"] and role_of(pack, top["agent"]) in JUDGEABLE
                   and top["lost_runs"] >= int(cfg["min_lost_runs"]))
    return {
        "top": _public(top), "next": _public(nxt), "limiters": [_public(e) for e in week_lim[:10]],
        "window_weeks": window, "window_top": _public(window_lim[0]) if window_lim else None,
        "window_next": _public(window_lim[1]) if len(window_lim) > 1 else None,
        "previous_top": previous_top, "moved": previous_top is not None and previous_top != (top or {}).get("id"),
        "binding_agent": top["agent"] if binding else None, "constraint_share": float(cfg["constraint_share"]),
        "funnel": funnel(pack, runs), "candidate_shares": candidate_shares(runs),
        "event": {"week": week, "top": top["id"] if top else None, "next": nxt["id"] if nxt else None,
                  "metric": "lost_runs" if top and top["lost_runs"] else ("lost_usd" if top else None),
                  "lost_runs": top["lost_runs"] if top else 0,
                  "lost_usd": str(Decimal(top["lost_usd"]).quantize(Decimal("0.00000001"))) if top else "0",
                  "previous_top": previous_top, "agent": top["agent"] if top else None,
                  "window_top": window_lim[0]["id"] if window_lim else None},
    }


def planner_input(constraint: dict, killed: dict) -> dict:
    """What the planner is told: the constraint, and the share it must give the constraint agent while it binds."""
    top = constraint.get("top") or {}
    out = {"constraint": {"top": top.get("id"), "kind": top.get("kind"), "agent": top.get("agent"),
                          "lost_runs": top.get("lost_runs", 0), "next": (constraint.get("next") or {}).get("id")}}
    agent = constraint.get("binding_agent")
    if agent and agent not in killed:
        out["constraint_share"] = constraint["constraint_share"]
    return out


def steer_recommendation(report: dict) -> None:
    """Point the one recommendation at the constraint: a harness limiter (tool budget, max_tokens, refusal,
    truncation) that cost more runs than the top failure cluster becomes the recommendation; a pass-rate
    constraint on another agent than the top cluster's moves the recommendation to that agent's cluster."""
    from engine.crank import _recommend
    c = report["constraint"]
    top = c.get("top")
    rec = report["recommendation"]
    if not top or not top.get("agent"):
        rec["constraint"] = top["id"] if top else None
        return
    clusters = report.get("failure_clusters") or []
    top_cluster_runs = len(set(clusters[0]["runs"])) if clusters else 0
    evidence = {"cluster": f"constraint {top['id']}", "count": top["lost_runs"], "runs": list(top["runs"])}
    if top["kind"] in HARNESS_KINDS and top["lost_runs"] > top_cluster_runs:
        if top["kind"] == "memory_truncation":
            change = (f"Rung 1 (grounding): the binding constraint is working-memory truncation on {top['agent']} "
                      f"({top['lost_runs']} runs lost). Narrow the grounding sources or memory queries to what its output cites.")
            rung = 1
        else:
            change = (f"Rung 2 (harness): the binding constraint is {top['kind'].replace('_', ' ')} on {top['agent']} "
                      f"({top['lost_runs']} runs lost, more than the top failure cluster). State in workflow.md when to stop "
                      f"calling tools and submit; keep the budget.")
            rung = 2
        report["recommendation"] = {"rung": rung, "change": change, "evidence": evidence, "constraint": top["id"]}
        return
    if top["kind"] in ("guardrail", "verifier"):
        mine = set(top["runs"])
        for i, cl in enumerate(clusters):
            if mine & set(cl["runs"]):
                if i > 0:
                    report["recommendation"] = {**_recommend([cl], Counter(), Counter()), "constraint": top["id"]}
                    return
                break
    rec["constraint"] = top["id"]


# -- resources (G-D3, report side) ---------------------------------------------------------------

def resources(engine, pack, runs: list[dict]) -> dict:
    """Where the week's wall-clock went and which resource binds."""
    by_id = {r["run_id"]: r for r in runs}
    child_ms: Counter = Counter()
    for r in runs:
        if r["parent_run_id"] in by_id:
            child_ms[r["parent_run_id"]] += int(r["latency_ms"])
    provider_ms = engine_ms = 0
    per_agent: dict[str, dict] = {}
    starts, ends = [], []
    for r in runs:
        own = max(0, int(r["latency_ms"]) - child_ms[r["run_id"]])
        p = min(own, sum(int(pc.get("latency_ms") or 0) for c in _cands(r) for pc in c.get("provider_calls") or []))
        provider_ms += p
        engine_ms += own - p
        a = per_agent.setdefault(r["agent"], {"provider_ms": 0, "engine_ms": 0, "runs": 0})
        a["provider_ms"] += p
        a["engine_ms"] += own - p
        a["runs"] += 1
        t0 = parse_iso(r["created_at"])
        starts.append(t0)
        ends.append(t0.timestamp() * 1000 + int(r["latency_ms"]))
    busy = provider_ms + engine_ms
    span_ms = 0 if not runs else max(0.0, max(ends) - min(s.timestamp() * 1000 for s in starts))
    budget = engine.config.sweep["budget_usd"]
    total = sum((Decimal(str(r["cost_usd"])) for r in runs), Decimal(0))
    judgeable = [r for r in runs if r["role"] in JUDGEABLE]
    backlog = (sum(1 for r in judgeable if not r["human_verdict"]) / len(judgeable)) if judgeable else 0.0
    pressure = {
        "provider_latency": round(provider_ms / busy, 4) if busy else 0.0,
        "engine": round(engine_ms / busy, 4) if busy else 0.0,
        "budget": 0.0 if budget is None or Decimal(str(budget)) == 0 else round(float(total / Decimal(str(budget))), 4),
        "operator_verdict_backlog": round(backlog, 4),
    }
    binding = None if not runs else max(sorted(pressure), key=lambda k: pressure[k])
    return {"provider_ms": provider_ms, "engine_ms": engine_ms, "provider_share": pressure["provider_latency"],
            "engine_share": pressure["engine"], "span_ms": round(span_ms), "concurrency": round(busy / span_ms, 4) if span_ms else None,
            "budget_used": pressure["budget"], "verdict_backlog_share": pressure["operator_verdict_backlog"],
            "pressure": pressure, "binding": binding,
            "per_agent": {k: {**v, "provider_share": round(v["provider_ms"] / (v["provider_ms"] + v["engine_ms"]), 4)
                              if (v["provider_ms"] + v["engine_ms"]) else 0.0} for k, v in sorted(per_agent.items())}}


def render(report: dict) -> list[str]:
    c = report["constraint"]
    top, nxt = c.get("top"), c.get("next")
    L = ["", "## The constraint (re-identified every cycle)", ""]
    if top:
        L.append(f"- THE constraint: `{top['id']}` — {top['lost_runs']} runs lost, ${top['lost_usd']} lost"
                 + (f" (runs {', '.join(top['runs'][:5])})" if top["runs"] else ""))
    else:
        L.append("- THE constraint: none this week (no run lost)")
    L.append(f"- next: `{nxt['id']}` — {nxt['lost_runs']} runs, ${nxt['lost_usd']}" if nxt else "- next: none")
    wt = c.get("window_top")
    L.append(f"- over the trailing {c['window_weeks']} weeks: `{wt['id']}` ({wt['lost_runs']} runs)" if wt else
             f"- over the trailing {c['window_weeks']} weeks: none")
    if c.get("previous_top"):
        L.append(f"- previous cycle's constraint: `{c['previous_top']}`" + (" — the constraint MOVED" if c["moved"] else " — unchanged"))
    if c.get("binding_agent"):
        L.append(f"- binding: the planner must give at least {c['constraint_share']:.0%} of its batch to {c['binding_agent']}")
    L += ["", "| agent | input | proposed | guardrails pass | certified | judged | followed | golden | tool-budget share |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a, f in sorted(c["funnel"].items()):
        L.append(f"| {a} | {f['input']} | {f['proposed']} | {f['guardrails_pass']} | {f['certified']} | {f['judged']} | "
                 f"{f['followed']} | {f['golden']} | {c['candidate_shares'].get(a, {}).get('tool_budget', 0)} |")
    r = report["resources"]
    L += ["", f"Resources: provider {r['provider_ms']} ms ({r['provider_share']:.0%}), engine {r['engine_ms']} ms "
              f"({r['engine_share']:.0%}), concurrency {r['concurrency']}, budget used {r['budget_used']}, "
              f"verdict backlog {r['verdict_backlog_share']:.0%}; binding resource: **{r['binding']}**"]
    return L


def sweep_throughput(engine, pack, agent: str, results: list[dict], *, workers: int, budget_usd: Decimal | None) -> dict:
    """A sweep's throughput: runs and items per hour against the manual baseline, worker utilisation, the
    engine-side share of wall time (tools, checks, store and its lock: not timed apart) and the binding resource."""
    from engine.analytics import _baseline
    ids = [e[k] for e in results for k in ("run_id", "judge_run_id") if e.get(k)]
    rows = [r for r in (engine.store.get_run(i) for i in ids) if r is not None]
    res = resources(engine, pack, rows)
    mine = [r for r in rows if r["agent"] == agent]
    hours = res["span_ms"] / 3_600_000 if res["span_ms"] else 0.0
    items = sum(int(r["items_evaluated"] or 0) for r in mine)
    baseline = _baseline(engine, pack, agent)
    busy = res["provider_ms"] + res["engine_ms"]
    pressure = dict(res["pressure"])
    if budget_usd is not None and budget_usd > 0:
        pressure["budget"] = round(float(sum((Decimal(str(r["cost_usd"])) for r in rows), Decimal(0)) / budget_usd), 4)
    binding = None if not rows else max(sorted(pressure), key=lambda k: pressure[k])
    return {"agent": agent, "workers": int(workers), "runs": len(mine),
            "runs_per_hour": round(len(mine) / hours, 2) if hours else 0.0,
            "items_per_hour": round(items / hours, 2) if hours else None, "manual_baseline_items": baseline,
            "provider_share": res["provider_share"], "lock_wait_share": res["engine_share"],
            "utilisation": round(min(1.0, busy / (workers * res["span_ms"])), 4) if res["span_ms"] else 0.0,
            "pressure": pressure, "binding": binding or "none"}
