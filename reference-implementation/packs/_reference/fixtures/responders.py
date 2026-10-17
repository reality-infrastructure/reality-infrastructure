"""Fixture models: deterministic responders standing in for an LLM.

Each responder has the Responder signature
``(model, system, messages, tools, candidate_index) -> Completion`` and speaks
the same neutral message protocol a real provider does: it reads the JSON
context from the first user message, may call tools, and finishes by calling
``engine__submit``.  Faulty variants exist on purpose so the engine's failure
paths are proven.  None of this is agent behavior for a real domain.
"""

from __future__ import annotations

import json
from decimal import Decimal

from engine.providers import Completion, ToolUse, Usage

from _reference.tools.arith import evaluate

SUBMIT = "engine__submit"


# ---------------------------------------------------------------------------
# protocol helpers
# ---------------------------------------------------------------------------

def _context(messages: list[dict]) -> dict:
    return json.loads(messages[0]["content"][0]["text"])["context"]


def _turn(messages: list[dict]) -> int:
    return sum(1 for m in messages if m["role"] == "assistant")


def _tool_results(messages: list[dict]) -> list[dict]:
    """All tool results so far, in order, parsed (errors come back as {"error": ...})."""
    out = []
    for m in messages:
        if m["role"] != "user":
            continue
        for b in m["content"]:
            if b["type"] == "tool_result":
                try:
                    out.append(json.loads(b["content"]))
                except json.JSONDecodeError:
                    out.append({"error": b["content"]})
    return out


def _usage(messages: list[dict]) -> Usage:
    return Usage(input_tokens=len(json.dumps(messages)) // 4, output_tokens=64)


def _calls(messages: list[dict], calls: list[tuple[str, dict]], text: str = "") -> Completion:
    uses = tuple(ToolUse(id=f"t{_turn(messages)}-{i}", name=name, input=args)
                 for i, (name, args) in enumerate(calls))
    return Completion(text=text, tool_uses=uses, stop_reason="tool_use", usage=_usage(messages), model="")


def _submit(messages: list[dict], output: dict, extra_calls: list[tuple[str, dict]] | None = None) -> Completion:
    calls = list(extra_calls or []) + [(SUBMIT, output)]
    return _calls(messages, calls)


def _number(s) -> int | float:
    d = Decimal(str(s))
    return int(d) if d == d.to_integral_value() else float(d)


def _grounding(ctx: dict, kind: str, ref: str) -> list:
    for g in ctx["grounding"]:
        if g["kind"] == kind and g["ref"] == ref:
            return g["data"]
    return []


# ---------------------------------------------------------------------------
# checker (worker): arithmetic sheet QA
# ---------------------------------------------------------------------------

def _sheet_rows(ctx: dict) -> list[dict]:
    sheet_id = ctx["input"]["sheet_id"]
    return [r for r in _grounding(ctx, "table", "sheets") if r["sheet_id"] == sheet_id]


def _checker_items(rows: list[dict], values: dict[str, str]) -> list[dict]:
    items = []
    for r in rows:
        recomputed = _number(values[r["expression"]])
        items.append({
            "row_id": r["id"],
            "claimed": _number(r["claimed"]),
            "recomputed": recomputed,
            "flag": Decimal(str(r["claimed"])) != Decimal(str(recomputed)),
            "citations": [{"ref": f"table:sheets:{r['id']}", "field": "claimed"}],
        })
    return items


def checker_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    """Uses the arithmetic tool for every row, logs a sheet_checked event, submits."""
    ctx = _context(messages)
    rows = _sheet_rows(ctx)
    if _turn(messages) == 0:
        return _calls(messages, [("_reference__arith__eval", {"expression": r["expression"]}) for r in rows])
    values = {res["expression"]: res["value"] for res in _tool_results(messages) if "expression" in res}
    items = _checker_items(rows, values)
    output = {"sheet_id": ctx["input"]["sheet_id"], "items": items, "confidence": 0.95}
    flagged = [i["row_id"] for i in items if i["flag"]]
    return _submit(messages, output, [("events__append", {
        "entity_type": "sheet", "entity_id": ctx["input"]["sheet_id"],
        "event_type": "_reference.sheet_checked",
        "payload": {"sheet_id": ctx["input"]["sheet_id"], "flagged": len(flagged), "row_ids": flagged}})])


def checker_v2(*, model, system, messages, tools, candidate_index) -> Completion:
    """A 'different model': no tool calls, computes in one turn, lower stated confidence."""
    ctx = _context(messages)
    rows = _sheet_rows(ctx)
    values = {r["expression"]: str(evaluate(r["expression"])) for r in rows}
    return _submit(messages, {"sheet_id": ctx["input"]["sheet_id"],
                              "items": _checker_items(rows, values), "confidence": 0.6})


def checker_malformed(*, model, system, messages, tools, candidate_index) -> Completion:
    """Confidently submits garbage: wrong types and an invented key."""
    ctx = _context(messages)
    return _submit(messages, {"sheet_id": ctx["input"]["sheet_id"], "items": "all fine",
                              "bogus": True, "confidence": 0.99})


def checker_snoop(*, model, system, messages, tools, candidate_index) -> Completion:
    """Reads a table the checker is not granted (fails closed with access_denied)."""
    if _turn(messages) == 0:
        return _calls(messages, [("tables__read", {"table": "candidates"})])
    ctx = _context(messages)
    return _submit(messages, {"sheet_id": ctx["input"]["sheet_id"], "items": [], "confidence": 0.5})


# ---------------------------------------------------------------------------
# allocator (specialist): knapsack
# ---------------------------------------------------------------------------

def _candidates(ctx: dict) -> list[dict]:
    return sorted(_grounding(ctx, "table", "candidates"), key=lambda r: r["id"])


def _dp_optimum(rows: list[dict], capacity: int) -> list[str]:
    best: list[tuple[int, tuple[str, ...]]] = [(0, ())] * (capacity + 1)
    for r in rows:
        w, v = int(r["weight"]), int(r["value"])
        for c in range(capacity, w - 1, -1):
            cand_v = best[c - w][0] + v
            cand_ids = best[c - w][1] + (r["id"],)
            if cand_v > best[c][0] or (cand_v == best[c][0] and cand_ids < best[c][1]):
                best[c] = (cand_v, cand_ids)
    return sorted(best[capacity][1])


def _greedy(rows: list[dict], capacity: int) -> list[str]:
    chosen, used = [], 0
    for r in sorted(rows, key=lambda r: (-(Decimal(r["value"]) / Decimal(r["weight"])), r["id"])):
        if used + int(r["weight"]) <= capacity:
            chosen.append(r["id"])
            used += int(r["weight"])
    return sorted(chosen)


def _allocation(rows: list[dict], selected: list[str], *, value_delta: int = 0, confidence: float) -> dict:
    by_id = {r["id"]: r for r in rows}
    items = [{"id": i, "weight": _number(by_id[i]["weight"]), "value": _number(by_id[i]["value"]),
              "citations": [{"ref": f"table:candidates:{i}", "field": "weight"},
                            {"ref": f"table:candidates:{i}", "field": "value"}]} for i in selected]
    return {
        "selected": list(selected),
        "items": items,
        "total_weight": sum(int(by_id[i]["weight"]) for i in selected),
        "total_value": sum(int(by_id[i]["value"]) for i in selected) + value_delta,
        "explanation": f"chose {len(selected)} of {len(rows)} candidates",
        "confidence": confidence,
    }


def allocator_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    ctx = _context(messages)
    rows = _candidates(ctx)
    cap = int(ctx["input"]["capacity"])
    return _submit(messages, _allocation(rows, _dp_optimum(rows, cap), confidence=0.9))


def allocator_greedy(*, model, system, messages, tools, candidate_index) -> Completion:
    """A cheaper 'model' that is sometimes suboptimal; the verifier catches it."""
    ctx = _context(messages)
    rows = _candidates(ctx)
    cap = int(ctx["input"]["capacity"])
    return _submit(messages, _allocation(rows, _greedy(rows, cap), confidence=0.9))


def allocator_infeasible(*, model, system, messages, tools, candidate_index) -> Completion:
    ctx = _context(messages)
    rows = _candidates(ctx)
    return _submit(messages, _allocation(rows, [r["id"] for r in rows], confidence=0.95))


def allocator_misstated(*, model, system, messages, tools, candidate_index) -> Completion:
    ctx = _context(messages)
    rows = _candidates(ctx)
    cap = int(ctx["input"]["capacity"])
    return _submit(messages, _allocation(rows, _dp_optimum(rows, cap), value_delta=1, confidence=0.95))


# ---------------------------------------------------------------------------
# briefer (orchestrator): calls the specialist, cites its figures, never computes
# ---------------------------------------------------------------------------

def briefer_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    ctx = _context(messages)
    if _turn(messages) == 0:
        return _calls(messages, [("agent___reference__allocator",
                                  {"input": {"capacity": ctx["input"]["capacity"]}})])
    result = _tool_results(messages)[-1]
    records = _grounding(ctx, "event_query", "event_type=_reference.record_observed")
    sources = [{"ref": f"event:events:{e['event_id']}"} for e in records]
    if result.get("status") != "succeeded":
        return _submit(messages, {"headline": "allocation not certified", "figures": [],
                                  "citations": sources, "confidence": 0.2})
    out, rid = result["output"], result["run_id"]
    figures = [
        {"name": "total_value", "value": out["total_value"],
         "citations": [{"ref": f"run:agent_runs:{rid}", "field": "total_value"}]},
        {"name": "total_weight", "value": out["total_weight"],
         "citations": [{"ref": f"run:agent_runs:{rid}", "field": "total_weight"}]},
    ]
    headline = (f"total_value={out['total_value']} total_weight={out['total_weight']} "
                f"selected={len(out['selected'])} records_seen={len(records)}")
    return _submit(messages, {"headline": headline, "figures": figures, "citations": sources,
                              "confidence": 0.8})


# ---------------------------------------------------------------------------
# compactor (worker): summarize a window of events with a citation per event
# ---------------------------------------------------------------------------

def compactor_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    ctx = _context(messages)
    events = ctx["input"]["events"]
    types = sorted({e["event_type"] for e in events})
    rng = ctx["input"]["range"]
    summary = (f"{len(events)} events from {rng['from_observed_at']} to {rng['to_observed_at']}; "
               f"types: {', '.join(types)}")
    return _submit(messages, {"summary": summary,
                              "citations": [{"ref": f"event:events:{e['event_id']}"} for e in events]})


# ---------------------------------------------------------------------------
# the closed loop (engine.autoloop): judge, planner, refiner, and faulty variants
# ---------------------------------------------------------------------------

def judge_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    """Reads the run, then: a failed run is 'wrong' with its first failure; a succeeded run is 'followed'."""
    ctx = _context(messages)
    rid = ctx["input"]["run_id"]
    if _turn(messages) == 0:
        return _calls(messages, [("agent_run__read", {"run_id": rid})])
    run = _tool_results(messages)[-1]
    if run.get("status") != "succeeded":
        reasons = run.get("failure_reasons") or ["no reason recorded"]
        return _submit(messages, {"run_id": rid, "verdict": "wrong",
                                  "reason": f"{run.get('status')}: {reasons[0]}"[:1000], "confidence": 0.9})
    keys = ", ".join(sorted(k for k in (run.get("output") or {}) if k != "citations"))
    return _submit(messages, {"run_id": rid, "verdict": "followed",
                              "reason": f"every check passed; output fields {keys} match the workflow", "confidence": 0.8})


def judge_lenient(*, model, system, messages, tools, candidate_index) -> Completion:
    """Says 'followed' without looking; verdict_grounded refuses it on a failed run."""
    ctx = _context(messages)
    return _submit(messages, {"run_id": ctx["input"]["run_id"], "verdict": "followed",
                              "reason": "looks fine", "confidence": 0.99})


def planner_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    """Schedules the sheet and the capacity the week has not seen, under the cap."""
    ctx = _context(messages)
    inp = ctx["input"]
    seen = {(p["agent"], json.dumps(p["input"], sort_keys=True)) for p in inp.get("pending", [])}
    wanted = [("checker", {"sheet_id": "S2"}), ("allocator", {"capacity": 20}), ("checker", {"sheet_id": "S1"})]
    batch = [{"agent": a, "input": i} for a, i in wanted if (a, json.dumps(i, sort_keys=True)) not in seen]
    batch = batch[: int(inp.get("max_runs", 20))]
    return _submit(messages, {"batch": batch, "why": f"{len(batch)} inputs the week has not covered", "confidence": 0.7})


def planner_bad(*, model, system, messages, tools, candidate_index) -> Completion:
    """Names an agent the pack does not have; batch_resolves refuses it."""
    return _submit(messages, {"batch": [{"agent": "nobody", "input": {}}], "why": "guess", "confidence": 0.5})


def refiner_v1(*, model, system, messages, tools, candidate_index) -> Completion:
    """One exact edit: the first non-empty line of skills.md gets a suffix."""
    ctx = _context(messages)
    inp = ctx["input"]
    text = inp["files"]["skills.md"]
    first = next(l for l in text.splitlines() if l.strip())
    return _submit(messages, {"agent": inp["agent"], "rung": int(inp["rung"]), "file": "skills.md", "old": first,
                              "new": first + " (refined by the loop)", "why": inp["change"][:200], "confidence": 0.6})


def refiner_bad(*, model, system, messages, tools, candidate_index) -> Completion:
    """Proposes text that is not in the file; edit_applies refuses it."""
    ctx = _context(messages)
    inp = ctx["input"]
    return _submit(messages, {"agent": inp["agent"], "rung": int(inp["rung"]), "file": "skills.md",
                              "old": "THIS TEXT IS NOT IN THE FILE", "new": "x", "why": "guess", "confidence": 0.5})


def refiner_declines(*, model, system, messages, tools, candidate_index) -> Completion:
    """Finds no edit the evidence warrants and says so."""
    ctx = _context(messages)
    inp = ctx["input"]
    return _submit(messages, {"agent": inp["agent"], "rung": int(inp["rung"]), "file": None, "old": "", "new": "",
                              "why": "the recommendation names data, not text", "confidence": 0.8})
