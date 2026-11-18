"""Refinement crank: the weekly report a human turns into the next contract.

    python -m engine.crank <pack> --week 2026-W42 [--db DSN] [--out DIR]

Writes ``packs/<pack>/crank/<week>.md`` with: runs, pass/fail rates, cost,
latency and scale_ratio per agent; verdict distribution and top override
reasons; guardrail/verifier failure clusters; the model-confidence conflict
mass (RI judgement) per agent; and ONE recommended rung-1 or rung-2 change
with the evidence rows.  The crank is a report, not an autopilot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from engine import stats
from engine.analytics import extend_report, render_sections
from engine.errors import EngineError
from engine.integrity import integrity_report, render_integrity, unspecific_runs
from engine.manifest import load_agent
from engine.packs import load_pack
from engine.fanout import coordination
from engine.runtime import iso
from engine.store import Engine

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def week_bounds(week: str) -> tuple[datetime, datetime]:
    m = _WEEK_RE.match(week)
    if not m:
        raise EngineError(f"week must look like 2026-W42, got {week!r}")
    start = datetime.fromisocalendar(int(m.group(1)), int(m.group(2)), 1).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _cluster_key(message: str) -> str:
    """Stable cluster label: strip paths/numbers so similar failures group."""
    key = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27}\b", "<id>", message)
    key = re.sub(r"\d+(\.\d+)?", "<n>", key)
    key = re.sub(r"'[^']*'", "'<v>'", key)
    return key[:120]


def build_report(engine: Engine, pack, week: str) -> dict:
    start, end = week_bounds(week)
    runs = engine.store.list_runs(pack=pack.name, since=iso(start), until=iso(end))
    per_agent: dict[str, dict] = {}
    clusters: Counter = Counter()
    cluster_rows: dict[str, list[str]] = defaultdict(list)
    verdicts: Counter = Counter()
    override_reasons: Counter = Counter()
    conflict: dict[str, list[Decimal]] = defaultdict(list)
    unspecific = unspecific_runs(engine, pack)              # an unspecific override steers no refinement
    for r in runs:
        a = per_agent.setdefault(r["agent"], {"runs": 0, "succeeded": 0, "failed_guardrail": 0,
                                               "failed_verifier": 0, "access_denied": 0, "error": 0, "needs_clarification": 0,
                                               "cost": Decimal(0), "latency_ms": 0, "items": 0})
        a["runs"] += 1
        a[r["status"]] += 1
        a["cost"] += Decimal(str(r["cost_usd"]))
        a["latency_ms"] += int(r["latency_ms"])
        a["items"] += int(r["items_evaluated"] or 0)
        if r["human_verdict"]:
            verdicts[f"{r['human_verdict']} ({r.get('verdict_source') or 'human'})"] += 1
            if r["human_verdict"] in ("overridden", "wrong") and r["verdict_reason"] and r["run_id"] not in unspecific:
                override_reasons[r["verdict_reason"].strip()] += 1
        for it in r["iterations"]:
            for cand in it.get("candidates", []):
                for g in cand.get("guardrails", []):
                    if not g["passed"]:
                        for msg in g["messages"]:
                            key = f"guardrail {g['id']}: {_cluster_key(msg)}"
                            clusters[key] += 1
                            cluster_rows[key].append(r["run_id"])
                v = cand.get("verifier")
                if v and not v["certified"]:
                    for msg in v["violations"]:
                        key = f"verifier: {_cluster_key(msg)}"
                        clusters[key] += 1
                        cluster_rows[key].append(r["run_id"])
                j = cand.get("judgement")
                if j:
                    conflict[r["agent"]].append(Decimal(j["conflict"]))
    agents_out = []
    for name in sorted(per_agent):
        a = per_agent[name]
        try:
            baseline = load_agent(pack, name, config=engine.config).manual_baseline_items
        except EngineError:
            baseline = None
        agents_out.append({
            "agent": name, "runs": a["runs"], "succeeded": a["succeeded"],
            "failed_guardrail": a["failed_guardrail"], "failed_verifier": a["failed_verifier"],
            "access_denied": a["access_denied"], "error": a["error"],
            "pass_rate": str((Decimal(a["succeeded"]) / a["runs"]).quantize(Decimal("0.001"))),
            "cost_usd": str(a["cost"].quantize(Decimal("0.00000001"))),
            "mean_latency_ms": a["latency_ms"] // a["runs"],
            "items_evaluated": a["items"],
            "scale_ratio": None if not baseline else str((Decimal(a["items"]) / baseline).quantize(Decimal("0.01"))),
            "mean_conflict_mass": None if not conflict[name] else
            str((sum(conflict[name]) / len(conflict[name])).quantize(Decimal("0.0001"))),
        })
    rigor_view = _rigor_view(engine, pack, runs, agents_out)
    weights = rigor_view["weights"]
    weighted = {k: sum(weights.get(rid, 1.0) for rid in cluster_rows[k]) for k in clusters}
    ranked = sorted(clusters.most_common(), key=lambda kn: -weighted[kn[0]])[:10]
    top_clusters = [{"cluster": k, "count": n, "runs": sorted(set(cluster_rows[k]))[:10], "weighted": round(weighted[k], 4)}
                    for k, n in ranked]
    recommendation = _recommend(top_clusters, verdicts, override_reasons)
    from engine import curate, forecast, outcome, reputation
    out = {"pack": pack.name, "week": week, "from": iso(start), "to": iso(end), "run_count": len(runs),
            "agents": agents_out, "verdicts": dict(sorted(verdicts.items())),
            "override_reasons": [{"reason": k, "count": n} for k, n in override_reasons.most_common(10)],
            "failure_clusters": top_clusters, "recommendation": recommendation, "saturation": rigor_view["saturation"],
            "outcomes": outcome.crank_section(engine, pack, iso(start), iso(end)),
            "reputation": reputation.crank_section(engine, pack), "forecasts": forecast.crank_section(engine, pack),
            "curator": curate.record(engine, pack), **_operations(engine, pack, runs, start, end),
            "coordination": coordination(engine, pack, iso(start), iso(end))}
    extend_report(engine, pack, week, runs, out)
    from engine.adoption import extend_report as adoption_report
    adoption_report(engine, pack, week, runs, out)       # JH-C11 wpB: cost per useful output, deletion, plateau / stall escalation
    out["integrity"] = integrity_report(engine, pack, runs, out)
    from engine.governance import crank_section
    out["governance"] = crank_section(engine, pack, runs)          # JH-C11 wpD
    return out


def _rigor_view(engine: Engine, pack, runs: list[dict], agents_out: list[dict]) -> dict:
    """JH-C11 wpA on the crank: every agent's pass rate with its interval, its golden view of the week (score
    beside the operator's baseline, the weakest stratum, the tier ladder), saturation of its golden set, and the
    value weight of every run on a weighted case (failure clusters rank by weighted count)."""
    from engine.eval import case_passes, load_golden
    from engine.goldenview import golden_view, value_weights
    from engine.rigor import input_key, saturation
    cfg, conf = engine.config.eval_rigor, engine.config.stats["confidence"]
    weights, sat = {}, {}
    for a in agents_out:
        a["pass_rate_interval"] = stats.rate(a["succeeded"], a["runs"], conf)
        a["golden"] = golden_view(engine, pack, a["agent"], runs)
        vw = value_weights(pack, a["agent"])
        for r in runs:
            if r["agent"] == a["agent"] and input_key(r["input"]) in vw:
                weights[r["run_id"]] = vw[input_key(r["input"])]
        path = pack.agent_dir(a["agent"]) / "eval" / "golden.jsonl"
        if path.is_file():
            g = load_golden(path, pack_is_fixture=pack.fixture)
            s = saturation(engine, pack, a["agent"], g.cases, g.compare, case_passes,
                           k=cfg["saturation_k"], max_share=cfg["max_saturated_share"])
            if s["flagged"]:
                sat[a["agent"]] = s
    return {"weights": weights, "saturation": sat}



def _operations(engine: Engine, pack, runs: list[dict], start: datetime, end: datetime) -> dict:
    """JH-C11 wpG: the spread of cost, latency and tokens per run, pass rate per version, and the schedule's week."""
    from engine.rollout import by_version
    from engine.schedule import week_summary
    from engine.sizing import percentiles_by_agent
    return {"percentiles": percentiles_by_agent(runs), "by_version": by_version(runs),
            "schedule": week_summary(engine, pack, iso(start), iso(end))}


def _recommend(clusters: list[dict], verdicts: Counter, overrides: Counter) -> dict:
    if clusters:
        top = clusters[0]
        label = top["cluster"]
        if "citations_resolve" in label or "no_fabrication" in label or "cited_values_match" in label:
            rung, change = 1, ("Rung 1 (grounding): the top failure cluster is citation/fabrication. "
                               "Add the missing source rows to the agent's grounding sources or memory "
                               "queries so the figures it needs are in context.")
        elif "verifier" in label:
            rung, change = 2, ("Rung 2 (harness): the top failure cluster is a verifier violation. "
                               "Feed the recomputed figures back as a worked example in skills.md and "
                               "tighten the output schema for the misstated field.")
        else:
            rung, change = 2, ("Rung 2 (harness): the top failure cluster is a guardrail. Adjust the "
                               "system prompt / output schema for that field; keep the guardrail.")
        return {"rung": rung, "change": change, "evidence": top}
    if overrides:
        reason, n = overrides.most_common(1)[0]
        return {"rung": 1, "change": f"Rung 1 (grounding): operators override most often for "
                f"'{reason}' ({n}x). Ground the agent on the data that reason names.",
                "evidence": {"reason": reason, "count": n}}
    return {"rung": None, "change": "No failures or overrides this week; no change recommended.",
            "evidence": None}


def render(report: dict) -> str:
    L = [f"# Crank — {report['pack']} — {report['week']}", "",
         f"window: {report['from']} → {report['to']}  runs: {report['run_count']}", "",
         "## Runs per agent", "",
         "| agent | runs | ok | guardrail | verifier | access | error | pass rate | cost USD | mean ms | items | scale_ratio | mean conflict m(∅) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in report["agents"]:
        L.append(f"| {a['agent']} | {a['runs']} | {a['succeeded']} | {a['failed_guardrail']} | "
                 f"{a['failed_verifier']} | {a['access_denied']} | {a['error']} | {a['pass_rate']} | "
                 f"{a['cost_usd']} | {a['mean_latency_ms']} | {a['items_evaluated']} | "
                 f"{a['scale_ratio']} | {a['mean_conflict_mass']} |")
    L += ["", "## Golden view of the week (pass rate interval, golden score vs the operator, weakest stratum, tiers)", ""]
    for a in report["agents"]:
        iv, g = a.get("pass_rate_interval"), a.get("golden")
        line = f"- {a['agent']}: pass rate {a['pass_rate']} ({iv['lo']}-{iv['hi']} at {iv['confidence']:.0%}, n={iv['n']})" if iv else f"- {a['agent']}"
        if g:
            line += f"; golden {g['score']} on {g['counted']} cases ({g['interval']['lo']}-{g['interval']['hi']})"
            if g["human_baseline"]:
                line += f"; operator baseline {g['human_baseline']['score']} (n={g['human_baseline']['n']}), delta {g['human_delta']}"
            if g["weakest_stratum"]:
                w = g["weakest_stratum"]
                line += f"; weakest stratum {w['stratum']}={w['value']} at {w['score']} ({w['counted']} cases)"
            if g["curriculum"]:
                c = g["curriculum"]
                line += f"; tiers mastered {c['mastered_tier']} frontier {c['frontier_tier']}" + (f" gaps {c['gaps']}" if c["gaps"] else "")
        L.append(line)
    for agent, s in sorted((report.get("saturation") or {}).items()):
        L.append(f"- SATURATED {agent}: {len(s['saturated'])} of {s['cases']} golden cases passed on each of their last runs "
                 f"({s['share']}); add harder cases. Failed inputs not yet cases: "
                 + (", ".join(json.dumps(h["input"], sort_keys=True) for h in s["hard_case_candidates"]) or "none"))
    L += ["", "## Verdict distribution", ""]
    L += [f"- {k}: {v}" for k, v in report["verdicts"].items()] or ["- none recorded"]
    L += ["", "## Top override reasons", ""]
    L += [f"- {r['count']}× {r['reason']}" for r in report["override_reasons"]] or ["- none"]
    L += ["", "## Guardrail / verifier failure clusters", ""]
    L += [f"- {c['count']}× `{c['cluster']}`  runs: {', '.join(c['runs'])}" for c in report["failure_clusters"]] or ["- none"]
    from engine import curate, forecast, outcome, reputation
    L += outcome.render_section(report.get("outcomes") or {}) + reputation.render_section(report.get("reputation") or {})
    L += forecast.render_section(report.get("forecasts") or {}) + curate.render_section(report.get("curator") or {})
    co = report.get("coordination")
    if co and co["child_runs"]:
        L += ["", "## Coordination (fan-out children)", "",
              f"{co['fanout_groups']} groups, {co['child_runs']} child runs, {co['messages']} messages, "
              f"{co['messages_per_child_run']} per child run (0 = the children solved independently)"]
    rec = report["recommendation"]
    L += ["", "## Recommended change (one, lowest rung first)", "",
          f"rung: {rec['rung']}", "", rec["change"], "", f"evidence: `{rec['evidence']}`", "",
          "See IMPROVEMENT-ORDER.md.  A human turns this into the next refinement contract, or "
          "engine.autoloop lets the pack's refiner propose the rung-1/2 edit and adopts it only if the "
          "golden set does not get worse."]
    if "percentiles" in report:
        L += ["", "## Spread per run (p50 / p95 / max)", "",
              "| agent | cost USD | latency ms | tokens | runs/hour/worker |", "|---|---|---|---|---|"]
        for name, q in report["percentiles"].items():
            L.append(f"| {name} | {q['cost_usd']['p50']} / {q['cost_usd']['p95']} / {q['cost_usd']['max']} | "
                     f"{q['latency_ms']['p50']} / {q['latency_ms']['p95']} / {q['latency_ms']['max']} | "
                     f"{q['tokens']['p50']} / {q['tokens']['p95']} / {q['tokens']['max']} | {q['runs_per_hour_per_worker']} |")
        L += ["", "## Pass rate per version", ""]
        L += [f"- {a} {h[:12]}: {v['succeeded']}/{v['runs']} ({v['pass_rate']})"
              for a, vs in sorted(report["by_version"].items()) for h, v in vs.items()] or ["- no runs"]
        sc = report["schedule"]
        L += ["", "## Schedule", "", f"ticks recorded {sc['ticks']}; missed {sc['missed']}; heartbeats {sc['heartbeats']}"]
        L += [f"- {j}: ran {c['ran']}, skipped {c['skipped']}, failed {c['failed']}, missed {c['missed']}"
              for j, c in sorted(sc["by_job"].items())]
    if "integrity" in report:
        L += render_integrity(report["integrity"])
    L += render_sections(report)
    from engine.governance import render_section, render_top
    L[2:2] = render_top(report.get("governance"))                   # JH-C11 wpD: red flags head the report
    L += render_section(report.get("governance"))
    from engine.adoption import render_section as adoption_section
    L += adoption_section(report)
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.crank")
    p.add_argument("pack")
    p.add_argument("--week", required=True)
    p.add_argument("--db")
    p.add_argument("--out", help="directory (default packs/<pack>/crank)")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            pack = load_pack(args.pack)
            report = build_report(engine, pack, args.week)
        finally:
            engine.close()
        out_dir = Path(args.out) if args.out else pack.root / "crank"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{args.week}.md"
        path.write_text(render(report), encoding="utf-8")
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"crank report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
