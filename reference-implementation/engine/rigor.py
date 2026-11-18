"""Eval rigor: the checks that make a golden score evidence (JH-C11 wpA).

A score is evidence only with its n and its spread, split by the kinds of task it averages over,
measured against an objective that has not silently moved, on an eval that is itself checked.
This module holds the mechanism; ``engine.eval.run_eval`` calls it and exposes its results.

- ``model_metrics``      per-model robust score, pass@1/pass@k, Wilson intervals, per-stratum scores,
                         the tier ladder (mastered / frontier / gaps), zero-signal cases
- ``objective_hash``     one hash of what the agent is scored against; ``objective_mismatch`` refuses a
                         comparison across objectives the operator has not acknowledged (``<pack>.objective``)
- ``check_controls``     negative controls: canned wrong outputs the golden comparison must fail
- ``expected_rejections`` the agent's own verifier re-run over every golden expected value
- ``history_suspects``   a case failed identically by every model is suspected of being broken
                         (``<pack>.suspect_case``); suspect cases leave the score until a human clears them
- ``adoption_refusals``  an edit that lowers pass@k or any stratum, or crosses objectives, is refused
- ``saturation``         cases passed on each of their last K runs no longer challenge the agent
- ``coverage``           which allowed tools and child agents the golden traces exercise

No clock, no randomness: ordering is the ledger's.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from engine import stats
from engine.errors import EngineError, ToolError
from engine.events import EventLog
from engine.hashing import canonical_json, sha256_json

EVAL_FILES = ("golden.jsonl", "holdout.jsonl")
Q4 = Decimal("0.0001")


def input_key(run_input) -> str:
    return canonical_json(run_input)


def _ratio(k: int, n: int) -> str:
    return str((Decimal(k) / Decimal(n)).quantize(Q4)) if n else "0.0000"


# -- per-model metrics --------------------------------------------------------------------------

def stratum_values(case: dict, key: str):
    return case.get("tier") if key == "tier" else (case.get("tags") or {}).get(key)


def tier_ladder(per_tier: dict[int, tuple[int, int]], promote_at: float) -> dict:
    """``{tier: (passed, counted)}`` -> mastered tier (every tier up to it at >= promote_at), frontier tier
    (the highest tier with a pass rate strictly between 0 and 1; failing that, the first unmastered tier) and
    gaps (zero-pass tiers more than one above the mastered one with nothing passed in between)."""
    tiers = sorted(t for t, (_, n) in per_tier.items() if n)
    rates = {t: per_tier[t][0] / per_tier[t][1] for t in tiers}
    mastered = None
    for t in tiers:
        if rates[t] < promote_at:
            break
        mastered = t
    partial = [t for t in tiers if 0.0 < rates[t] < 1.0]
    unmastered = [t for t in tiers if mastered is None or t > mastered]
    frontier = partial[-1] if partial else (unmastered[0] if unmastered else None)
    base = mastered or 0
    gaps = [t for t in tiers if rates[t] == 0.0 and t > base + 1
            and not any(per_tier[u][0] for u in tiers if base < u < t)]
    return {"mastered_tier": mastered, "frontier_tier": frontier, "gaps": gaps}


def model_metrics(cases: list[dict], *, samples: int, confidence: float, strata_keys: tuple[str, ...],
                  promote_at: float) -> dict:
    """Metrics over a model's case entries ``{id, counted, passed, passes, samples, tags, tier}``.

    ``passed`` is the robust case pass (passes / samples >= min_case_rate, decided by the caller);
    ``pass_at_1`` is the mean per-draw pass rate; ``pass_at_k`` the mean unbiased pass@k with
    k = ``samples``; every rate carries a Wilson interval."""
    counted = [c for c in cases if c["counted"]]
    passed = sum(1 for c in counted if c["passed"])
    draws = sum(c["samples"] for c in counted)
    draw_passes = sum(c["passes"] for c in counted)
    strata: dict[str, dict] = {}
    for key in tuple(strata_keys) + ("tier",):
        groups: dict = {}
        for c in counted:
            v = stratum_values(c, key)
            if v is None:
                continue
            g = groups.setdefault(json.dumps(v), [0, 0])
            g[0] += int(c["passed"])
            g[1] += 1
        if groups:
            strata[key] = {json.loads(v): {"passed": k, "counted": n, "score": _ratio(k, n), "interval": stats.rate(k, n, confidence)}
                           for v, (k, n) in sorted(groups.items())}
    per_tier = {int(t): (s["passed"], s["counted"]) for t, s in (strata.get("tier") or {}).items()}
    return {
        "samples": samples,
        "interval": stats.rate(passed, len(counted), confidence),
        "pass_at_1": str(Decimal(repr(stats.mean([c["passes"] / c["samples"] for c in counted]))).quantize(Q4)),
        "pass_at_k": str(Decimal(repr(stats.mean([stats.pass_at_k(c["samples"], c["passes"], samples) for c in counted]))).quantize(Q4)),
        "sample_interval": stats.rate(draw_passes, draws, confidence),
        "strata": strata,
        "curriculum": tier_ladder(per_tier, promote_at) if per_tier else None,
        "zero_signal": [c["id"] for c in counted if c["passes"] == 0],
    }


def weakest_stratum(strata: dict) -> dict | None:
    """The stratum value with the lowest score (ties: fewer cases first, then key order)."""
    best = None
    for key in sorted(strata):
        for value, s in strata[key].items():
            cand = (Decimal(s["score"]), s["counted"], key, json.dumps(value))
            if best is None or cand < best[0]:
                best = (cand, {"stratum": key, "value": value, "score": s["score"], "counted": s["counted"]})
    return None if best is None else best[1]


def human_delta(score: Decimal, baseline: dict | None) -> str | None:
    if not baseline:
        return None
    return str((Decimal(score) - Decimal(str(baseline["score"]))).quantize(Q4))


# -- the objective ------------------------------------------------------------------------------

def objective_hash(pack, agent) -> str:
    """Hash of what the agent is scored against: the pack's problem statement, the agent's output schema,
    each eval set's compare fields and threshold, and the verifier id.  Prompts, skills and grounding are
    not the objective: they are what the loop tunes."""
    headers = {}
    for name in EVAL_FILES:
        path = agent.dir / "eval" / name
        if path.is_file():
            first = next((ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()), None)
            if first:
                h = json.loads(first)
                headers[name] = {"compare": h.get("compare"), "threshold": str(Decimal(str(h.get("threshold"))))}
    return sha256_json({"problem": pack.problem_text, "output_schema": agent.output_schema,
                        "eval": headers, "verifier": agent.verifier})


def objective_on_record(engine, pack, agent_name: str) -> str | None:
    """The objective hash last on record for an agent: the latest of the refinement events that carry one
    and the operator's ``<pack>.objective`` acknowledgements (human-sourced only), in ledger order."""
    marks = []
    for e in engine.store.query_events(event_type=f"{pack.name}.refinement", limit=100000, ascending=True):
        if e["payload"]["agent"] == agent_name and e["payload"].get("objective_hash"):
            marks.append((e["ledger_index"], e["payload"]["objective_hash"]))
    for e in engine.store.query_events(event_type=f"{pack.name}.objective", source="human", limit=100000, ascending=True):
        if e["payload"]["agent"] == agent_name:
            marks.append((e["ledger_index"], e["payload"]["new_hash"]))
    return max(marks)[1] if marks else None


def objective_mismatch(engine, pack, agent_name: str, current: str) -> str | None:
    recorded = objective_on_record(engine, pack, agent_name)
    if recorded is None or recorded == current:
        return None
    return (f"objective-mismatch: {agent_name}'s objective is {current[:12]} but the record holds {recorded[:12]}; "
            f"scores across objectives are not compared until the operator records a <pack>.objective event")


def record_objective(engine, pack, agent, why: str) -> dict:
    """The operator acknowledges a change of objective (never the loop: the source is human)."""
    if not why or not why.strip():
        raise EngineError("an objective change needs a reason")
    new = objective_hash(pack, agent)
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent.name, event_type=f"{pack.name}.objective",
        payload={"agent": agent.name, "old_hash": objective_on_record(engine, pack, agent.name), "new_hash": new,
                 "why": why.strip()[:1000]}, source="human")


# -- eval integrity: negative controls and the verifier re-audit ---------------------------------

def check_controls(golden, passes_fn) -> dict:
    """Score every negative control against its case; a control the comparison lets pass means the
    golden set cannot tell a wrong answer from a right one."""
    by_id = {c.id: c for c in golden.cases}
    failed, passed = [], []
    for ctl in golden.controls:
        ok, _ = passes_fn(ctl["output"], by_id[ctl["case"]].expected, golden.compare)
        (passed if ok else failed).append(ctl["id"])
    return {"declared": len(golden.controls), "failed_as_expected": failed, "passed": passed}


def expected_rejections(engine, pack, agent, cases) -> list[dict]:
    """Run the agent's verifier over every case's expected value; a case its own check rejects is broken."""
    if not agent.verifier:
        return []
    from engine.citations import CitationResolver
    from engine.verify import VerifyContext
    resolver = CitationResolver(engine=engine, pack=pack, access=agent.access, kinds=engine.config.citation_kinds)
    out = []
    for case in cases:
        vctx = VerifyContext(pack=pack, agent=agent, run_input=case.input, resolver=resolver, read_table=pack.table_rows)
        try:
            res = pack.verifiers.run(agent.verifier, dict(case.expected), vctx)
        except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation, ToolError):
            continue                       # the expected value holds only compare fields the verifier cannot read
        if not res.certified:
            out.append({"case_id": case.id, "violations": list(res.violations)})
    return out


def record_integrity(engine, pack, agent_name: str, golden_file: str, controls: dict, rejected: list[dict]) -> dict:
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.eval_integrity",
        payload={"agent": agent_name, "golden_file": golden_file, "controls_failed_as_expected": controls["failed_as_expected"],
                 "controls_passed": controls["passed"], "golden_cases_rejected_by_checks": rejected},
        source="pipeline:eval")


# -- suspect cases ---------------------------------------------------------------------------------

def suspect_state(engine, pack, agent_name: str, golden_file: str) -> tuple[dict[str, str], dict[str, int]]:
    """(open suspects {case_id: reason}, last clearance ledger index {case_id: index})."""
    open_, cleared = {}, {}
    for e in engine.store.query_events(event_type=f"{pack.name}.suspect_case", limit=100000, ascending=True):
        p = e["payload"]
        if p["agent"] != agent_name or p["golden_file"] != golden_file:
            continue
        if p["cleared"]:
            open_.pop(p["case_id"], None)
            cleared[p["case_id"]] = e["ledger_index"]
        else:
            open_[p["case_id"]] = p["reason"]
    return open_, cleared


def _failure_signature(row: dict, expected: dict, compare, passes_fn) -> tuple[bool, str]:
    if row["output"] is not None:
        ok, diffs = passes_fn(row["output"], expected, compare)
        return ok, "|".join(diffs)
    from engine.crank import _cluster_key
    reasons = row.get("failure_reasons") or [""]
    return False, f"{row['status']}: {_cluster_key(reasons[0].split(': ', 1)[-1])}"


def history_suspects(engine, pack, agent_name: str, cases, compare, passes_fn, cleared: dict[str, int],
                     min_evals: int) -> dict[str, str]:
    """A case failed with one identical signature by two or more models over at least ``min_evals`` runs
    (since its last clearance) is suspect: when every model fails it the same way, the case is the likelier fault."""
    by_input: dict[str, list[dict]] = {}
    from engine.experiment import is_experiment_run
    for r in engine.store.list_runs(pack=pack.name, agent=agent_name):
        if not is_experiment_run(r):                 # a variant's or a probe's failure says nothing about the case (wpC)
            by_input.setdefault(input_key(r["input"]), []).append(r)
    out = {}
    for case in cases:
        rows = [r for r in by_input.get(input_key(case.input), []) if r["ledger_index"] > cleared.get(case.id, -1)]
        if len(rows) < min_evals:
            continue
        models = {f"{r['provider']}/{r['model']}" for r in rows}
        sigs = set()
        for r in rows:
            ok, sig = _failure_signature(r, case.expected, compare, passes_fn)
            if ok:
                sigs = None
                break
            sigs.add(sig)
        if sigs is not None and len(models) >= 2 and len(sigs) == 1:
            out[case.id] = f"failed identically by {len(models)} models over {len(rows)} runs: {next(iter(sigs))[:300]}"
    return out


def flag_suspect(engine, pack, agent_name: str, golden_file: str, case_id: str, reason: str) -> dict:
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.suspect_case",
        payload={"agent": agent_name, "golden_file": golden_file, "case_id": case_id, "reason": reason[:1000], "cleared": False},
        source="pipeline:eval")


def clear_suspect(engine, pack, agent_name: str, golden_file: str, case_id: str, why: str) -> dict:
    """A human looked at the case (and rebuilt it if it was broken): it counts again, and only runs after
    this clearance can make it suspect again."""
    if not why or not why.strip():
        raise EngineError("clearing a suspect case needs a reason")
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.suspect_case",
        payload={"agent": agent_name, "golden_file": golden_file, "case_id": case_id, "reason": why.strip()[:1000], "cleared": True},
        source="human")


# -- coverage --------------------------------------------------------------------------------------

def tools_called(row: dict) -> set[str]:
    """Tools the model itself called (origin ``agent``); grounding and memory reads the engine makes for it do not count."""
    out = set()
    for it in row.get("iterations") or []:
        for cand in it.get("candidates") or []:
            for call in cand.get("tool_calls") or []:
                if call.get("origin", "agent") == "agent":
                    out.add(call["tool"])
    return out


def coverage(allowed: tuple[str, ...], cases: list[dict]) -> dict:
    """Which allowed tools (child agents are ``agent.<pack>.<name>`` tools) the golden traces exercised."""
    used = {t: sorted(c["id"] for c in cases if t in c.get("tools", ())) for t in allowed}
    return {"tools": used, "uncovered": sorted(t for t, ids in used.items() if not ids),
            "declared_unexercised": sorted({t for c in cases for t in c.get("exercises", ()) if t not in c.get("tools", ())})}


def declared_uncovered(allowed: tuple[str, ...], golden) -> list[str]:
    declared = {t for c in golden.cases for t in c.exercises}
    return sorted(t for t in allowed if t not in declared)


def hard_tier_problem(golden, hard_tier: int, min_share: float) -> str | None:
    n = len(golden.cases)
    hard = sum(1 for c in golden.cases if (c.tier or 0) >= hard_tier)
    if n and hard / n >= min_share:
        return None
    return f"{hard} of {n} cases are at tier >= {hard_tier}; a real golden set needs at least {min_share:.0%} hard cases"


# -- adoption ----------------------------------------------------------------------------------------

def adoption_refusals(before: dict, after: dict, before_holdout: dict | None, after_holdout: dict | None) -> list[str]:
    """Why an edit may not be adopted on top of the score rule: a different objective, a fall in pass@k
    (the edit wins draws by luck, not on every case), or a fall in any stratum with enough cases even when
    the total rises."""
    out = []
    pairs = [("golden", before, after)]
    if before_holdout is not None and after_holdout is not None:
        pairs.append(("held-out", before_holdout, after_holdout))
    for label, b, a in pairs:
        bo, ao = b.get("objective_hash"), a.get("objective_hash")
        if bo and ao and bo != ao:
            out.append(f"objective-mismatch on {label}: before {bo[:12]} after {ao[:12]}")
        bm, am = b["models"][0], a["models"][0]
        if "pass_at_k" in bm and "pass_at_k" in am and Decimal(am["pass_at_k"]) < Decimal(bm["pass_at_k"]):
            out.append(f"{label} pass@{bm.get('samples', 'k')} fell {bm['pass_at_k']} -> {am['pass_at_k']}")
        min_cases = int(b.get("min_stratum_cases", 0) or 0)
        for key, values in sorted((bm.get("strata") or {}).items()):
            for value, s in values.items():
                s2 = ((am.get("strata") or {}).get(key) or {}).get(value)
                if s2 is not None and s["counted"] >= max(min_cases, 1) and Decimal(s2["score"]) < Decimal(s["score"]):
                    out.append(f"{label} stratum {key}={value} fell {s['score']} -> {s2['score']} ({s['counted']} cases)")
    return out


def tier_gaps(teacher: dict, student: dict, max_gap: float) -> dict | None:
    """Teacher minus student score per tier (eval model rows).  A gap above ``max_gap`` at any tier says the
    student is a rung too far: distil an intermediate student first."""
    tiers = (teacher.get("strata") or {}).get("tier")
    if not tiers:
        return None
    s_tiers = (student.get("strata") or {}).get("tier") or {}
    per = {t: str((Decimal(s["score"]) - Decimal((s_tiers.get(t) or {"score": "0"})["score"])).quantize(Q4)) for t, s in tiers.items()}
    return {"per_tier": per, "max_gap": max_gap, "suggest_intermediate": any(Decimal(g) > Decimal(repr(max_gap)) for g in per.values())}


# -- saturation ----------------------------------------------------------------------------------------

def saturation(engine, pack, agent_name: str, cases, compare, passes_fn, *, k: int, max_share: float) -> dict:
    """A case passed on each of its last ``k`` runs is saturated; above ``max_share`` saturated the set no longer
    challenges the agent and harder cases are wanted: the inputs the agent failed on that are not cases yet
    are listed for the operator (marked followed, they become golden through the loop's growth step)."""
    by_input: dict[str, list[dict]] = {}
    rows = engine.store.list_runs(pack=pack.name, agent=agent_name)
    for r in rows:
        by_input.setdefault(input_key(r["input"]), []).append(r)
    saturated = []
    for case in cases:
        last = by_input.get(input_key(case.input), [])[-k:]
        if len(last) == k and all(_failure_signature(r, case.expected, compare, passes_fn)[0] for r in last):
            saturated.append(case.id)
    known = {input_key(c.input) for c in cases}
    candidates, seen = [], set()
    for r in reversed(rows):
        key = input_key(r["input"])
        if r["status"] != "succeeded" and key not in known and key not in seen:
            seen.add(key)
            candidates.append({"input": r["input"], "run_id": r["run_id"], "status": r["status"]})
        if len(candidates) >= 10:
            break
    share = len(saturated) / len(cases) if cases else 0.0
    return {"saturated": saturated, "cases": len(cases), "share": _ratio(len(saturated), len(cases)),
            "flagged": bool(cases) and share > max_share, "hard_case_candidates": candidates}


def record_saturation(engine, pack, agent_name: str, sat: dict) -> dict:
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.saturation",
        payload={"agent": agent_name, "saturated": sat["saturated"], "cases": sat["cases"], "share": sat["share"],
                 "hard_case_candidates": sat["hard_case_candidates"]}, source="pipeline:eval")


# -- the operator's two records ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """python -m engine.rigor objective <pack>/<agent> --why TEXT [--db DSN]
       python -m engine.rigor clear-suspect <pack>/<agent> <case_id> --why TEXT [--file golden.jsonl] [--db DSN]"""
    import argparse
    import sys
    from engine.manifest import load_agent
    from engine.packs import load_pack, parse_agent_ref
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.rigor")
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("objective", help="acknowledge a changed objective (problem, output schema, compare, threshold, verifier)")
    o.add_argument("agent_ref")
    c = sub.add_parser("clear-suspect", help="a human looked at a suspect case: it counts again")
    c.add_argument("agent_ref")
    c.add_argument("case_id")
    c.add_argument("--file", default="golden.jsonl", choices=list(EVAL_FILES))
    for s in (o, c):
        s.add_argument("--why", required=True)
        s.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            if args.cmd == "objective":
                ev = record_objective(engine, pack, load_agent(pack, agent_name, config=engine.config), args.why)
                print(f"objective of {args.agent_ref} recorded: {ev['payload']['old_hash']} -> {ev['payload']['new_hash']} (event {ev['event_id']})")
            else:
                ev = clear_suspect(engine, pack, agent_name, args.file, args.case_id, args.why)
                print(f"suspect case {args.case_id} of {args.agent_ref} cleared (event {ev['event_id']})")
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
