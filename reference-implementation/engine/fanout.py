"""Parallel modular fan-out under an orchestrator, and the sibling message bus (JH-C11 G-D11, G-B3).

Patel: decompose the task into independent modules, check each locally, try several approaches per module and
keep the best.  Brown: the workers talk to each other, a child may ask instead of guessing, and the amount of
talking is bounded.

``agent.<pack>.<child>`` called with ``inputs: [..]`` runs one child per part (times
``alternatives_per_part``) concurrently on the shared engine, ``workers`` at a time, the same lock discipline
as the sweep (the store serializes writes, provider calls overlap).  Every child is certified by its own
guardrails and verifier; per part the certified alternative with the most RI accept mass is kept.  Only
certified children can be cited: a failed child's output is null and ``run:agent_runs:<id>`` refuses it.
Children carry ``fanout_group`` (a run column) and ``parent_run_id``.

Within a group the children share a ``Bus``: ``siblings.message`` posts a ``<pack>.message`` event and queues the
text for the addressed part(s); a recipient receives at most ``loop.max_inbox_per_turn`` messages at each turn
boundary (the excess is dropped and the drop is shown to it), and a sender may send at most
``loop.max_messages_per_run``.  The group's message count is returned to the orchestrator (zero = the children
worked as independent solvers) and reported by ``coordination``.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from engine.errors import ToolError
from engine.runctx import RunOptions


def fanout_config(config, agent) -> dict:
    cfg = {**config.run_loop["fanout"], **(agent.manifest["loop"].get("fanout") or {})}
    out = {k: int(cfg[k]) for k in ("max_children", "workers", "alternatives_per_part")}
    if min(out.values()) < 1:
        raise ToolError(f"loop.fanout values must be >= 1, got {out}")
    return out


class Bus:
    def __init__(self, *, group: str, parts: int, events, pack_name: str, max_inbox: int, max_per_run: int) -> None:
        self.group, self.parts = group, parts
        self._events, self._pack = events, pack_name
        self._max_inbox, self._max_per_run = max_inbox, max_per_run
        self._inbox: dict[int, list[dict]] = {p: [] for p in range(parts)}
        self._sent: dict[str, int] = {}
        self._lock = threading.Lock()
        self.count = 0

    def post(self, ctx, to: str, text: str) -> dict:
        part = ctx.extra["part"]
        if to == "*":
            targets = [p for p in range(self.parts) if p != part]
        else:
            try:
                targets = [int(to)]
            except ValueError:
                raise ToolError(f"to must be a part index or '*', got {to!r}") from None
            if targets[0] == part or not 0 <= targets[0] < self.parts:
                raise ToolError(f"no sibling part {to!r} (parts 0..{self.parts - 1}, you are {part})")
        with self._lock:
            n = self._sent.get(ctx.run_id, 0)
            if n >= self._max_per_run:
                raise ToolError(f"message budget of {self._max_per_run} per run exhausted")
            self._sent[ctx.run_id] = n + 1
        row = self._events.append(
            entity_type="agent_run", entity_id=ctx.run_id, event_type=f"{self._pack}.message",
            payload={"group": self.group, "from_run_id": ctx.run_id, "from_part": part, "to_part": to, "text": text},
            source=f"agent:{ctx.agent.name}", source_ref=ctx.run_id)
        msg = {"from_part": part, "text": text, "event_id": row["event_id"]}
        with self._lock:
            for t in targets:
                self._inbox[t].append(msg)
            self.count += 1
        return {"sent_to": targets, "event_id": row["event_id"]}

    def drain(self, part: int) -> tuple[list[dict], int]:
        with self._lock:
            waiting = self._inbox[part]
            self._inbox[part] = []
        return waiting[: self._max_inbox], max(0, len(waiting) - self._max_inbox)


def _accept_mass(row: dict) -> Decimal:
    for it in row["iterations"]:
        for cand in it.get("candidates", []):
            if cand.get("accepted") and cand.get("judgement"):
                return Decimal(cand["judgement"]["accept"])
    return Decimal(0)


def fan_out(runner, parent_agent, child: str, inputs: list[dict], parent_trace, depth: int,
            base: RunOptions) -> dict:
    cfg = fanout_config(runner.config, parent_agent)
    alts = cfg["alternatives_per_part"]
    if len(inputs) * alts > cfg["max_children"]:
        raise ToolError(f"fan-out of {len(inputs)} parts x {alts} alternatives exceeds max_children "
                        f"{cfg['max_children']}")
    parent_trace.state["fanouts"] += 1
    group = f"{parent_trace.run_id}:{parent_trace.state['fanouts']}"
    loop_cfg = runner.config.run_loop
    bus = Bus(group=group, parts=len(inputs), events=runner.events, pack_name=runner.pack.name,
              max_inbox=loop_cfg["max_inbox_per_turn"], max_per_run=loop_cfg["max_messages_per_run"])
    tasks = [(part, alt) for part in range(len(inputs)) for alt in range(alts)]

    def one(task):
        part, _ = task
        opts = RunOptions(fanout_group=group, part=part, parts=len(inputs), bus=bus, scratch_scope=group,
                          forked=base.forked, may_clarify=base.may_clarify)
        return runner.run(child, inputs[part], parent_run_id=parent_trace.run_id, depth=depth, options=opts)

    with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
        results = list(pool.map(one, tasks))
    parts = []
    for part in range(len(inputs)):
        tries = [r for (p, _), r in zip(tasks, results) if p == part]
        for r in tries:
            parent_trace.add_child_cost(r.cost_usd)
            parent_trace.state["clarifications"] += int(r.status == "needs_clarification")
        certified = [r for r in tries if r.status == "succeeded"]
        best = max(certified, key=lambda r: _accept_mass(r.row)) if certified else tries[0]
        parts.append({"part": part, **best.as_dict(), "alternatives": [r.run_id for r in tries]})
    return {"fanout_group": group, "parts": parts, "messages": bus.count}


def coordination(engine, pack, since: str, until: str) -> dict:
    """Messages per fan-out child run in a window: 0.0 means the children never coordinated."""
    children = [r for r in engine.store.list_runs(pack=pack.name, since=since, until=until) if r.get("fanout_group")]
    msgs = engine.store.query_events(event_type=f"{pack.name}.message", since=since, until=until, limit=1_000_000)
    groups = {r["fanout_group"] for r in children}
    return {"fanout_groups": len(groups), "child_runs": len(children), "messages": len(msgs),
            "messages_per_child_run": round(len(msgs) / len(children), 4) if children else None}
