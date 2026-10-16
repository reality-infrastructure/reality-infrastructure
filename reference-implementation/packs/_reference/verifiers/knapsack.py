"""Deterministic verifier for the allocator: feasibility, recompute, optimality.

Proposer/verifier boundary for this specialist:
- the MODEL owns: selected, explanation, confidence (and copies of weight/value it cites)
- CODE owns: total_weight, total_value (recomputed), feasibility (≤ capacity),
  row existence/uniqueness, and the optimum (dynamic programming over the table)
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from engine.verify import VerifyResult, verifier


def optimum(rows: list[dict], capacity: int) -> tuple[int, list[str]]:
    best: list[tuple[int, tuple[str, ...]]] = [(0, ())] * (capacity + 1)
    for r in sorted(rows, key=lambda r: r["id"]):
        w, v = int(r["weight"]), int(r["value"])
        for c in range(capacity, w - 1, -1):
            cand_v = best[c - w][0] + v
            cand_ids = best[c - w][1] + (r["id"],)
            if cand_v > best[c][0] or (cand_v == best[c][0] and cand_ids < best[c][1]):
                best[c] = (cand_v, cand_ids)
    return best[capacity][0], sorted(best[capacity][1])


@verifier(id="_reference.knapsack_feasible")
def knapsack_feasible(proposal: dict, vctx) -> VerifyResult:
    rows = vctx.read_table("candidates")
    by_id = {r["id"]: r for r in rows}
    violations: list[str] = []
    try:
        capacity = int(vctx.run_input["capacity"])
    except (KeyError, TypeError, ValueError):
        return VerifyResult.fail(["run input lacks an integer capacity"])
    for r in rows:
        if not isinstance(r["weight"], int) or not isinstance(r["value"], int):
            return VerifyResult.fail([f"row {r['id']}: weights and values must be integers"])
    selected = proposal.get("selected")
    if not isinstance(selected, list) or not all(isinstance(s, str) for s in selected):
        return VerifyResult.fail(["selected must be a list of row ids"])
    if len(set(selected)) != len(selected):
        violations.append("selected contains duplicates")
    unknown = sorted(s for s in selected if s not in by_id)
    if unknown:
        return VerifyResult.fail(violations + [f"unknown candidate ids {unknown}"])
    total_weight = sum(by_id[s]["weight"] for s in selected)
    total_value = sum(by_id[s]["value"] for s in selected)
    recomputed = {"total_weight": total_weight, "total_value": total_value, "capacity": capacity}
    for field, truth in (("total_weight", total_weight), ("total_value", total_value)):
        try:
            stated = Decimal(str(proposal.get(field)))
        except InvalidOperation:
            violations.append(f"{field} is not numeric")
            continue
        if stated != truth:
            violations.append(f"{field} misstated: proposal says {stated}, recomputed {truth}")
    if total_weight > capacity:
        violations.append(f"infeasible: total_weight {total_weight} exceeds capacity {capacity}")
    for item in proposal.get("items") or []:
        row = by_id.get(item.get("id"))
        if row is None or item.get("id") not in selected:
            violations.append(f"items entry {item.get('id')!r} is not a selected candidate")
            continue
        for f in ("weight", "value"):
            if Decimal(str(item.get(f))) != row[f]:
                violations.append(f"item {row['id']} {f} misstated: {item.get(f)} vs {row[f]}")
    best_value, best_ids = optimum(rows, capacity)
    recomputed["optimum_value"] = best_value
    recomputed["optimum_selected"] = best_ids
    if total_weight <= capacity and total_value < best_value:
        violations.append(f"suboptimal: value {total_value} but {best_value} is attainable with {best_ids}")
    return VerifyResult(certified=not violations, violations=tuple(violations), recomputed=recomputed)
