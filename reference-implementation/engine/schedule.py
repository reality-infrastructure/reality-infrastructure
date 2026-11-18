"""The schedule: agents that work while the operator sleeps, one process per store.

    python -m engine.schedule <pack> [<pack> ...] --tick  [--db DSN]     # run what is due now, then exit
    python -m engine.schedule <pack> [<pack> ...] --serve [--db DSN]     # tick, sleep until the next due job, repeat

A pack declares its jobs in ``schedule.yaml``::

    jobs:
      - id: weekly-loop
        kind: autoloop                     # the closed loop for the ISO week of the tick
        every: 7d                          # <n>m | <n>h | <n>d
        anchor: "2026-10-12T04:00:00+00:00"   # ticks fall on anchor + k * every (a Monday 04:00 = weekly at Mon 04:00)
        max_runs: 20                       # optional, the planner's cap
      - id: nightly-sweep
        kind: sweep                        # engine.sweep with the engine's law (rollout, sizing, pilot, budget)
        every: 1d
        anchor: "2026-10-12T22:00:00+00:00"
        agent: checker
        table: sheets
        column: sheet_id                   # optional (the table's id field); input_key optional (= column)
        judge: true                        # optional
        workers: 4                         # optional
        budget_usd: "2.00"                 # mandatory outside fixture packs
        off_peak: true                     # optional: start work only inside the model's off-peak windows
      - {id: triggers, kind: triggers, every: 5m, anchor: "2026-10-12T00:00:00+00:00"}    # engine.triggers poll
      - {id: remediate, kind: remediate, every: 15m, anchor: "2026-10-12T00:00:00+00:00"} # engine.remediate check

The store lease (``engine_leases`` row ``store``) enforces HARNESS.md's one-process-per-store rule: the
scheduler, and every long-running CLI (sweep, scale, triggers, autoloop), takes it before writing and renews
it while it works; a second process is refused while the lease is live (``schedule.lease_seconds``).

On every tick the scheduler finds, per job, the ticks due since the last one it recorded; the oldest beyond
``schedule.max_catch_up`` are recorded as skipped in one event, the rest run once each, oldest first, marked
``missed`` when a later tick is also due (the process was down at that time).  A sweep tick for an agent the
kill rule halts is recorded as skipped and does not run; so is an off-peak sweep outside its window.

Events: ``<pack>.schedule`` {job, kind, tick, started_at, finished_at, status, missed, skipped_reason,
skipped_ticks, result, error}; ``<pack>.heartbeat`` {holder, expires_at, reason} every
``schedule.heartbeat_seconds`` while the lease is held.  The crank reports the week's ticks and misses.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Iterator

from engine.config import load_yaml
from engine.errors import EngineError, ManifestError
from engine.events import EventLog
from engine.packs import load_pack
from engine.runtime import iso, parse_iso
from engine.store import Engine

STORE_LEASE = "store"
JOB_KINDS = ("autoloop", "sweep", "triggers", "remediate")
_EVERY_RE = re.compile(r"^(\d+)([mhd])$")
_COMMON_KEYS = {"id", "kind", "every", "anchor"}
_KIND_KEYS = {"autoloop": {"max_runs"},
              "sweep": {"agent", "table", "column", "input_key", "judge", "workers", "budget_usd", "off_peak"},
              "triggers": set(), "remediate": set()}


class LeaseHeld(EngineError):
    """Another process holds the store: one process per store."""


# -- the lease ------------------------------------------------------------------------------

class Lease:
    """The store lease, renewed by ``beat`` (thread-safe; a sweep's workers beat on every completion)."""

    def __init__(self, engine: Engine, holder: str, *, packs: list | None = None) -> None:
        cfg = engine.config.schedule
        self.engine, self.holder, self.packs = engine, holder, list(packs or [])
        self.seconds, self.heartbeat = timedelta(seconds=cfg["lease_seconds"]), timedelta(seconds=cfg["heartbeat_seconds"])
        self._last: datetime | None = None
        self._lock = threading.Lock()

    def _take(self, reason: str) -> None:
        now = self.engine.clock.now()
        expires = now + self.seconds
        if not self.engine.store.lease_acquire(STORE_LEASE, self.holder, iso(now), iso(expires)):
            held = self.engine.store.lease_get(STORE_LEASE) or {}
            raise LeaseHeld(f"the store is leased by {held.get('holder')!r} until {held.get('expires_at')}: "
                            f"one process per store (HARNESS.md); this process ({self.holder}) may not write to it")
        self._last = now
        for pack in self.packs:
            EventLog(self.engine, pack).append(entity_type="agent_run", entity_id=self.holder,
                                               event_type=f"{pack.name}.heartbeat",
                                               payload={"holder": self.holder, "expires_at": iso(expires), "reason": reason},
                                               source="pipeline:schedule")

    def acquire(self) -> None:
        with self._lock:
            self._take("acquired")

    def beat(self) -> None:
        """Renew when a heartbeat is due."""
        with self._lock:
            if self._last is None or self.engine.clock.now() - self._last >= self.heartbeat:
                self._take("heartbeat")

    def release(self) -> None:
        with self._lock:
            self.engine.store.lease_release(STORE_LEASE, self.holder)
            self._last = None


@contextmanager
def store_lease(engine: Engine, program: str, *, packs: list | None = None) -> Iterator[Lease]:
    lease = Lease(engine, f"{program}:{os.getpid()}:{engine.ids.new()[:8]}", packs=packs)
    lease.acquire()
    try:
        yield lease
    finally:
        lease.release()


# -- jobs -------------------------------------------------------------------------------------

def parse_every(text) -> timedelta:
    m = _EVERY_RE.match(str(text))
    if not m or int(m.group(1)) <= 0:
        raise ManifestError(f"every {text!r} must look like 15m, 6h or 7d")
    n = int(m.group(1))
    return {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[m.group(2)]


def load_schedule(pack) -> list[dict]:
    """The pack's jobs, checked; [] without schedule.yaml."""
    path = pack.root / "schedule.yaml"
    if not path.is_file():
        return []
    doc = load_yaml(path)
    if set(doc) != {"jobs"} or not isinstance(doc["jobs"], list):
        raise ManifestError(f"{path}: must hold exactly one key, jobs: a list")
    jobs, seen = [], set()
    for n, j in enumerate(doc["jobs"]):
        where = f"{path}: job {n}"
        if not isinstance(j, dict) or j.get("kind") not in JOB_KINDS:
            raise ManifestError(f"{where}: kind must be one of {JOB_KINDS}")
        extra = set(j) - _COMMON_KEYS - _KIND_KEYS[j["kind"]]
        if extra or not (_COMMON_KEYS <= set(j)):
            raise ManifestError(f"{where}: needs {sorted(_COMMON_KEYS)}; unknown keys {sorted(extra)}")
        if j["id"] in seen:
            raise ManifestError(f"{where}: duplicate id {j['id']!r}")
        seen.add(j["id"])
        try:
            anchor = parse_iso(str(j["anchor"]))
        except ValueError as e:
            raise ManifestError(f"{where}: anchor {j['anchor']!r} is not ISO-8601") from e
        if j["kind"] == "sweep":
            if j.get("agent") not in pack.agent_names:
                raise ManifestError(f"{where}: no agent {j.get('agent')!r} in pack {pack.name!r}")
            if j.get("table") not in pack.tables:
                raise ManifestError(f"{where}: no table {j.get('table')!r} in pack {pack.name!r}")
            if j.get("budget_usd") is None and not pack.fixture:
                raise ManifestError(f"{where}: a sweep job in a real pack needs budget_usd")
        jobs.append({**j, "every": parse_every(j["every"]), "anchor": anchor, "every_text": str(j["every"])})
    return jobs


def _last_ticks(engine: Engine, pack) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for e in engine.store.query_events(event_type=f"{pack.name}.schedule", limit=1_000_000, ascending=True):
        t = parse_iso(e["payload"]["tick"])
        job = e["payload"]["job"]
        if job not in out or t > out[job]:
            out[job] = t
    return out


def due_ticks(job: dict, last: datetime | None, now: datetime) -> list[datetime]:
    """Every tick of the job due at ``now`` after ``last`` (the caller keeps at most max_catch_up of them)."""
    if now < job["anchor"]:
        return []
    every = job["every"]
    k_max = math.floor((now - job["anchor"]) / every)
    k_min = 0 if last is None else math.floor((last - job["anchor"]) / every) + 1
    return [job["anchor"] + k * every for k in range(k_min, k_max + 1)]


class Scheduler:
    def __init__(self, engine: Engine, packs: list, *, holder: str | None = None) -> None:
        self.engine, self.packs = engine, list(packs)
        self.jobs = {p.name: load_schedule(p) for p in self.packs}
        self.lease = Lease(engine, holder or f"engine.schedule:{os.getpid()}:{engine.ids.new()[:8]}", packs=self.packs)
        self._held = False

    # one tick ---------------------------------------------------------------------------

    def tick(self) -> list[dict]:
        if not self._held:
            self.lease.acquire()
            self._held = True
        else:
            self.lease.beat()
        cap = self.engine.config.schedule["max_catch_up"]
        out = []
        for pack in self.packs:
            last = _last_ticks(self.engine, pack)
            for job in self.jobs[pack.name]:
                ticks = due_ticks(job, last.get(job["id"]), self.engine.clock.now())
                if not ticks:
                    continue
                if len(ticks) > cap:
                    dropped, ticks = ticks[: len(ticks) - cap], ticks[len(ticks) - cap:]
                    out.append(self._record(pack, job, dropped[-1], status="skipped", missed=True,
                                            skipped_reason="beyond_max_catch_up", skipped_ticks=len(dropped)))
                latest = ticks[-1]
                for t in ticks:
                    out.append(self._run_job(pack, job, t, missed=t < latest))
                    self.lease.beat()
        return out

    def _record(self, pack, job: dict, tick: datetime, *, status: str, missed: bool, skipped_reason: str | None = None,
                skipped_ticks: int = 0, started_at: str | None = None, result: dict | None = None, error: str | None = None) -> dict:
        now = iso(self.engine.clock.now())
        payload = {"job": job["id"], "kind": job["kind"], "tick": iso(tick), "started_at": started_at or now,
                   "finished_at": now, "status": status, "missed": bool(missed), "skipped_reason": skipped_reason,
                   "skipped_ticks": int(skipped_ticks), "result": result, "error": error}
        ev = EventLog(self.engine, pack).append(entity_type="agent_run", entity_id=job["id"], event_type=f"{pack.name}.schedule",
                                                payload=payload, source="pipeline:schedule")
        return dict(payload, pack=pack.name, event_id=ev["event_id"])

    def _run_job(self, pack, job: dict, tick: datetime, *, missed: bool) -> dict:
        started = iso(self.engine.clock.now())
        try:
            if job["kind"] == "sweep":
                skip = self._sweep_skip(pack, job)
                if skip:
                    return self._record(pack, job, tick, status="skipped", missed=missed, skipped_reason=skip, started_at=started)
                result = self._sweep(pack, job)
            elif job["kind"] == "autoloop":
                result = self._autoloop(pack, job, tick)
            elif job["kind"] == "triggers":
                from engine.triggers import dispatch
                recs = dispatch(self.engine, pack)
                result = {"dispatched": len(recs), "runs": [r["run_id"] for r in recs if r["run_id"]]}
            else:
                from engine.remediate import remediation_trigger
                r = remediation_trigger(self.engine, pack, packs_root=pack.root.parent)
                result = {"status": r["status"], "event_id": r.get("event_id")}
        except LeaseHeld:
            raise
        except EngineError as e:
            return self._record(pack, job, tick, status="failed", missed=missed, started_at=started, error=str(e)[:1000])
        return self._record(pack, job, tick, status="ran", missed=missed, started_at=started, result=result)

    def _sweep_skip(self, pack, job: dict) -> str | None:
        from engine.autoloop import kill_rule
        if job["agent"] in kill_rule(self.engine, pack):
            return "halted"
        if job.get("off_peak"):
            from engine.loop import Runner
            from engine.offpeak import in_windows
            a = Runner(self.engine, pack).agent(job["agent"])
            windows = self.engine.config.off_peak_windows(a.model.provider, a.model.name)
            if windows and not in_windows(windows, self.engine.clock.now()):
                return "window_closed"
        return None

    def _sweep(self, pack, job: dict) -> dict:
        from engine.sweep import build_sweep, candidates
        column = job.get("column") or pack.tables[job["table"]].id_field
        inputs = candidates(self.engine, pack, job["agent"], table=job["table"], column=column,
                            input_key=job.get("input_key") or column)
        sweep = build_sweep(self.engine, pack, job["agent"], workers=job.get("workers"),
                            budget_usd=None if job.get("budget_usd") is None else Decimal(str(job["budget_usd"])),
                            judge=bool(job.get("judge")), off_peak=job.get("off_peak"),
                            log=lambda _m: self.lease.beat())
        rep = sweep.run(inputs)
        return {"stop_reason": rep["stop_reason"], "completed": rep["completed"], "candidates": rep["candidates"],
                "cost_usd": rep["cost_usd"]}

    def _autoloop(self, pack, job: dict, tick: datetime) -> dict:
        from engine.autoloop import cycle, render
        from engine.crank import build_report, render as render_crank
        y, w, _ = tick.isocalendar()
        week = f"{y}-W{w:02d}"
        result = cycle(self.engine, pack, week, packs_root=pack.root.parent, max_runs=job.get("max_runs"))
        out = pack.root / "crank"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{week}.md").write_text(render_crank(build_report(self.engine, pack, week)), encoding="utf-8")
        (out / f"autoloop-{week}.md").write_text(render(result), encoding="utf-8")
        (out / f"autoloop-{week}.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return {"week": week, "refine": (result.get("refine") or {}).get("status"), "cycle_seconds": result.get("cycle_seconds")}

    # serving ------------------------------------------------------------------------------

    def next_due(self) -> datetime | None:
        now = self.engine.clock.now()
        best = None
        for pack in self.packs:
            for job in self.jobs[pack.name]:
                k = max(0, math.floor((now - job["anchor"]) / job["every"]) + 1) if now >= job["anchor"] else 0
                t = job["anchor"] + k * job["every"]
                best = t if best is None or t < best else best
        return best

    def serve(self, *, max_ticks: int | None = None, sleep: Callable[[float], None] = time.sleep) -> int:
        """Tick, then sleep until the next due job (waking at least every heartbeat to renew the lease)."""
        n = 0
        try:
            while max_ticks is None or n < max_ticks:
                self.tick()
                n += 1
                if max_ticks is not None and n >= max_ticks:
                    break
                nxt = self.next_due()
                gap = self.lease.heartbeat.total_seconds() if nxt is None else (nxt - self.engine.clock.now()).total_seconds()
                sleep(max(0.0, min(gap, self.lease.heartbeat.total_seconds())))
        finally:
            if self._held:
                self.lease.release()
                self._held = False
        return n


def week_summary(engine: Engine, pack, since: str, until: str) -> dict:
    """The crank's view of the schedule: ticks recorded in the window, how many ran, were missed, skipped, failed."""
    evs = engine.store.query_events(event_type=f"{pack.name}.schedule", since=since, until=until, limit=1_000_000, ascending=True)
    by_job: dict[str, dict] = {}
    for e in evs:
        p = e["payload"]
        j = by_job.setdefault(p["job"], {"ran": 0, "skipped": 0, "failed": 0, "missed": 0})
        j[p["status"]] += 1
        j["missed"] += p["skipped_ticks"] if p["skipped_reason"] == "beyond_max_catch_up" else int(p["missed"])
    beats = engine.store.query_events(event_type=f"{pack.name}.heartbeat", since=since, until=until, limit=1_000_000)
    return {"ticks": len(evs), "missed": sum(j["missed"] for j in by_job.values()), "by_job": by_job, "heartbeats": len(beats)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.schedule")
    p.add_argument("packs", nargs="+")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tick", action="store_true", help="run what is due now, then exit")
    mode.add_argument("--serve", action="store_true", help="tick, sleep until the next due job, repeat")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            sched = Scheduler(engine, [load_pack(n) for n in args.packs])
            if args.tick:
                try:
                    recs = sched.tick()
                finally:
                    sched.lease.release()
                for r in recs:
                    print(json.dumps(r, sort_keys=True, default=str))
                print(f"schedule: {len(recs)} ticks recorded")
            else:
                sched.serve()
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
