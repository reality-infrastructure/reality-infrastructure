"""The adoption law: when an edit is better, judged on evidence, cost and its whole system (JH-C11 wpB).

``engine.autoloop.adopt_decision`` is the C7 rule (golden and held-out do not fall and still pass) plus
wpA's refusals (pass@k, strata, objective).  ``decide`` is the law the loop adopts by; it keeps that rule
and adds, each a refusal with its reason:

- evidence (Naval, G-NCD9)  per-case paired wins and losses with a one-sided sign test; a golden or
  held-out set below ``adopt.min_cases`` is small evidence (refused or flagged); where the operator asks
  for it (``adopt.require_strict_gain_on``) the wins must beat the noise bound and ties keep the incumbent
- cost (Musk G-M2, Patel G-D7)  cost per golden case from every draw's trace: a rise above
  ``cost.max_cost_rise`` is refused; at equal scores the cheaper side wins; an equal-score edit that
  is cheaper or faster by ``cost.min_efficiency_gain`` is adopted as an efficiency gain
- anchor (Brown, G-B16)  the generation-0 scores (engine.lifecycle) bound every step, not only the last
- system (Musk, G-M15)  the golden and held-out sets of every orchestrator that calls the agent
- rules (Musk, G-M13)  a rule a golden case pins and the edit breaks is named (engine.rules)
- exploration (Musk, G-M4)  one edit per stall may let golden fall by ``stall.explore_tolerance`` when
  a held-out set exists and does not fall

The crank side (``extend_report``): cost per useful output, rework, the cost split, the floor cost and the
overhead over it, iterations and candidates to acceptance, ramp-up to the first PASS, and a deletion
recommendation for a grounding source no followed run cites.

No clock, no randomness.
"""

from __future__ import annotations

import math
from decimal import Decimal

from engine import rigor
from engine.errors import EngineError
from engine.events import EventLog

Q8 = Decimal("0.00000001")
Q4 = Decimal("0.0001")


# -- per-draw and per-model economics (called by engine.eval) ---------------------------------------------

def _candidates(row: dict) -> list[dict]:
    return [c for it in row.get("iterations") or [] for c in it.get("candidates") or []]


def draw_economics(result) -> dict:
    """Cost, tokens, provider latency, and iterations / candidates spent until a candidate was accepted, of one eval draw."""
    row = result.row
    iterations = [it for it in row.get("iterations") or [] if it.get("candidates")]
    tokens, latency, n_cand, accepted = 0, 0, 0, False
    for it in iterations:
        for c in it["candidates"]:
            calls = c.get("provider_calls") or []
            tokens += sum(int(p.get("input_tokens") or 0) + int(p.get("output_tokens") or 0) for p in calls)
            latency += sum(int(p.get("latency_ms") or 0) for p in calls)    # the provider's own figure, not the engine's wall clock
            if not accepted:
                n_cand += 1
            accepted = accepted or bool(c.get("accepted"))
    return {"cost_usd": str(Decimal(str(result.cost_usd)).quantize(Q8)), "tokens": tokens, "latency_ms": latency,
            "iterations": len(iterations), "candidates": n_cand, "accepted": accepted}


def economics(cases: list[dict]) -> dict:
    """``{"economics": {...}}`` for a model row: cost and tokens per counted case (each case's mean over its draws),
    cost per passed case, latency per case, mean iterations and candidates to acceptance.  Each case entry gains
    its own ``cost_usd`` and ``tokens`` (means over its draws)."""
    for c in cases:
        draws = [d for d in c.get("draws") or [] if "cost_usd" in d]
        if draws:
            c["cost_usd"] = str((sum(Decimal(d["cost_usd"]) for d in draws) / len(draws)).quantize(Q8))
            c["tokens"] = sum(d["tokens"] for d in draws) // len(draws)
    counted = [c for c in cases if c["counted"] and "cost_usd" in c]
    if not counted:
        return {"economics": None}
    draws = [d for c in counted for d in c["draws"]]
    total = sum(Decimal(d["cost_usd"]) for d in draws)
    passed = sum(1 for c in counted if c["passed"])
    acc = [d for d in draws if d["accepted"]]
    return {"economics": {
        "cost_per_case": str((sum(Decimal(c["cost_usd"]) for c in counted) / len(counted)).quantize(Q8)),
        "cost_per_pass": None if not passed else str((total / passed).quantize(Q8)),
        "tokens_per_case": sum(c["tokens"] for c in counted) // len(counted),
        "latency_ms_per_case": sum(d["latency_ms"] for d in draws) // len(draws),
        "iterations_to_accept": None if not acc else str((Decimal(sum(d["iterations"] for d in acc)) / len(acc)).quantize(Q4)),
        "candidates_to_accept": None if not acc else str((Decimal(sum(d["candidates"] for d in acc)) / len(acc)).quantize(Q4)),
    }}


# -- evidence: paired per-case comparison and the noise bound ----------------------------------------------

def sign_p(wins: int, losses: int) -> float:
    """One-sided exact sign test: the chance of at least ``wins`` of ``wins + losses`` coin flips."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def paired(before: dict, after: dict) -> dict:
    """Cases counted on both sides, compared one by one: a win fails before and passes after, a loss the reverse."""
    b = {c["id"]: c for c in before["models"][0].get("cases") or [] if c.get("counted", True)}
    a = {c["id"]: c for c in after["models"][0].get("cases") or [] if c.get("counted", True)}
    both = sorted(set(b) & set(a))
    wins = sum(1 for i in both if a[i]["passed"] and not b[i]["passed"])
    losses = sum(1 for i in both if b[i]["passed"] and not a[i]["passed"])
    return {"n": len(both), "wins": wins, "losses": losses, "p": round(sign_p(wins, losses), 6)}


def _score(ev: dict | None) -> Decimal | None:
    return None if ev is None else Decimal(ev["models"][0]["score"])


def _econ(ev: dict | None) -> dict | None:
    return None if ev is None else ev["models"][0].get("economics")


def _rel(before: Decimal, after: Decimal) -> float:
    return 0.0 if before <= 0 else float((after - before) / before)


# -- the law -------------------------------------------------------------------------------------------------

def decide(engine, pack, before: dict, after: dict, before_h: dict | None, after_h: dict | None, *,
           anchor: dict | None = None, downstream: list[dict] | None = None, broken_rules: list[str] | None = None,
           explore: bool = False) -> dict:
    """The verdict on one edit (or one combination, consolidation or removal): ``adopted``, every ``refusal``
    with its reason, and the figures the refinement event records under ``law``."""
    cfg = engine.config.lifecycle
    refusals: list[str] = []
    b, a, bh, ah = _score(before), _score(after), _score(before_h), _score(after_h)
    has_h = bh is not None and ah is not None
    exploratory = False
    if a < b:
        tol = Decimal(repr(cfg["stall"]["explore_tolerance"]))
        if explore and has_h and a >= b - tol:
            exploratory = True
        else:
            refusals.append(f"golden score fell {b} -> {a}")
    if not after["pass"]:
        refusals.append(f"golden after the edit does not pass: {after['summary']}")
    if has_h:
        if ah < bh:
            refusals.append(f"held-out score fell {bh} -> {ah}")
        if not after_h["pass"]:
            refusals.append(f"held-out after the edit does not pass: {after_h['summary']}")
    rig = rigor.adoption_refusals(before, after, before_h, after_h)
    refusals += [r for r in rig if not (exploratory and r.startswith("golden "))]

    # cost per useful output
    c = cfg["cost"]
    eb, ea = _econ(before), _econ(after)
    tie = a == b and (not has_h or ah == bh)
    cost = None
    efficiency = False
    if eb and ea:
        cb, ca = Decimal(eb["cost_per_case"]), Decimal(ea["cost_per_case"])
        rise = _rel(cb, ca)
        lb, la = eb["latency_ms_per_case"], ea["latency_ms_per_case"]
        lat = 0.0 if lb <= 0 else (la - lb) / lb
        cost = {"before_cost": eb["cost_per_case"], "after_cost": ea["cost_per_case"], "rise": round(rise, 6),
                "before_cost_per_pass": eb["cost_per_pass"], "after_cost_per_pass": ea["cost_per_pass"],
                "before_latency_ms": lb, "after_latency_ms": la,
                "before_iterations_to_accept": eb["iterations_to_accept"], "iterations_to_accept": ea["iterations_to_accept"]}
        if rise > c["max_cost_rise"]:
            refusals.append(f"cost per golden case rose {rise:.1%} ({cb} -> {ca}), above cost.max_cost_rise {c['max_cost_rise']:.0%}")
        elif tie and c["prefer_cheaper_on_tie"] and rise > c["tie_band"]:
            refusals.append(f"equal scores and cost per golden case up {rise:.1%} ({cb} -> {ca}): the cheaper side wins")
        faster = -lat >= c["min_efficiency_gain"] and lb - la >= c["min_latency_gain_ms"]     # a few ms is timing noise
        efficiency = tie and (-rise >= c["min_efficiency_gain"] or (faster and rise <= c["tie_band"]))

    # minimum evidence and the noise bound
    ad = cfg["adopt"]
    pg = paired(before, after)
    ph = paired(before_h, after_h) if has_h else None
    n_g = int(after["models"][0].get("counted", pg["n"]))
    n_h = int(after_h["models"][0].get("counted", ph["n"])) if has_h else 0
    small = n_g < ad["min_cases"] or (has_h and n_h < ad["min_cases"])   # no held-out set: the event already says it rests on golden
    mode = ad["small_set"] if ad["small_set"] != "auto" else ("flag" if pack.fixture else "refuse")
    if small and mode == "refuse":
        refusals.append(f"small evidence: golden {n_g} and held-out {n_h if has_h else 'no'} cases, adopt.min_cases is {ad['min_cases']}")
    strict = {"golden": ["golden"], "holdout": ["holdout"], "both": ["golden", "holdout"], "none": []}[ad["require_strict_gain_on"]]
    if not efficiency:
        for name in strict:
            p = pg if name == "golden" else ph
            if p is None:
                refusals.append(f"no held-out set: a strict gain on {name} cannot be shown")
            elif not (p["wins"] > p["losses"] and p["p"] <= ad["max_p"]):
                refusals.append(f"no gain beyond the noise bound on {name}: {p['wins']} wins, {p['losses']} losses "
                                f"(sign-test p {p['p']}, adopt.max_p {ad['max_p']}); ties keep the incumbent")

    # the generation-0 anchor
    anchor_out = None
    if anchor is not None:
        tol = Decimal(repr(cfg["anchor_tolerance"]))
        g0, h0 = Decimal(anchor["golden_score"]), anchor.get("holdout_score")
        anchor_out = {"event_id": anchor["event_id"], "golden_score": anchor["golden_score"], "holdout_score": h0, "tolerance": cfg["anchor_tolerance"]}
        if a < g0 - tol:
            refusals.append(f"golden {a} is below the generation-0 anchor {g0} (tolerance {tol})")
        if has_h and h0 is not None and ah < Decimal(h0) - tol:
            refusals.append(f"held-out {ah} is below the generation-0 anchor {h0} (tolerance {tol})")

    # the system: orchestrators that call this agent
    down = []
    for d in downstream or []:
        row = {"agent": d["agent"], "before": d["before"]["models"][0]["score"], "after": d["after"]["models"][0]["score"],
               "before_holdout": None if d.get("before_h") is None else d["before_h"]["models"][0]["score"],
               "after_holdout": None if d.get("after_h") is None else d["after_h"]["models"][0]["score"]}
        down.append(row)
        if _score(d["after"]) < _score(d["before"]) or (d["before"]["pass"] and not d["after"]["pass"]):
            refusals.append(f"downstream {d['agent']} golden fell {row['before']} -> {row['after']}: the edit breaks the system that calls it")
        if d.get("before_h") is not None and d.get("after_h") is not None and _score(d["after_h"]) < _score(d["before_h"]):
            refusals.append(f"downstream {d['agent']} held-out fell {row['before_holdout']} -> {row['after_holdout']}")

    refusals += list(broken_rules or [])
    return {"adopted": not refusals, "refusals": refusals, "exploratory": exploratory, "efficiency_gain": efficiency and not refusals,
            "evidence": {"n_golden": n_g, "n_holdout": n_h, "paired_wins": pg["wins"], "paired_losses": pg["losses"],
                         "paired_p": pg["p"], "holdout_paired_wins": None if ph is None else ph["wins"],
                         "holdout_paired_losses": None if ph is None else ph["losses"], "small_set": small,
                         "small_set_policy": mode, "min_cases": ad["min_cases"]},
            "cost": cost, "anchor": anchor_out, "downstream": down}


def best(trials: list[dict]) -> dict | None:
    """Of the trials the law adopts, the one with the highest golden score, then held-out, then the cheapest."""
    ok = [t for t in trials if t["law"]["adopted"]]
    if not ok:
        return None

    def key(t):
        h = _score(t.get("after_h"))
        cost = (t["law"]["cost"] or {}).get("after_cost")
        return (-_score(t["after"]), -(h if h is not None else Decimal(0)), Decimal(cost) if cost else Decimal(0), t["index"])
    return min(ok, key=key)


# -- the refiner's edit beyond a text replacement (engine.guardrails.edit_applies hook) ------------------------

def edit_problems(output: dict, run_input: dict) -> list[str]:
    """A manifest edit is only the deletion the crank recommended (one grounding source or memory query line,
    replaced by nothing); a consolidation replaces the whole file; the instruction ledger's rule ids
    (engine.rules) stay unique and every rule line added to a ledgered file carries one."""
    from engine import rules
    path = str(output.get("file") or "").replace("\\", "/")
    files = run_input.get("files") or {}
    old, new = output.get("old"), output.get("new")
    out = []
    if path == "manifest.yaml":
        target = run_input.get("deletion")
        if not isinstance(target, dict):
            out.append("manifest.yaml may be edited only to delete the grounding source the crank recommended")
        elif new != "" or not isinstance(old, str) or old.strip() != str(target.get("line", "")).strip():
            out.append(f"a manifest deletion replaces exactly the line {target.get('line')!r} with nothing")
        return out
    if run_input.get("mode") == "consolidate" and isinstance(old, str) and old != files.get(path):
        out.append("a consolidation rewrites the whole file: old must be the file's entire text")
    if isinstance(old, str) and isinstance(new, str) and path in files:
        out += rules.edit_problems(files[path], old, new)
    return out


# -- ramp-up to the first PASS (G-D7) ---------------------------------------------------------------------------

def record_rampup(engine, pack, agent_name: str, ev: dict) -> dict | None:
    """The first time an agent's golden eval passes: how many runs, human verdicts and loop cycles it took."""
    if not ev.get("pass") or ev.get("golden_file", "golden.jsonl") != "golden.jsonl":
        return None
    t = f"{pack.name}.rampup"
    if any(e["payload"]["agent"] == agent_name for e in engine.store.query_events(event_type=t, limit=100000)):
        return None
    runs = engine.store.list_runs(pack=pack.name, agent=agent_name)
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent_name, event_type=t,
        payload={"agent": agent_name, "runs": len(runs),
                 "human_verdicts": sum(1 for r in runs if r["human_verdict"] and (r.get("verdict_source") or "human") == "human"),
                 "cycles": len(engine.store.query_events(event_type=f"{pack.name}.cycle", limit=100000)),
                 "manifest_hash": ev.get("manifest_hash"), "score": ev["models"][0]["score"]},
        source="pipeline:eval")


# -- the crank: cost per useful output, rework, split, floor and overhead, deletion (G-M2, G-D7) --------------

def _price_split(engine, provider: str, call: dict) -> tuple[Decimal, Decimal]:
    cost = Decimal(str(call.get("cost_usd") or 0))
    tin, tout = int(call.get("input_tokens") or 0), int(call.get("output_tokens") or 0)
    try:
        pin, _ = engine.config.price_per_token(provider, call.get("model") or "")
        part = min(cost, (pin * tin).quantize(Q8))
    except EngineError:
        part = cost if tin + tout == 0 else (cost * tin / (tin + tout)).quantize(Q8)
    return part, cost - part


def run_costs(engine, row: dict) -> dict:
    """One run's cost lines: input and output of the accepted candidate's provider calls, retries (every call of a
    candidate not accepted), child runs, the floor (the accepted candidate's first provider call) and rework."""
    cands = _candidates(row)
    acc = next((c for c in cands if c.get("accepted")), None)
    own = sum((Decimal(str(p.get("cost_usd") or 0)) for c in cands for p in c.get("provider_calls") or []), Decimal(0))
    retries = sum((Decimal(str(p.get("cost_usd") or 0)) for c in cands if c is not acc for p in c.get("provider_calls") or []), Decimal(0))
    tin = tout = Decimal(0)
    for p in (acc or {}).get("provider_calls") or []:
        i, o = _price_split(engine, row["provider"], p)
        tin, tout = tin + i, tout + o
    calls = (acc or {}).get("provider_calls") or []
    iterations = sum(1 for it in row.get("iterations") or [] if it.get("candidates"))
    return {"input": tin, "output": tout, "retries": retries, "children": max(Decimal(0), Decimal(str(row["cost_usd"])) - own),
            "floor": Decimal(str(calls[0].get("cost_usd") or 0)) if calls else Decimal(0),
            "rework": iterations > 1 or len(cands) > 1, "iterations": iterations,
            "candidates": (cands.index(acc) + 1) if acc else len(cands), "accepted": acc is not None}


def _cited_refs(output) -> set[str]:
    out = set()
    if isinstance(output, dict):
        for k, v in output.items():
            if k == "ref" and isinstance(v, str):
                out.add(v)
            else:
                out |= _cited_refs(v)
    elif isinstance(output, list):
        for v in output:
            out |= _cited_refs(v)
    return out


def _source_cited(kind: str, ref: str, refs: set[str]) -> bool | None:
    prefix = {"table": f"table:{ref}:", "file": f"file:{ref}", "event_query": "event:", "agent_output": "run:"}.get(kind)
    return None if prefix is None else any(r.startswith(prefix) for r in refs)


def deletion_candidates(engine, pack, agent_name: str) -> list[dict]:
    """Grounding sources and memory event queries of the agent that no followed run (of its last 50) cites, once
    ``cost.deletion_min_followed`` followed runs exist.  Each carries the manifest line a deletion would remove
    (only when exactly one line names it)."""
    from engine.manifest import load_agent
    need = int(engine.config.lifecycle["cost"]["deletion_min_followed"])
    rows = [r for r in engine.store.list_runs(pack=pack.name, agent=agent_name, status="succeeded", verdicted=True, limit=50,
                                              newest_first=True) if r["human_verdict"] == "followed"]
    if len(rows) < max(need, 1):
        return []
    refs = set()
    for r in rows:
        refs |= _cited_refs(r["output"])
    agent = load_agent(pack, agent_name, config=engine.config)
    text = (agent.dir / "manifest.yaml").read_text(encoding="utf-8")
    sources = [(s.get("kind"), str(s.get("ref"))) for s in (agent.manifest.get("grounding") or {}).get("sources") or []]
    lt = (agent.manifest.get("memory") or {}).get("long_term") or {}
    sources += [("event_query", str(q.get("ref", q) if isinstance(q, dict) else q)) for q in lt.get("event_queries") or []]
    out = []
    for kind, ref in sources:
        if _source_cited(kind, ref, refs) is not False:
            continue
        lines = [ln for ln in text.splitlines() if ref in ln and "ref" in ln]
        out.append({"agent": agent_name, "kind": kind, "ref": ref, "followed_runs": len(rows),
                    "line": lines[0] if len(lines) == 1 else None, "runs": [r["run_id"] for r in rows[-3:]]})
    return out


def extend_report(engine, pack, week: str, runs: list[dict], report: dict) -> None:
    """The crank's economics section, ramp-up record, deletion candidates (and a rung-1 deletion recommendation
    when nothing else is recommended), then the escalation of a rung that stopped paying (engine.escalation)."""
    from engine import escalation
    from engine.guardrails import JUDGEABLE_ROLES
    judged: dict[str, Decimal] = {}
    by_id = {r["run_id"]: r for r in runs}
    for r in runs:
        rid = (r["input"] or {}).get("run_id") if r["role"] == "judge" and isinstance(r["input"], dict) else None
        if rid in by_id:
            judged[by_id[rid]["agent"]] = judged.get(by_id[rid]["agent"], Decimal(0)) + Decimal(str(r["cost_usd"]))
    econ = {}
    for name in sorted({r["agent"] for r in runs}):
        rows = [r for r in runs if r["agent"] == name]
        lines = [run_costs(engine, r) for r in rows]
        cost = sum((Decimal(str(r["cost_usd"])) for r in rows), Decimal(0))
        ok = [r for r in rows if r["status"] == "succeeded"]
        fol = [r for r in rows if r["human_verdict"] == "followed"]
        floor = sum((x["floor"] for x in lines), Decimal(0))
        judge = judged.get(name, Decimal(0))
        acc = [x for x in lines if x["accepted"]]
        econ[name] = {
            "runs": len(rows), "cost_usd": str(cost.quantize(Q8)),
            "cost_per_succeeded": None if not ok else str((cost / len(ok)).quantize(Q8)),
            "cost_per_followed": None if not fol else str(((cost + judge) / len(fol)).quantize(Q8)),
            "rework": {"runs": sum(1 for x in lines if x["rework"]), "share": str((Decimal(sum(1 for x in lines if x["rework"])) / len(rows)).quantize(Q4))},
            "split": {k: str(sum((x[k] for x in lines), Decimal(0)).quantize(Q8)) for k in ("input", "output", "retries", "children")}
                     | {"judge": str(judge.quantize(Q8))},
            "floor_cost": str(floor.quantize(Q8)),
            "overhead": None if floor <= 0 else str(((cost + judge) / floor).quantize(Q4)),
            "iterations_to_accept": None if not acc else str((Decimal(sum(x["iterations"] for x in acc)) / len(acc)).quantize(Q4)),
            "candidates_to_accept": None if not acc else str((Decimal(sum(x["candidates"] for x in acc)) / len(acc)).quantize(Q4))}
    report["economics"] = econ
    report["rampup"] = {e["payload"]["agent"]: e["payload"] for e in engine.store.query_events(event_type=f"{pack.name}.rampup", limit=100000, ascending=True)}
    from engine.config import load_yaml
    deletions = []
    for name in sorted(pack.agent_names):
        if load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role") in JUDGEABLE_ROLES:
            deletions += deletion_candidates(engine, pack, name)
    report["deletions"] = deletions
    rec = report.get("recommendation") or {}
    usable = [d for d in deletions if d["line"]]
    if rec.get("rung") is None and usable:
        d = usable[0]
        report["recommendation"] = {
            "rung": 1, "deletion": {"kind": d["kind"], "ref": d["ref"], "line": d["line"]},
            "change": (f"Rung 1 (deletion): {d['agent']}'s {d['kind']} source {d['ref']!r} is cited by none of its last "
                       f"{d['followed_runs']} followed runs. Delete it: the same answers for fewer input tokens."),
            "evidence": {"cluster": f"unused grounding {d['kind']}:{d['ref']}", "count": d["followed_runs"], "runs": d["runs"]}}
    escalation.apply(engine, pack, report)


def render_section(report: dict) -> list[str]:
    L = []
    econ = report.get("economics") or {}
    if econ:
        L += ["", "## Cost per useful output (rework, split, floor and overhead)", "",
              "| agent | runs | per succeeded | per followed | rework | input | output | retries | children | judge | floor | overhead | iterations / candidates to accept |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, e in econ.items():
            s = e["split"]
            L.append(f"| {name} | {e['runs']} | {e['cost_per_succeeded']} | {e['cost_per_followed']} | {e['rework']['runs']} ({e['rework']['share']}) | "
                     f"{s['input']} | {s['output']} | {s['retries']} | {s['children']} | {s['judge']} | {e['floor_cost']} | {e['overhead']} | "
                     f"{e['iterations_to_accept']} / {e['candidates_to_accept']} |")
    for a, r in sorted((report.get("rampup") or {}).items()):
        L.append(f"- ramp-up {a}: first golden PASS after {r['runs']} runs, {r['human_verdicts']} human verdicts, {r['cycles']} cycles")
    for d in report.get("deletions") or []:
        L.append(f"- unused grounding: {d['agent']} {d['kind']} {d['ref']!r} cited by none of {d['followed_runs']} followed runs"
                 + ("" if d["line"] else " (no single manifest line names it: delete by hand)"))
    from engine import escalation
    L += escalation.render_section(report)
    return L


# -- validate (engine.validate hook) ------------------------------------------------------------------------------

def validation(engine, pack, agents: dict) -> dict:
    """Warn when a golden or held-out set is below ``adopt.min_cases`` (an adoption on it rests on small evidence),
    report each agent's instruction ledger, and refuse a rule no case pins (``rules.require_pins``)."""
    from engine import rules
    from engine.errors import EvalError
    from engine.eval import load_golden
    cfg = engine.config.lifecycle
    warnings: dict[str, list[str]] = {}
    ledgers = {}
    for a in agents.values():
        for name in ("golden.jsonl", "holdout.jsonl"):
            p = a.dir / "eval" / name
            if p.is_file():
                n = len(load_golden(p, pack_is_fixture=pack.fixture).cases)
                if n < cfg["adopt"]["min_cases"]:
                    warnings.setdefault(a.name, []).append(f"{name} has {n} cases, below autoloop.adopt.min_cases "
                                                           f"{cfg['adopt']['min_cases']}: an adoption on it rests on small evidence")
        led = rules.ledger(pack, a.name)
        if led["rules"]:
            ledgers[a.name] = {"rules": sorted(led["rules"], key=lambda r: int(r[1:])), "pinned": sorted(led["pins"], key=lambda r: int(r[1:])),
                               "unpinned": led["unpinned"]}
        if led["unpinned"] and cfg["rules"]["require_pins"]:
            raise EvalError(f"{a.ref}: rules {led['unpinned']} are pinned by no golden case (\"pins\") and not named in problem.md")
    return {"adoption_warnings": warnings, "rule_ledger": ledgers}
