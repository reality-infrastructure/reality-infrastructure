"""The curator: a loop role that synthesises practice cases; code admits only the correct, discriminating ones.

    python -m engine.curate confirm <pack>/<agent> <case_id> --reason "..." [--db DSN]

Golden sets otherwise grow only from runs the operator marked followed.  Each cycle the pack's
``curator`` (role ``curator``: frontier-only, no verifier, guardrail ``case_certified``) proposes up
to ``autoloop.curate.max_cases_per_cycle`` new cases (input + expected output) for one agent.  Code
then decides, case by case:

  correct        the agent's own verifier certifies the expected output on that input; an agent
                 without a verifier cannot have a case admitted by code, so the case waits in
                 ``eval/proposed.jsonl`` for the operator (``confirm``)
  discriminating the case is run ``attempts`` times on the agent's own model plus once per model in
                 its latest eval matrix; the fail fraction is its difficulty, and it is admitted
                 only inside ``[min_fail, max_fail]`` (a case everyone passes teaches nothing; one
                 no one passes is not yet reachable)

An admitted case is appended to ``eval/golden.jsonl`` (never ``holdout.jsonl``) with
``provenance: synthesised by curator run <id>``, its ``difficulty`` and a ``tier``; every proposal
is a ``<pack>.case_proposed`` event, so the curator's reward history (admitted / proposed, mean
difficulty) is on the record, and adoption reports the golden score per tier.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.citations import CitationResolver
from engine.config import load_yaml
from engine.errors import EngineError
from engine.eval import case_passes, load_golden
from engine.events import EventLog
from engine.guardrails import JUDGEABLE_ROLES
from engine.providers import parse_model_string
from engine.verify import VerifyContext

TIERS = ((1 / 3, "easy"), (2 / 3, "medium"), (1.01, "hard"))
SEED_TIER = "seed"


def tier_of(difficulty: float) -> str:
    return next(name for bound, name in TIERS if difficulty < bound)


def _cases(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines[1:]] if path.name != "proposed.jsonl" else [json.loads(ln) for ln in lines]


def target_agent(pack, refined: str | None) -> str | None:
    """The agent the refine step worked on, else the first agent with a golden set and a verifier, else with a golden set."""
    eligible = []
    for name in sorted(pack.agent_names):
        m = load_yaml(pack.agent_dir(name) / "manifest.yaml")
        if m.get("role") in JUDGEABLE_ROLES and (pack.agent_dir(name) / "eval" / "golden.jsonl").is_file():
            eligible.append((name, m["safeguards"].get("verifier") is not None))
    names = [n for n, _ in eligible]
    if refined in names:
        return refined
    with_verifier = [n for n, v in eligible if v]
    return (with_verifier or names or [None])[0]


def _attempt_models(agent) -> list[str]:
    own = agent.model.model_string
    files = sorted((agent.dir / "eval").glob("matrix-*.json"))
    others = []
    if files:
        others = [r["model"] for r in json.loads(files[-1].read_text(encoding="utf-8")).get("models", []) if r["model"] != own]
    return [own] + sorted(set(others))


def curate(engine, pack, runner, curator: str, agent_name: str) -> dict:
    cfg = engine.config.autoloop_long_horizon["curate"]
    agent = runner.agent(agent_name)
    gpath, hpath = agent.dir / "eval" / "golden.jsonl", agent.dir / "eval" / "holdout.jsonl"
    golden = load_golden(gpath, pack_is_fixture=pack.fixture)
    known = sorted({json.dumps(c["input"], sort_keys=True) for c in _cases(gpath) + _cases(hpath) + _cases(agent.dir / "eval" / "proposed.jsonl")})
    r = runner.run(curator, {"agent": agent_name, "role": agent.role, "compare": list(golden.compare), "threshold": str(golden.threshold),
                             "max_cases": cfg["max_cases_per_cycle"], "known_inputs": known, "verifier": agent.verifier is not None,
                             "band": [cfg["min_fail"], cfg["max_fail"]],
                             "examples": [{"input": c.input, "expected": c.expected} for c in golden.cases[:3]]})
    if r.status != "succeeded":
        return {"status": "curator_failed", "agent": agent_name, "curator_run_id": r.run_id, "failure_reasons": list(r.failure_reasons)}
    models = _attempt_models(agent)
    plan = [models[0]] * max(1, cfg["attempts"]) + models[1:]
    log = EventLog(engine, pack)
    resolver = CitationResolver(engine=engine, pack=pack, access=agent.access, kinds=engine.config.citation_kinds)
    roots = sorted({f.split(".")[0] for f in golden.compare})
    admitted, queued, cases = [], [], []
    for c in r.output["cases"]:
        correct = None
        if agent.verifier is not None:
            vctx = VerifyContext(pack=pack, agent=agent, run_input=c["input"], resolver=resolver, read_table=pack.table_rows)
            res = pack.verifiers.run(agent.verifier, c["expected"], vctx)
            correct = res.certified
        difficulty, fails = None, 0
        if correct is not False:
            for ms in plan:
                try:
                    out = runner.run(agent_name, c["input"], model_override=parse_model_string(ms), enforce_economics=False)
                    ok = out.status == "succeeded" and case_passes(out.output, c["expected"], golden.compare)[0]
                except EngineError:
                    ok = False
                fails += int(not ok)
            difficulty = round(fails / len(plan), 4)
        in_band = difficulty is not None and cfg["min_fail"] <= difficulty <= cfg["max_fail"]
        tier = None if difficulty is None else tier_of(difficulty)
        case_id = f"cur-{r.run_id[:8]}-{c['id']}"
        entry = {"id": case_id, "input": c["input"], "expected": {k: c["expected"][k] for k in roots},
                 "difficulty": difficulty, "tier": tier}
        if correct is False:
            why = "the agent's verifier does not certify the expected output"
        elif not in_band:
            why = f"difficulty {difficulty} outside [{cfg['min_fail']}, {cfg['max_fail']}]: not discriminating"
        elif correct is None:
            why = "no verifier: the expected output awaits the operator (engine.curate confirm)"
            queued.append({**entry, "curator_run_id": r.run_id, "why": c["why"]})
        else:
            why = f"verifier certified; failed {fails} of {len(plan)} attempts across {len(models)} model(s)"
            admitted.append({**entry, "provenance": f"synthesised by curator run {r.run_id}: {why}"})
        log.append(entity_type="agent_run", entity_id=r.run_id, event_type=f"{pack.name}.case_proposed",
                   payload={"curator_run_id": r.run_id, "agent": agent_name, "case_id": case_id, "correct": correct,
                            "difficulty": difficulty, "attempts": len(plan) if difficulty is not None else 0,
                            "admitted": bool(correct and in_band), "tier": tier, "why": why},
                   source=f"agent:{curator}", source_ref=r.run_id)
        cases.append({"case_id": case_id, "correct": correct, "difficulty": difficulty, "tier": tier,
                      "admitted": bool(correct and in_band), "queued": correct is None and in_band, "why": why})
    _append(gpath, admitted)
    _append(agent.dir / "eval" / "proposed.jsonl", queued)
    return {"status": "curated", "agent": agent_name, "curator_run_id": r.run_id, "models": models, "cases": cases,
            "admitted": [a["id"] for a in admitted], "queued": [q["id"] for q in queued]}


def _append(path: Path, rows: list[dict]) -> None:
    if rows:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True) + "\n")


def confirm(engine, pack, agent_name: str, case_id: str, reason: str) -> dict:
    """The operator certifies a queued case's expected output; it moves from proposed.jsonl into the golden set."""
    if not reason.strip():
        raise EngineError("a confirmation needs a reason")
    edir = pack.agent_dir(agent_name) / "eval"
    queue = _cases(edir / "proposed.jsonl")
    hit = [q for q in queue if q["id"] == case_id]
    if not hit:
        raise EngineError(f"no proposed case {case_id!r} for {agent_name}")
    q = hit[0]
    case = {"id": q["id"], "input": q["input"], "expected": q["expected"], "difficulty": q["difficulty"], "tier": q["tier"],
            "provenance": f"synthesised by curator run {q['curator_run_id']}; expected output confirmed by the operator: {reason.strip()}"}
    _append(edir / "golden.jsonl", [case])
    rest = [x for x in queue if x["id"] != case_id]
    (edir / "proposed.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in rest), encoding="utf-8", newline="\n")
    EventLog(engine, pack).append(entity_type="agent_run", entity_id=q["curator_run_id"], event_type=f"{pack.name}.case_proposed",
                                  payload={"curator_run_id": q["curator_run_id"], "agent": agent_name, "case_id": case_id, "correct": True,
                                           "difficulty": q["difficulty"], "attempts": 0, "admitted": True, "tier": q["tier"],
                                           "why": f"confirmed by the operator: {reason.strip()}"},
                                  source="human", source_ref=q["curator_run_id"])
    return case


def record(engine, pack) -> dict:
    """The curator's reward history: cases proposed, admitted, and the difficulty of what it got in."""
    evs = engine.store.query_events(event_type=f"{pack.name}.case_proposed", limit=1_000_000, ascending=True)
    if not evs:
        return {}
    proposed = {e["payload"]["case_id"]: e["payload"] for e in evs}
    admitted = {e["payload"]["case_id"]: e["payload"] for e in evs if e["payload"]["admitted"]}
    diffs = [p["difficulty"] for p in admitted.values() if p["difficulty"] is not None]
    by_tier: dict[str, int] = {}
    for p in admitted.values():
        by_tier[p["tier"] or SEED_TIER] = by_tier.get(p["tier"] or SEED_TIER, 0) + 1
    return {"proposed": len(proposed), "admitted": len(admitted), "admit_rate": round(len(admitted) / len(proposed), 4),
            "mean_difficulty": None if not diffs else round(sum(diffs) / len(diffs), 4), "by_tier": dict(sorted(by_tier.items()))}


def tier_scores(pack, agent_name: str, eval_result: dict, golden_file: str = "golden.jsonl") -> dict[str, str]:
    """``{tier: "passed/counted"}`` of one eval, so adoption shows whether a gain on easy cases carries to hard ones."""
    tiers = {str(c["id"]): c.get("tier") or SEED_TIER for c in _cases(pack.agent_dir(agent_name) / "eval" / golden_file)}
    acc: dict[str, list[int]] = {}
    for c in eval_result["models"][0]["cases"]:
        if c["counted"]:
            a = acc.setdefault(tiers.get(c["id"], SEED_TIER), [0, 0])
            a[0] += int(c["passed"])
            a[1] += 1
    return {t: f"{p}/{n}" for t, (p, n) in sorted(acc.items())}


def render_section(section: dict) -> list[str]:
    if not section:
        return []
    return ["", "## Curator (synthesised cases)", "",
            f"proposed {section['proposed']}, admitted {section['admitted']} ({section['admit_rate']:.0%}); "
            f"mean difficulty of admitted {section['mean_difficulty']}; by tier {section['by_tier']}"]


def main(argv: list[str] | None = None) -> int:
    from engine.packs import load_pack, parse_agent_ref
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.curate")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("confirm")
    c.add_argument("agent_ref")
    c.add_argument("case_id")
    c.add_argument("--reason", required=True)
    c.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            case = confirm(engine, load_pack(pack_name), agent_name, args.case_id, args.reason)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"confirmed {case['id']} into {agent_name}'s golden set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
