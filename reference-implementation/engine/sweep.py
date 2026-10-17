"""The sweep: one continuous parallel grading loop over every row of a table.

    python -m engine.sweep <pack>/<agent> --table T [--column COL] [--input-key KEY] [--workers N]
                                          [--budget-usd X] [--judge] [--limit M] [--db DSN] [--out DIR]

Every distinct value of ``COL`` (default: the table's id field) that has no succeeded run of the
agent on input ``{KEY: value}`` (default KEY = COL) is a candidate.  Candidates run ``N`` at a time
against one engine and one ledger (the store serializes writes; provider calls overlap), and with
``--judge`` each finished run is adjudicated at once by the pack's judge, the verdict recorded as
the judge's.  The sweep stops for exactly three reasons: every candidate is graded, the budget is
spent (no new work is started once the sweep's cost reaches it; work in flight finishes), or the
kill rule halts the agent.  It writes ``crank/sweep-<agent>-<stamp>.md`` and ``.json``.

Why: the interviews, read as a trader.  Musk puts the sensor at the point of contact so every
launch is recorded; Brown runs the grading as one parallel loop where cost is the only reason to
stop; the panel keeps the whole trace of every launch so the next model trains on all of it.  A
sample of twenty is how a human grades; this is how a machine does.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

from engine.autoloop import kill_rule, loop_agents
from engine.errors import EngineError
from engine.loop import Runner
from engine.packs import load_pack, parse_agent_ref
from engine.runtime import iso
from engine.store import Engine
from engine.verdicts import record_verdict

STOP_REASONS = ("done", "budget", "kill", "limit", "halted_before_start")


def candidates(engine: Engine, pack, agent: str, *, table: str, column: str, input_key: str) -> list[dict]:
    """Inputs ``{input_key: value}`` for every distinct value of ``column`` without a succeeded run."""
    rows = pack.table_rows(table)
    values = []
    seen_vals = set()
    for r in rows:
        v = r.get(column)
        if v is None or v in seen_vals:
            continue
        seen_vals.add(v)
        values.append(v)
    done = {json.dumps(r["input"], sort_keys=True) for r in engine.store.list_runs(pack=pack.name, agent=agent, status="succeeded")}
    return [{input_key: v} for v in values if json.dumps({input_key: v}, sort_keys=True) not in done]


class Sweep:
    def __init__(self, engine: Engine, pack, agent: str, *, workers: int, budget_usd: Decimal | None,
                 judge: bool, limit: int | None, kill_check_every: int, log=None) -> None:
        self.engine, self.pack, self.agent = engine, pack, agent
        self.workers, self.budget, self.limit = max(1, int(workers)), budget_usd, limit
        self.kill_check_every = max(1, int(kill_check_every))
        self.runner = Runner(engine, pack)
        self.judge_name = loop_agents(pack).get("judge") if judge else None
        if judge and self.judge_name is None:
            raise EngineError(f"pack {pack.name!r} has no judge; drop --judge or add one")
        self.runner.agent(agent)                       # load once, before the threads
        if self.judge_name:
            self.runner.agent(self.judge_name)
        self.log = log or (lambda *_: None)
        self._lock = threading.Lock()
        self.cost = Decimal(0)
        self.completed = 0
        self.results: list[dict] = []
        self.stop_reason: str | None = None

    # -- one unit of work: the run, then its verdict ------------------------------------

    def _one(self, run_input: dict) -> dict:
        entry: dict = {"input": run_input}
        try:
            r = self.runner.run(self.agent, run_input)
            entry.update({"run_id": r.run_id, "status": r.status, "cost_usd": str(r.cost_usd)})
            cost = r.cost_usd
            if self.judge_name:
                j = self.runner.run(self.judge_name, {"run_id": r.run_id})
                cost += j.cost_usd
                entry["judge_run_id"], entry["judge_status"] = j.run_id, j.status
                if j.status == "succeeded":
                    record_verdict(self.engine, self.pack, r.run_id, j.output["verdict"], j.output["reason"],
                                   source=f"agent:{self.judge_name}", source_ref=j.run_id)
                    entry["verdict"] = j.output["verdict"]
        except EngineError as e:                       # an errored run is traced by the runner; the sweep goes on
            entry.update({"run_id": entry.get("run_id"), "status": "error", "error": str(e)[:300], "cost_usd": "0"})
            cost = Decimal(0)
        with self._lock:
            self.cost += cost
            self.completed += 1
            self.results.append(entry)
            n = self.completed
        self.log(f"{n} {entry.get('status')} {entry.get('verdict', '')} {json.dumps(run_input, sort_keys=True)[:80]} cost={self.cost}")
        return entry

    def _over_budget(self) -> bool:
        return self.budget is not None and self.cost >= self.budget

    def _halted(self) -> bool:
        return self.agent in kill_rule(self.engine, self.pack)

    # -- the loop ---------------------------------------------------------------------------

    def run(self, inputs: list[dict]) -> dict:
        if self._halted():
            self.stop_reason = "halted_before_start"
            return self.report(inputs, remaining=len(inputs))
        truncated = self.limit is not None and self.limit < len(inputs)
        if truncated:
            inputs = inputs[: self.limit]
        pending = list(inputs)
        in_flight = set()
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            while pending or in_flight:
                while pending and len(in_flight) < self.workers and not self._over_budget() and self.stop_reason is None:
                    in_flight.add(pool.submit(self._one, pending.pop(0)))
                if not in_flight:
                    break
                done = next(as_completed(in_flight))
                in_flight.discard(done)
                done.result()
                if self.stop_reason is None:
                    if self._over_budget():
                        self.stop_reason = "budget"
                    elif self.completed % self.kill_check_every == 0 and self._halted():
                        self.stop_reason = "kill"
        if self.stop_reason is None:
            self.stop_reason = "limit" if truncated else "done"
        return self.report(inputs, remaining=len(pending))

    def report(self, inputs: list[dict], *, remaining: int) -> dict:
        by_status: dict[str, int] = {}
        verdicts: dict[str, int] = {}
        for e in self.results:
            by_status[e.get("status") or "error"] = by_status.get(e.get("status") or "error", 0) + 1
            if "verdict" in e:
                verdicts[e["verdict"]] = verdicts.get(e["verdict"], 0) + 1
        return {"pack": self.pack.name, "agent": self.agent, "judge": self.judge_name, "workers": self.workers,
                "budget_usd": None if self.budget is None else str(self.budget), "candidates": len(inputs),
                "completed": self.completed, "remaining": remaining, "by_status": by_status, "verdicts": verdicts,
                "cost_usd": str(self.cost), "stop_reason": self.stop_reason, "halted_now": self._halted(),
                "results": self.results}


def render(rep: dict, stamp: str) -> str:
    L = [f"# Sweep — {rep['pack']}/{rep['agent']} — {stamp}", "",
         f"candidates {rep['candidates']}; completed {rep['completed']}; remaining {rep['remaining']}; "
         f"workers {rep['workers']}; judge {rep['judge'] or 'none'}; budget {rep['budget_usd'] or 'none'}; cost ${rep['cost_usd']}", "",
         f"stopped because: **{rep['stop_reason']}**" + ("; the agent is halted by the kill rule now" if rep["halted_now"] else ""), "",
         "| status | runs |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(rep["by_status"].items())]
    L += ["", "| verdict (judge) | runs |", "|---|---|"] + ([f"| {k} | {v} |" for k, v in sorted(rep["verdicts"].items())] or ["| none | 0 |"])
    L += ["", "Every run above is a trace in the store and every verdict a ledger-bound event; the operator's verdict on any run outranks the judge's."]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.sweep")
    p.add_argument("agent_ref")
    p.add_argument("--table", required=True)
    p.add_argument("--column", help="distinct values of this column become inputs (default: the table's id field)")
    p.add_argument("--input-key", help="the input key the agent takes (default: the column name)")
    p.add_argument("--workers", type=int)
    p.add_argument("--budget-usd", type=Decimal)
    p.add_argument("--judge", action="store_true", help="adjudicate each run at once with the pack's judge")
    p.add_argument("--limit", type=int)
    p.add_argument("--db")
    p.add_argument("--out", help="directory (default packs/<pack>/crank)")
    args = p.parse_args(argv)
    try:
        pack_name, agent = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            if args.table not in pack.tables:
                raise EngineError(f"no table {args.table!r} in pack {pack_name!r}")
            column = args.column or pack.tables[args.table].id_field
            cfg = engine.config.sweep
            inputs = candidates(engine, pack, agent, table=args.table, column=column, input_key=args.input_key or column)
            sweep = Sweep(engine, pack, agent, workers=args.workers or cfg["workers"],
                          budget_usd=args.budget_usd if args.budget_usd is not None else (None if cfg["budget_usd"] is None else Decimal(str(cfg["budget_usd"]))),
                          judge=args.judge, limit=args.limit, kill_check_every=cfg["kill_check_every"],
                          log=lambda m: print(m, flush=True))
            stamp = iso(engine.clock.now())[:19].replace(":", "")
            rep = sweep.run(inputs)
        finally:
            engine.close()
        out_dir = Path(args.out) if args.out else pack.root / "crank"
        out_dir.mkdir(parents=True, exist_ok=True)
        base = out_dir / f"sweep-{agent}-{stamp}"
        base.with_suffix(".md").write_text(render(rep, stamp), encoding="utf-8")
        base.with_suffix(".json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"sweep: {rep['completed']} of {rep['candidates']} ({rep['stop_reason']}), cost ${rep['cost_usd']} -> {base.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
