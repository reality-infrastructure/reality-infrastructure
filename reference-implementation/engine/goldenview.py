"""The golden view of the record: an agent's runs on golden and held-out inputs, scored against the
expected values, split by stratum and tier (JH-C11 wpA).

``run_eval`` measures by running; this measures what already ran (the week's runs for the crank, all of
an agent's runs for the curriculum), with the same metrics (``engine.rigor.model_metrics``): the
weakest stratum per agent, the tier ladder, and the score beside the operator's own baseline.
"""

from __future__ import annotations

from decimal import Decimal

from engine.eval import case_passes, load_golden
from engine.rigor import EVAL_FILES, human_delta, input_key, model_metrics, weakest_stratum


def _cases(pack, agent: str) -> tuple[dict, dict | None]:
    """({canonical input: (case, compare)}, the golden header's human baseline)."""
    by_key, baseline = {}, None
    for name in EVAL_FILES:
        path = pack.agent_dir(agent) / "eval" / name
        if not path.is_file():
            continue
        g = load_golden(path, pack_is_fixture=pack.fixture)
        if name == "golden.jsonl":
            baseline = g.human_baseline
        for c in g.cases:
            by_key[input_key(c.input)] = (c, g.compare)
    return by_key, baseline


def value_weights(pack, agent: str) -> dict[str, float]:
    """{canonical input: tags.value_weight} for the agent's cases that declare one."""
    by_key, _ = _cases(pack, agent)
    return {k: float(c.tags["value_weight"]) for k, (c, _) in by_key.items() if "value_weight" in c.tags}


def golden_view(engine, pack, agent: str, runs: list[dict]) -> dict | None:
    """None when the agent has no eval set or none of ``runs`` touched one of its inputs."""
    by_key, baseline = _cases(pack, agent)
    if not by_key:
        return None
    cfg = engine.config.eval_rigor
    entries: dict[str, dict] = {}
    for r in runs:
        if r["agent"] != agent:
            continue
        hit = by_key.get(input_key(r["input"]))
        if hit is None:
            continue
        case, compare = hit
        ok, _ = case_passes(r["output"], case.expected, compare)
        e = entries.setdefault(input_key(case.input), {"id": case.id, "counted": pack.fixture or not case.fixture,
                                                        "passes": 0, "samples": 0, "tags": dict(case.tags), "tier": case.tier})
        e["passes"] += int(ok)
        e["samples"] += 1
    if not entries:
        return None
    for e in entries.values():
        e["passed"] = e["passes"] / e["samples"] >= cfg["min_case_rate"]
    cases = [entries[k] for k in sorted(entries)]
    m = model_metrics(cases, samples=1, confidence=engine.config.stats["confidence"], strata_keys=cfg["strata"],
                      promote_at=engine.config.curriculum["promote_at"])
    counted = [c for c in cases if c["counted"]]
    passed = sum(1 for c in counted if c["passed"])
    score = (Decimal(passed) / len(counted)).quantize(Decimal("0.0001")) if counted else Decimal(0)
    return {"cases_seen": len(cases), "passed": passed, "counted": len(counted), "score": str(score),
            "interval": m["interval"], "strata": m["strata"], "curriculum": m["curriculum"],
            "weakest_stratum": weakest_stratum(m["strata"]),
            "human_baseline": baseline, "human_delta": human_delta(score, baseline) if counted else None}
