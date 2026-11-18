"""Rollout: a new agent version earns its volume.

Musk ramps a new line on an S-curve, not a jump, and a version that has not proved itself runs small.
Patel's loop switches to the adopted version the moment it exists instead of finishing a long run on the
superseded one.  Per manifest_hash (the version, every file of the agent hashed):

  burn-in   fewer than ``rollout.burn_in_runs`` runs, or a pass rate below ``rollout.min_pass_rate`` on them:
            the sweep runs one worker and at most the burn-in count of inputs
  ramp      after burn-in, workers start at ``rollout.start_workers`` and double after each
            ``rollout.step_runs`` completions while the window pass rate holds, halve when it falls, and stop
            doubling when the doubled step's throughput gains less than ``sizing.min_gain`` (the provider is
            saturated: more workers buy nothing)
  tiers     a version may run up to the next of ``rollout.tiers`` total runs; passing one tier opens the next
  switch    every ``sweep.kill_check_every`` completions the sweep re-hashes the agent; an adopted edit changes
            the hash and the remaining inputs run on the new version (``<pack>.version_switch``)

Events: ``<pack>.rollout`` {manifest_hash, tier, workers, pass_rate, ...}.
"""

from __future__ import annotations

from datetime import datetime

from engine.events import EventLog
from engine.store import Engine


def version_record(engine: Engine, pack, agent: str, manifest_hash: str) -> dict:
    rows = [r for r in engine.store.list_runs(pack=pack.name, agent=agent) if r["manifest_hash"] == manifest_hash]
    ok = sum(1 for r in rows if r["status"] == "succeeded")
    return {"runs": len(rows), "succeeded": ok, "pass_rate": (ok / len(rows)) if rows else None}


def plan(engine: Engine, pack, agent: str, manifest_hash: str, *, requested_workers: int, cfg: dict) -> dict:
    """The volume this version may run in one sweep: {mode, workers, start_workers, limit, tier, ...}."""
    rec = version_record(engine, pack, agent, manifest_hash)
    n, rate = rec["runs"], rec["pass_rate"]
    base = {"agent": agent, "manifest_hash": manifest_hash, "runs": n,
            "pass_rate": None if rate is None else round(rate, 4)}
    if n < cfg["burn_in_runs"] or (rate is not None and rate < cfg["min_pass_rate"]):
        limit = cfg["burn_in_runs"] - n if n < cfg["burn_in_runs"] else cfg["burn_in_runs"]
        why = (f"{n} runs on this version, burn-in needs {cfg['burn_in_runs']}" if n < cfg["burn_in_runs"]
               else f"pass rate {rate:.3f} on this version is below {cfg['min_pass_rate']}")
        return {**base, "mode": "burn_in", "workers": 1, "start_workers": 1, "limit": max(0, limit), "tier": 0, "why": why}
    tiers = cfg["tiers"]
    tier = next((i for i, t in enumerate(tiers) if t > n), None)
    limit = None if tier is None else tiers[tier] - n
    return {**base, "mode": "ramp", "workers": int(requested_workers),
            "start_workers": min(cfg["start_workers"], int(requested_workers)), "limit": limit,
            "tier": len(tiers) if tier is None else tier + 1,
            "why": ("past every volume tier" if tier is None else f"tier {tier + 1}: up to {tiers[tier]} runs on this version")}


class Ramp:
    """Workers on an S-curve: double after a healthy step, halve after a failing one, freeze when saturated."""

    def __init__(self, *, start: int, ceiling: int, step_runs: int, min_pass_rate: float, min_gain: float | None,
                 now: datetime) -> None:
        self.workers, self.ceiling = max(1, start), max(1, ceiling)
        self.step_runs, self.min_pass_rate, self.min_gain = step_runs, min_pass_rate, min_gain
        self.saturated = False
        self._window: list[bool] = []
        self._step_start = now
        self._prev: tuple[int, float] | None = None         # (workers, throughput) of the step before the last doubling
        self.history: list[dict] = []

    def on_completion(self, succeeded: bool, now: datetime) -> dict | None:
        """Feed one completion; returns the change {workers, from, why, ...} when the worker count changes."""
        self._window.append(bool(succeeded))
        if len(self._window) < self.step_runs:
            return None
        rate = sum(self._window) / len(self._window)
        seconds = max((now - self._step_start).total_seconds(), 1e-9)
        throughput = len(self._window) / seconds
        self._window, self._step_start = [], now
        old = self.workers
        step = {"workers": old, "pass_rate": round(rate, 4), "throughput_per_s": round(throughput, 6)}
        self.history.append(step)
        if rate < self.min_pass_rate:
            self.workers, why = max(1, old // 2), f"window pass rate {rate:.3f} below {self.min_pass_rate}: halve"
            self._prev = None
        elif self.saturated or old >= self.ceiling:
            return None
        elif (self._prev is not None and self.min_gain is not None and self._prev[0] < old
              and throughput < self._prev[1] * (1 + self.min_gain)):
            self.workers, self.saturated = self._prev[0], True
            why = (f"saturated: {old} workers gave {throughput:.4f}/s against {self._prev[1]:.4f}/s at {self._prev[0]}, "
                   f"a gain below {self.min_gain:.0%}; back to {self._prev[0]} and no more doubling")
        else:
            self._prev = (old, throughput)
            self.workers, why = min(self.ceiling, old * 2), f"window pass rate {rate:.3f} holds: double"
        if self.workers == old:
            return None
        return {"from": old, "workers": self.workers, "pass_rate": round(rate, 4),
                "throughput_per_s": round(throughput, 6), "saturated": self.saturated, "why": why}


def record(engine: Engine, pack, agent: str, payload: dict) -> dict:
    return EventLog(engine, pack).append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.rollout",
                                         payload=payload, source="pipeline:sweep")


def by_version(runs: list[dict]) -> dict:
    """Per agent, per manifest_hash: runs and pass rate (the crank's view of each version)."""
    out: dict[str, dict] = {}
    for r in runs:
        v = out.setdefault(r["agent"], {}).setdefault(r["manifest_hash"], {"runs": 0, "succeeded": 0})
        v["runs"] += 1
        v["succeeded"] += int(r["status"] == "succeeded")
    for versions in out.values():
        for v in versions.values():
            v["pass_rate"] = round(v["succeeded"] / v["runs"], 4)
    return out
