"""The checker's domain guardrail: code recomputes every row; the model's flags must agree."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from engine.guardrails import guardrail

from _reference.tools.arith import evaluate


@guardrail(id="_reference.flags_consistent")
def flags_consistent(output, gctx) -> list[str]:
    problems = []
    items = output.get("items") if isinstance(output, dict) else None
    if not isinstance(items, list):
        return ["items must be a list"]
    seen = set()
    for i, item in enumerate(items):
        row = gctx.pack.table_row("sheets", str(item.get("row_id")))
        if row is None:
            problems.append(f"items/{i}: unknown row {item.get('row_id')!r}")
            continue
        if row["id"] in seen:
            problems.append(f"items/{i}: duplicate row {row['id']}")
        seen.add(row["id"])
        if row["sheet_id"] != gctx.run_input.get("sheet_id"):
            problems.append(f"items/{i}: row {row['id']} belongs to sheet {row['sheet_id']}")
        truth = evaluate(row["expression"])
        try:
            recomputed = Decimal(str(item.get("recomputed")))
            claimed = Decimal(str(item.get("claimed")))
        except InvalidOperation:
            problems.append(f"items/{i}: non-numeric claimed/recomputed")
            continue
        if recomputed != truth:
            problems.append(f"items/{i}: recomputed {recomputed} but {row['expression']} = {truth}")
        if bool(item.get("flag")) != (claimed != truth):
            problems.append(f"items/{i}: flag {item.get('flag')} inconsistent with claimed {claimed} vs {truth}")
    expected = {r["id"] for r in gctx.pack.table_rows("sheets") if r["sheet_id"] == gctx.run_input.get("sheet_id")}
    missing = sorted(expected - seen)
    if missing:
        problems.append(f"rows not evaluated: {missing}")
    return problems
