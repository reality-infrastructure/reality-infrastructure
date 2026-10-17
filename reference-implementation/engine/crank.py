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
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from engine.errors import EngineError
from engine.manifest import load_agent
from engine.packs import load_pack
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
    for r in runs:
        a = per_agent.setdefault(r["agent"], {"runs": 0, "succeeded": 0, "failed_guardrail": 0,
                                               "failed_verifier": 0, "access_denied": 0, "error": 0,
                                               "cost": Decimal(0), "latency_ms": 0, "items": 0})
        a["runs"] += 1
        a[r["status"]] += 1
        a["cost"] += Decimal(str(r["cost_usd"]))
        a["latency_ms"] += int(r["latency_ms"])
        a["items"] += int(r["items_evaluated"] or 0)
        if r["human_verdict"]:
            verdicts[f"{r['human_verdict']} ({r.get('verdict_source') or 'human'})"] += 1
            if r["human_verdict"] in ("overridden", "wrong") and r["verdict_reason"]:
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
    top_clusters = [{"cluster": k, "count": n, "runs": sorted(set(cluster_rows[k]))[:10]}
                    for k, n in clusters.most_common(10)]
    recommendation = _recommend(top_clusters, verdicts, override_reasons)
    return {"pack": pack.name, "week": week, "from": iso(start), "to": iso(end), "run_count": len(runs),
            "agents": agents_out, "verdicts": dict(sorted(verdicts.items())),
            "override_reasons": [{"reason": k, "count": n} for k, n in override_reasons.most_common(10)],
            "failure_clusters": top_clusters, "recommendation": recommendation}


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
    L += ["", "## Verdict distribution", ""]
    L += [f"- {k}: {v}" for k, v in report["verdicts"].items()] or ["- none recorded"]
    L += ["", "## Top override reasons", ""]
    L += [f"- {r['count']}× {r['reason']}" for r in report["override_reasons"]] or ["- none"]
    L += ["", "## Guardrail / verifier failure clusters", ""]
    L += [f"- {c['count']}× `{c['cluster']}`  runs: {', '.join(c['runs'])}" for c in report["failure_clusters"]] or ["- none"]
    rec = report["recommendation"]
    L += ["", "## Recommended change (one, lowest rung first)", "",
          f"rung: {rec['rung']}", "", rec["change"], "", f"evidence: `{rec['evidence']}`", "",
          "See IMPROVEMENT-ORDER.md.  A human turns this into the next refinement contract, or "
          "engine.autoloop lets the pack's refiner propose the rung-1/2 edit and adopts it only if the "
          "golden set does not get worse."]
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
