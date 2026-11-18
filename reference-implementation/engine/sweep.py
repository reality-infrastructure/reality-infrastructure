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

from engine import curriculum
from engine import rollout as rollout_mod
from engine import sizing
from engine import integrity
from engine.autoloop import kill_rule, loop_agents, plant_honeypots
from engine.crank import _cluster_key
from engine.constraint import sweep_throughput
from engine.errors import EngineError
from engine.events import EventLog
from engine.loop import Runner
from engine.manifest import load_agent
from engine.offpeak import in_windows, next_open
from engine.packs import load_pack, parse_agent_ref
from engine.runtime import iso
from engine.store import Engine
from engine.verdicts import record_verdict
from engine.reputation import sweep_leverage

STOP_REASONS = ("done", "budget", "kill", "limit", "halted_before_start",
                "burn_in", "tier", "sizing_cap", "target", "pilot", "window_closed", "broken_task",
                "review_backlog")


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
    """``rollout``, ``pilot``, ``preflight`` and ``window`` are off unless given; ``build_sweep`` gives them from
    config/engine.yaml, and the CLI and the scheduler always build through it."""

    def __init__(self, engine: Engine, pack, agent: str, *, workers: int, budget_usd: Decimal | None,
                 judge: bool, limit: int | None, kill_check_every: int, log=None, runner: Runner | None = None,
                 rollout: dict | None = None, pilot: dict | None = None, preflight: bool = False,
                 target_followed: int | None = None, window: tuple = (), reload_on_adoption: bool = True,
                 remediate: bool = False, broken: dict | None = None) -> None:
        sizing.require_budget(pack, budget_usd, "a sweep")
        self.engine, self.pack, self.agent = engine, pack, agent
        self.workers, self.budget, self.limit = max(1, int(workers)), budget_usd, limit
        self.kill_check_every = max(1, int(kill_check_every))
        self.tier, self.workers, self.budget = sweep_leverage(engine, pack.name, agent, self.workers, self.budget)   # leverage bought by the record
        self.runner = runner or Runner(engine, pack)
        self.judge_name = loop_agents(pack).get("judge") if judge else None
        if judge and self.judge_name is None:
            raise EngineError(f"pack {pack.name!r} has no judge; drop --judge or add one")
        loaded = self.runner.agent(agent)              # load once, before the threads
        self.manifest_hash = loaded.hash
        # JH-C11 G-B4: workers of an agent that shares findings write to and read from one scratch per sweep
        self.scratch_scope = (f"sweep:{engine.ids.new()}"
                              if {"scratch.write", "scratch.read"} & set(loaded.tools) else None)
        if self.judge_name:
            self.runner.agent(self.judge_name)
        self.log = log or (lambda *_: None)
        self._lock = threading.Lock()
        self.cost = Decimal(0)
        self.completed = 0
        self.results: list[dict] = []
        self.stop_reason: str | None = None
        self.broken = dict(broken or engine.config.sweep_broken)
        self.broken_cluster: dict | None = None
        self.tier_gated: list[dict] = []
        self.promoted: dict | None = None
        self.rollout_cfg, self.pilot_cfg, self.preflight = rollout, pilot, preflight
        self.target_followed, self.window = target_followed, tuple(window)
        self.reload_on_adoption, self.remediate = reload_on_adoption, remediate
        self.active_workers = self.workers
        self.peak_in_flight = 0
        self.started_at: str | None = None
        self.ramp: rollout_mod.Ramp | None = None
        self.extra: dict = {"rollout": None, "sizing": None, "pilot": None, "projection": None,
                            "version_switches": [], "worker_changes": [], "remediation": None}
        self.withheld: str | None = None             # why no agent verdict is recorded on this sweep (judge suspended)
        self.guard: dict = {}
        self.honeypots: list[dict] = []

    # -- one unit of work: the run, then its verdict ------------------------------------

    def _one(self, run_input: dict, slot: int) -> dict:
        threading.current_thread().name = f"sweep-slot-{slot}"     # the worker slot this unit occupies, as the thread's name
        entry: dict = {"input": run_input, "slot": slot, "started_at": iso(self.engine.clock.now())}
        try:
            r = self.runner.run(self.agent, run_input, scratch_scope=self.scratch_scope)
            entry.update({"run_id": r.run_id, "status": r.status, "cost_usd": str(r.cost_usd),
                          "manifest_hash": r.row["manifest_hash"], "tokens": sizing.run_tokens(r.row)})
            cost = r.cost_usd
            if self.judge_name and self.withheld:
                entry["verdict_withheld"] = self.withheld
            elif self.judge_name:
                j = integrity.adjudicate(self.runner, self.judge_name, self.engine.store.get_run(r.run_id))
                cost += Decimal(j["cost_usd"])
                entry["judge_run_id"], entry["judge_status"] = j["judge_run_id"], j["status"]
                if "verdict" in j:
                    entry["verdict"] = j["verdict"]
        except EngineError as e:                       # an errored run is traced by the runner; the sweep goes on
            entry.update({"run_id": entry.get("run_id"), "status": "error", "error": str(e)[:300], "cost_usd": "0"})
            cost = Decimal(0)
        entry["finished_at"] = iso(self.engine.clock.now())
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

    def _open(self) -> bool:
        """Inside the off-peak window (always, without one)."""
        return not self.window or in_windows(self.window, self.engine.clock.now())

    def _backlogged(self) -> bool:
        return bool(self.judge_name) and integrity.review_gate(self.engine, self.pack, "sweep")["over"]

    def _check_version(self) -> None:
        """An adopted edit changed the agent's files: the remaining inputs run on the new version."""
        fresh = load_agent(self.pack, self.agent, config=self.engine.config)
        if fresh.hash == self.manifest_hash:
            return
        payload = {"agent": self.agent, "old_hash": self.manifest_hash, "new_hash": fresh.hash, "at_completion": self.completed}
        EventLog(self.engine, self.pack).append(entity_type="agent_run", entity_id=self.agent,
                                                event_type=f"{self.pack.name}.version_switch", payload=payload, source="pipeline:sweep")
        self.runner._agents[self.agent] = fresh
        self.manifest_hash = fresh.hash
        self.extra["version_switches"].append(payload)

    def _ramp_step(self, entry: dict) -> None:
        change = self.ramp.on_completion(entry.get("status") == "succeeded", self.engine.clock.now())
        if change is None:
            return
        self.active_workers = change["workers"]
        payload = {"agent": self.agent, "manifest_hash": self.manifest_hash, "tier": self.extra["rollout"]["tier"],
                   "mode": "ramp", "workers": change["workers"], "pass_rate": change["pass_rate"],
                   "at_completion": self.completed, "why": change["why"]}
        rollout_mod.record(self.engine, self.pack, self.agent, payload)
        self.extra["worker_changes"].append(payload)

    def _drive(self, inputs: list[dict]) -> list[dict]:
        """Run ``inputs`` with up to ``active_workers`` in flight; returns those never started.  Each unit takes the
        lowest free worker slot (0..workers-1), so per-slot occupancy is a property of the sweep, not of the OS."""
        pending = list(inputs)
        in_flight: dict = {}
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            while pending or in_flight:
                while (pending and len(in_flight) < self.active_workers and not self._over_budget()
                       and self.stop_reason is None):
                    if not self._open():
                        self.stop_reason = "window_closed"
                        break
                    slot = min(set(range(self.workers)) - set(in_flight.values()))
                    in_flight[pool.submit(self._one, pending.pop(0), slot)] = slot
                self.peak_in_flight = max(self.peak_in_flight, len(in_flight))
                if not in_flight:
                    break
                done = next(as_completed(in_flight))
                del in_flight[done]
                entry = done.result()
                if self.stop_reason is None:
                    if self._over_budget():
                        self.stop_reason = "budget"
                    elif self.completed % self.kill_check_every == 0 and self._halted():
                        self.stop_reason = "kill"
                    elif self.completed == self.broken["window"] and self._broken():
                        self.stop_reason = "broken_task"
                    elif self.completed % self.kill_check_every == 0 and self._backlogged():
                        self.stop_reason = "review_backlog"
                    elif self.completed % self.kill_check_every == 0 and self.reload_on_adoption:
                        self._check_version()
                if self.ramp is not None and self.stop_reason is None:
                    self._ramp_step(entry)
        return pending

    # -- the loop ---------------------------------------------------------------------------

    def _apply_rollout(self, inputs: list[dict], cap_reason: str | None) -> tuple[list[dict], str | None]:
        plan = rollout_mod.plan(self.engine, self.pack, self.agent, self.manifest_hash,
                                requested_workers=self.workers, cfg=self.rollout_cfg)
        self.extra["rollout"] = plan
        rollout_mod.record(self.engine, self.pack, self.agent,
                           {"agent": self.agent, "at_completion": 0,
                            **{k: plan[k] for k in ("manifest_hash", "tier", "workers", "pass_rate", "mode", "why")}})
        self.workers, self.active_workers = plan["workers"], plan["start_workers"]
        if plan["limit"] is not None and plan["limit"] < len(inputs):
            inputs, cap_reason = inputs[: plan["limit"]], "burn_in" if plan["mode"] == "burn_in" else "tier"
        if plan["mode"] == "ramp" and plan["start_workers"] < self.workers:
            self.ramp = rollout_mod.Ramp(start=plan["start_workers"], ceiling=self.workers,
                                         step_runs=self.rollout_cfg["step_runs"], min_pass_rate=self.rollout_cfg["min_pass_rate"],
                                         min_gain=self.rollout_cfg.get("min_gain", self.engine.config.sizing["min_gain"]),
                                         now=self.engine.clock.now())
        return inputs, cap_reason

    def run(self, inputs: list[dict]) -> dict:
        self.started_at = iso(self.engine.clock.now())
        self.guard = integrity.safeguards(self.engine, self.pack, "sweep", self.agent)
        if self.judge_name and self.guard["judge"]["suspended"]:
            self.withheld = f"judge suspended by {self.guard['judge']['suspended_by']}: no agent verdict is recorded on any path"
        if self._halted():
            self.stop_reason = "halted_before_start"
            return self.report(inputs, remaining=len(inputs))
        if self._backlogged():
            self.stop_reason = "review_backlog"
            return self.report(inputs, remaining=len(inputs))
        inputs, self.tier_gated = curriculum.gate_inputs(self.engine, self.pack, self.agent, inputs)
        cap_reason = None
        if self.limit is not None and self.limit < len(inputs):
            inputs, cap_reason = inputs[: self.limit], "limit"
        if self.rollout_cfg is not None:
            inputs, cap_reason = self._apply_rollout(inputs, cap_reason)
        if self.preflight:
            sz = sizing.preflight(self.engine, self.pack, self.agent, remaining=len(inputs), workers=self.workers,
                                  budget=self.budget, judge=self.judge_name, target_followed=self.target_followed)
            self.extra["sizing"] = sz
            if sz.get("limit") is not None and sz["limit"] < len(inputs):
                inputs, cap_reason = inputs[: sz["limit"]], "sizing_cap" if sz["decision"] == "cap" else "target"
        main, pilot = list(inputs), None
        n = int((self.pilot_cfg or {}).get("n") or 0)
        if n and len(inputs) > n:
            seed = str(self.pilot_cfg["seed"])
            idx = set(sizing.pilot_indices(len(inputs), n, seed))
            main = [x for i, x in enumerate(inputs) if i not in idx]
            left = self._drive([x for i, x in enumerate(inputs) if i in idx])
            if self.stop_reason is not None:
                return self._finish(inputs, left + main, cap_reason)
            pilot = sizing.project_pilot(self.engine, self.pack, self.agent, list(self.results), remaining=len(main),
                                         budget=self.budget, spent=self.cost, seed=seed,
                                         refuse_over_budget=bool(self.pilot_cfg.get("refuse_if_projected_over_budget", True)),
                                         workers=self.active_workers, width=self.runner.agent(self.agent).loop["search_width"],
                                         iterations=self.runner.agent(self.agent).loop["max_iterations"])
            self.extra["pilot"] = pilot
            if pilot["decision"] == "stop":
                self.stop_reason = "pilot"
                return self._finish(inputs, main, cap_reason)
        pilot_done = len(self.results)
        left = self._drive(main)
        if pilot is not None:
            self.extra["projection"] = sizing.final_projection(self.engine, self.pack, self.agent, pilot,
                                                               self.results[pilot_done:], self.results,
                                                               sweep_started=self.started_at)
        return self._finish(inputs, left, cap_reason)

    def _finish(self, inputs: list[dict], left: list[dict], cap_reason: str | None) -> dict:
        if self.stop_reason is None:
            self.stop_reason = cap_reason or "done"
        if self.judge_name and not self.withheld:
            k = int(self.engine.config.autoloop["judge"]["honeypots_per_cycle"])
            mine = [self.engine.store.get_run(e["run_id"]) for e in self.results if e.get("status") == "succeeded"]
            self.honeypots = [h for j in integrity.panel_members(self.engine, self.pack, self.judge_name)
                              for h in plant_honeypots(self.runner, j, mine, k)]
        promoted = curriculum.promote(self.engine, self.pack, self.agent)
        self.promoted = None if promoted is None else promoted["payload"]
        if self.remediate:
            from engine.remediate import remediation_trigger
            self.extra["remediation"] = remediation_trigger(self.engine, self.pack, packs_root=self.pack.root.parent)
        rep = self.report(inputs, remaining=len(left))
        if self.engine.config.analytics["measure_throughput"] and self.results:
            rep["throughput"] = sweep_throughput(self.engine, self.pack, self.agent, self.results, workers=self.workers, budget_usd=self.budget)
        return rep

    def record_throughput(self, rep: dict) -> dict | None:
        """The finished sweep's ``<pack>.throughput`` event (the CLI records it beside its report files)."""
        t = rep.get("throughput")
        if not t:
            return None
        return self.runner.events.append(entity_type="agent_run", entity_id=self.agent, event_type=f"{self.pack.name}.throughput",
                                         payload={k: t[k] for k in ("agent", "workers", "runs_per_hour", "items_per_hour",
                                                                    "manual_baseline_items", "lock_wait_share",
                                                                    "provider_share", "utilisation", "binding")},
                                         source="pipeline:sweep")

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
                "results": self.results, "tier_gated": self.tier_gated, "promoted": self.promoted,
                "broken_cluster": self.broken_cluster, "reputation_tier": self.tier,
                "verdicts_withheld": self.withheld, "honeypots": self.honeypots,
                "safeguards_event": self.guard.get("event_id"), **self._measures()}

    def _broken(self) -> bool:
        """Patel's broken task: when one failure cluster (the crank's key, or one shared error message) is more
        than ``max_cluster_share`` of the first ``window`` completions, the case or environment is the likelier
        fault, and grading on would spend the budget measuring it.  The sweep pauses for a human to rebuild it."""
        keys: dict[str, int] = {}
        window = self.results[: self.broken["window"]]
        for e in window:
            if e.get("status") == "succeeded":
                continue
            if e.get("error"):
                key = f"error: {_cluster_key(e['error'].split(': ', 1)[-1])}"
            else:
                row = self.engine.store.get_run(e["run_id"])
                reasons = (row or {}).get("failure_reasons") or [""]
                key = f"{e.get('status')}: {_cluster_key(reasons[0].split(': ', 1)[-1])}"
            keys[key] = keys.get(key, 0) + 1
        if not keys:
            return False
        top, n = max(sorted(keys.items()), key=lambda kv: kv[1])
        if n / len(window) <= self.broken["max_cluster_share"]:
            return False
        self.broken_cluster = {"cluster": top, "count": n, "window": len(window)}
        return True

    def _measures(self) -> dict:
        """When it ran, how long, on how many tokens, how wide; and what rollout, sizing and the pilot decided."""
        tokens = {"input": 0, "output": 0, "reasoning": 0}
        for e in self.results:
            for k in tokens:
                tokens[k] += (e.get("tokens") or {}).get(k, 0)
        finished = [e["finished_at"] for e in self.results if e.get("finished_at")]
        return {"started_at": self.started_at, "finished_at": max(finished) if finished else self.started_at,
                "wall_s": sizing.wall_seconds(self.results), "tokens": tokens, "peak_in_flight": self.peak_in_flight,
                "window_opens_at": (iso(next_open(self.window, self.engine.clock.now()))
                                    if self.stop_reason == "window_closed" else None), **self.extra}


def render(rep: dict, stamp: str) -> str:
    L = [f"# Sweep — {rep['pack']}/{rep['agent']} — {stamp}", "",
         f"candidates {rep['candidates']}; completed {rep['completed']}; remaining {rep['remaining']}; "
         f"workers {rep['workers']}; judge {rep['judge'] or 'none'}; budget {rep['budget_usd'] or 'none'}; cost ${rep['cost_usd']}", "",
         f"stopped because: **{rep['stop_reason']}**" + ("; the agent is halted by the kill rule now" if rep["halted_now"] else ""), "",
         "| status | runs |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(rep["by_status"].items())]
    L += ["", "| verdict (judge) | runs |", "|---|---|"] + ([f"| {k} | {v} |" for k, v in sorted(rep["verdicts"].items())] or ["| none | 0 |"])
    if rep.get("broken_cluster"):
        b = rep["broken_cluster"]
        L += ["", f"broken task: {b['count']} of the first {b['window']} completions failed as `{b['cluster']}`; rebuild the case or environment before grading on"]
    if rep.get("tier_gated"):
        L += ["", f"{len(rep['tier_gated'])} inputs held back above the agent's promoted tier (easy first)"]
    if rep.get("promoted"):
        L += ["", f"promoted from tier {rep['promoted']['from_tier']} to {rep['promoted']['to_tier']}"]
    L += ["", f"wall {rep.get('wall_s')} s from {rep.get('started_at')} to {rep.get('finished_at')}; tokens {rep.get('tokens')}; "
              f"peak in flight {rep.get('peak_in_flight')}"]
    if rep.get("rollout"):
        r = rep["rollout"]
        L += [f"rollout: {r['mode']} on version {r['manifest_hash'][:12]} ({r['runs']} runs, pass rate {r['pass_rate']}): {r['why']}"]
        L += [f"- workers -> {c['workers']} at completion {c['at_completion']}: {c['why']}" for c in rep.get("worker_changes") or []]
    if rep.get("sizing"):
        L += [f"pre-flight ({rep['sizing']['decision']}): {rep['sizing']['arithmetic']}"]
    if rep.get("pilot"):
        pl = rep["pilot"]
        L += [f"pilot of {pl['n']} (seed {pl['seed']}): pass rate {pl['pass_rate']} {pl['wilson']}, projected ${pl['projected_cost']} "
              f"for {pl['remaining']} more, {pl['decision']}: {pl['why']}"]
    if rep.get("projection"):
        pr = rep["projection"]
        L += [f"projection vs actual: cost ${pr['projected_cost']} -> ${pr['actual_cost']} (error {pr['cost_error']}); pass rate "
              f"{pr['projected_pass_rate']} -> {pr['actual_pass_rate']} (error {pr['pass_rate_error']})"
              + (f"; refinement {pr['refinement_event_id']} {'survived' if pr['refinement']['survived'] else 'DID NOT survive'} at scale"
                 if pr.get("refinement") else "")]
    L += [f"version switch at completion {v['at_completion']}: {v['old_hash'][:12]} -> {v['new_hash'][:12]}" for v in rep.get("version_switches") or []]
    if rep.get("window_opens_at"):
        L += [f"outside the off-peak window: the next one opens at {rep['window_opens_at']}"]
    t = rep.get("throughput")
    if t:
        L += ["", f"Throughput: {t['runs_per_hour']} runs/hour, {t['items_per_hour']} items/hour (manual baseline {t['manual_baseline_items']}); "
                  f"provider share {t['provider_share']:.0%}, engine share {t['lock_wait_share']:.0%}, worker utilisation {t['utilisation']:.0%}; "
                  f"binding resource: **{t['binding']}**"]
    L += ["", "Every run above is a trace in the store and every verdict a ledger-bound event; the operator's verdict on any run outranks the judge's."]
    return "\n".join(L) + "\n"


def build_sweep(engine: Engine, pack, agent: str, *, workers: int | None = None, budget_usd: Decimal | None = None,
                judge: bool = False, limit: int | None = None, off_peak: bool | None = None, pilot_n: int | None = None,
                target_followed: int | None = None, log=None, runner: Runner | None = None) -> Sweep:
    """A sweep with the engine's law on it (config/engine.yaml): rollout, pre-flight sizing, the pilot, the
    off-peak window, reload on adoption, remediation at the end, and the mandatory budget outside fixtures."""
    cfg, opts = engine.config.sweep, engine.config.sweep_options
    if workers is None and opts["adaptive_workers"]:
        from engine.scale import recommended_workers
        workers = recommended_workers(engine, pack, agent)
    budget = budget_usd if budget_usd is not None else (None if cfg["budget_usd"] is None else Decimal(str(cfg["budget_usd"])))
    window = ()
    if off_peak if off_peak is not None else opts["off_peak"]:
        a = (runner or Runner(engine, pack)).agent(agent)
        window = engine.config.off_peak_windows(a.model.provider, a.model.name)
        if not window:
            raise EngineError(f"--off-peak: {a.model.model_string} has no off_peak tariff in config/prices.yaml")
    pilot = dict(opts["pilot"])
    if pilot_n is not None:
        pilot["n"] = pilot_n
    return Sweep(engine, pack, agent, workers=workers or cfg["workers"], budget_usd=budget, judge=judge, limit=limit,
                 kill_check_every=cfg["kill_check_every"], log=log, runner=runner, rollout=engine.config.rollout,
                 pilot=pilot, preflight=True, target_followed=target_followed, window=window,
                 reload_on_adoption=opts["reload_on_adoption"], remediate=engine.config.autoloop_trigger["enabled"])


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
    p.add_argument("--off-peak", action="store_true", default=None,
                   help="start new work only inside the agent model's off-peak windows (config/prices.yaml)")
    p.add_argument("--pilot", type=int, help="pilot size (0: no pilot; default config sweep.pilot.n)")
    p.add_argument("--target-followed", type=int, help="work backward from this many followed runs to the runs needed")
    args = p.parse_args(argv)
    try:
        pack_name, agent = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            from engine.schedule import store_lease
            pack = load_pack(pack_name)
            if args.table not in pack.tables:
                raise EngineError(f"no table {args.table!r} in pack {pack_name!r}")
            column = args.column or pack.tables[args.table].id_field
            with store_lease(engine, "engine.sweep"):
                inputs = candidates(engine, pack, agent, table=args.table, column=column, input_key=args.input_key or column)
                sweep = build_sweep(engine, pack, agent, workers=args.workers, budget_usd=args.budget_usd, judge=args.judge,
                                    limit=args.limit, off_peak=args.off_peak, pilot_n=args.pilot,
                                    target_followed=args.target_followed, log=lambda m: print(m, flush=True))
                stamp = iso(engine.clock.now())[:19].replace(":", "")
                rep = sweep.run(inputs)
                sweep.record_throughput(rep)
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
