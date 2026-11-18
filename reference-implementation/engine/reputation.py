"""Reputation: a long track record per agent that compounds, partly resets on an edit, and buys leverage.

The kill rule looks at an agent's last twenty runs and the judge's safety case at its overrides;
neither remembers further, and neither pays out.  Here every run the agent ever made counts,
weighted ``0.5 ** (age / half_life_runs)`` (age counted in newer runs), with goodness 1 for a run
that succeeded and was not overridden or proven wrong, 0 otherwise.  A run made under a manifest
the agent has since moved past counts at ``carry_on_edit ** edits_since``: an edited agent starts
at ``carry_on_edit`` times the record of its predecessor, not at it and not at zero.

The score maps to a tier (config ``reputation.tiers``, best first).  Each cycle the autoloop
records one ``<pack>.reputation`` event per agent: a tier rises one step per cycle on the record,
falls at once when the score falls, and drops to the bottom at once on a kill or a judge
suspension.  The tier in force is leverage: the share of the agent's runs sent to human review
(``engine.verdicts --pending``), its sweep budget and workers (``engine.sweep``) and its share of
the planner's batch (``batch_resolves``).  A halted agent gets ``probation_runs`` golden-input runs
per cycle so the kill rule's "until it recovers" has a path: tit for tat, with forgiveness.
"""

from __future__ import annotations

import hashlib
import math
from decimal import Decimal

from engine.errors import EngineError
from engine.events import EventLog
from engine.hashing import sha256_tree


def _goodness(row: dict) -> float:
    if row["human_verdict"] in ("overridden", "wrong"):
        return 0.0
    return 1.0 if row["status"] == "succeeded" else 0.0


def _conflict(row: dict) -> float | None:
    summ = (row.get("judgement") or {}).get("summaries") or {}
    vals = [float(Decimal(s["conflict"])) for s in summ.values() if "conflict" in s]
    return sum(vals) / len(vals) if vals else None


def record(engine, pack, agent: str) -> dict:
    """The agent's long-horizon score with its lineage, and the cross-cycle metrics behind it."""
    cfg = engine.config.reputation
    current = sha256_tree(pack.agent_dir(agent), exclude_dirs=("eval", "crank"))
    rows = engine.store.list_runs(pack=pack.name, agent=agent)
    num = den = 0.0
    edits, newer = 0, current
    for age, row in enumerate(reversed(rows)):
        if row["manifest_hash"] != newer:
            edits += 1
            newer = row["manifest_hash"]
        w = 0.5 ** (age / cfg["half_life_runs"])
        num += w * _goodness(row) * cfg["carry_on_edit"] ** edits
        den += w
    lineage_edits = 0 if not rows else sum(1 for a, b in zip(rows, rows[1:]) if a["manifest_hash"] != b["manifest_hash"]) \
        + int(rows[-1]["manifest_hash"] != current)
    succeeded = [r for r in rows if r["status"] == "succeeded"]
    verdicted = [r for r in rows if r["human_verdict"]]
    conflicts = [c for c in (_conflict(r) for r in rows) if c is not None]
    cost = sum(Decimal(str(r["cost_usd"])) for r in rows)
    outcome_rows = [r for r in rows if r.get("verdict_source") == "outcome"]
    metrics = {"runs": len(rows), "pass_rate": None if not rows else round(len(succeeded) / len(rows), 4),
               "override_rate": None if not verdicted else round(sum(r["human_verdict"] in ("overridden", "wrong") for r in verdicted) / len(verdicted), 4),
               "mean_conflict_mass": None if not conflicts else round(sum(conflicts) / len(conflicts), 4),
               "cost_per_certified_usd": None if not succeeded else str((cost / len(succeeded)).quantize(Decimal("0.00000001"))),
               "outcome_hit_rate": None if not outcome_rows else round(sum(r["human_verdict"] == "followed" for r in outcome_rows) / len(outcome_rows), 4)}
    score = round(num / den, 6) if len(rows) >= cfg["min_runs"] and den > 0 else None
    return {"agent": agent, "score": score, "lineage": current, "edits": lineage_edits, "metrics": metrics}


# -- tiers ---------------------------------------------------------------------------------

def _tiers(engine) -> list[dict]:
    return engine.config.reputation["tiers"]


def last_event(engine, pack_name: str, agent: str) -> dict | None:
    evs = engine.store.query_events(event_type=f"{pack_name}.reputation", entity_id=agent, limit=1)
    return evs[0]["payload"] if evs else None


def current_tier(engine, pack_name: str, agent: str) -> str:
    ev = last_event(engine, pack_name, agent)
    return ev["tier"] if ev else engine.config.reputation["start_tier"]


def leverage(engine, pack_name: str, agent: str) -> dict:
    name = current_tier(engine, pack_name, agent)
    for t in _tiers(engine):
        if t["name"] == name:
            return t
    raise EngineError(f"agent {agent!r} sits in tier {name!r}, which config reputation.tiers no longer defines")


def step(tiers: list[dict], previous: str, score: float | None, *, forced: str | None) -> tuple[str, str]:
    """Next tier: bottom at once when forced; hold without a score; fall at once; rise one step."""
    names = [t["name"] for t in tiers]
    i = names.index(previous) if previous in names else len(names) - 1
    if forced:
        return names[-1], forced
    if score is None:
        return names[i], "too few runs to move the tier"
    target = next(k for k, t in enumerate(tiers) if score >= t["min_score"] or k == len(tiers) - 1)
    if target > i:
        return names[target], f"score {score:.4f} fell below {tiers[i]['min_score']}: down at once"
    if target < i:
        return names[i - 1], f"score {score:.4f} earns {names[target]}: up one step this cycle"
    return names[i], f"score {score:.4f} holds {names[i]}"


def update(engine, pack, cycle_label: str, *, killed: dict[str, str], judge_agent: str | None, judge_suspended: bool) -> list[dict]:
    """One ``<pack>.reputation`` event per agent: the score, the tier it moves to, and why."""
    log = EventLog(engine, pack)
    out = []
    for agent in sorted(pack.agent_names):
        rec = record(engine, pack, agent)
        prev = current_tier(engine, pack.name, agent)
        forced = (f"halted by the kill rule ({killed[agent]})" if agent in killed else
                  "the judge is suspended" if judge_suspended and agent == judge_agent else None)
        tier, why = step(_tiers(engine), prev, rec["score"], forced=forced)
        payload = {"agent": agent, "cycle": cycle_label, "score": rec["score"], "tier": tier, "previous_tier": prev,
                   "lineage": rec["lineage"], "edits": rec["edits"], "metrics": rec["metrics"], "why": why}
        log.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.reputation", payload=payload,
                   source="pipeline:reputation")
        out.append(payload)
    return out


# -- leverage consumers -----------------------------------------------------------------------

def _sampled(run_id: str, rate: float) -> bool:
    if rate >= 1.0:
        return True
    return int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF < rate


def review_sample(engine, pack_name: str, agent: str, rows: list[dict]) -> list[dict]:
    """The runs a human reviews: all of a standard agent's, a seeded share of a trusted one's."""
    rate = leverage(engine, pack_name, agent)["review_rate"]
    return [r for r in rows if _sampled(r["run_id"], rate)]


def agent_caps(engine, pack, max_runs: int) -> dict[str, int]:
    """{agent: most items it may hold in one batch}, only for agents whose tier grants less than the whole cap."""
    caps = {}
    for agent in sorted(pack.agent_names):
        share = leverage(engine, pack.name, agent)["max_runs_share"]
        if share < 1.0:
            caps[agent] = max(1, math.floor(share * max_runs))
    return caps


def cap_problems(output: dict, run_input: dict) -> list[str]:
    caps = run_input.get("caps") or {}
    counts: dict[str, int] = {}
    for item in output.get("batch") or []:
        if isinstance(item, dict) and isinstance(item.get("agent"), str):
            counts[item["agent"]] = counts.get(item["agent"], 0) + 1
    return [f"batch: {a} has {n} items; its reputation tier allows {caps[a]} per batch" for a, n in sorted(counts.items())
            if a in caps and n > caps[a]]


def sweep_leverage(engine, pack_name: str, agent: str, workers: int, budget: Decimal | None) -> tuple[str, int, Decimal | None]:
    t = leverage(engine, pack_name, agent)
    scaled = budget if budget is None or t["budget_mult"] == 1.0 else (budget * Decimal(str(t["budget_mult"]))).quantize(Decimal("0.00000001"))
    return t["name"], max(1, round(workers * t["workers_mult"])), scaled


def probation(runner, killed: dict[str, str], still_halted) -> list[dict]:
    """``probation_runs`` golden-input runs for each halted agent, recorded as ``<pack>.probation``."""
    from engine.eval import load_golden
    n = runner.engine.config.reputation["probation_runs"]
    pack = runner.pack
    out = []
    for agent in sorted(killed):
        path = pack.agent_dir(agent) / "eval" / "golden.jsonl"
        if n <= 0 or not path.is_file():
            continue
        cases = load_golden(path, pack_is_fixture=pack.fixture).cases
        if not cases:
            continue
        runs, passed = [], 0
        for i in range(n):
            try:
                r = runner.run(agent, cases[i % len(cases)].input)
            except EngineError:
                continue
            runs.append(r.run_id)
            passed += int(r.status == "succeeded")
        lifted = not still_halted(agent)
        runner.events.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.probation",
                             payload={"agent": agent, "runs": runs, "passed": passed, "lifted": lifted}, source="pipeline:reputation")
        out.append({"agent": agent, "runs": runs, "passed": passed, "lifted": lifted})
    return out


# -- report ------------------------------------------------------------------------------------

def crank_section(engine, pack) -> dict:
    out = {}
    for agent in sorted(pack.agent_names):
        ev = last_event(engine, pack.name, agent)
        if ev:
            out[agent] = {k: ev[k] for k in ("score", "tier", "previous_tier", "cycle", "edits", "metrics")}
    return out


def render_section(section: dict) -> list[str]:
    if not section:
        return []
    L = ["", "## Reputation (the long record and the leverage it buys)", "",
         "| agent | tier | was | score | runs | pass rate | override rate | conflict m(∅) | cost/certified | edits |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for agent, s in section.items():
        m = s["metrics"]
        L.append(f"| {agent} | {s['tier']} | {s['previous_tier']} | {s['score']} | {m['runs']} | {m['pass_rate']} | "
                 f"{m['override_rate']} | {m['mean_conflict_mass']} | {m['cost_per_certified_usd']} | {s['edits']} |")
    return L
