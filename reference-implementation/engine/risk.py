"""The ruin guard on external effects (JH-C11 G-NAB4, G-NCD5).

Naval: "never risk ruin"; "what is true for a hundred people on average isn't the same as one person averaging
that same thing a hundred times".  Every outbound command passes ``RiskGuard.check`` in the adapter gateway after
the suppression and disclosure checks and before the vendor sees it.  A command is BLOCKED (never queued), with a
``<pack>.risk_block`` event naming the rule, when:

- ``ruin_halt``                 the agent was halted by a ruinous loss and no human has lifted the halt;
- ``max_external_per_run``      the run already sent ``risk.max_external_per_run`` commands;
- ``max_external_per_cycle``    the pack already sent ``risk.max_external_per_cycle`` commands this ISO week;
- ``stake_undeclared``          the slot declares ``exposure_field`` and the command does not carry a number there;
- ``max_exposure``              the slot's exposure this week plus this command's ``at_risk`` exceeds ``max_exposure``;
- ``stake``                     ``at_risk`` exceeds ``max_fraction_per_action`` of the slot's remaining capacity
                                (``capacity`` minus every realised loss on the slot minus this week's exposure);
- ``irreversible_needs_approval`` the slot is ``irreversible: true`` and no unused human ``<pack>.approval``
                                cites this exact command (by sha256).

A sent command is a ``<pack>.command_sent`` event (the record the caps count).  A realised loss is a
``<pack>.loss`` event; one loss at or above the slot's ruin threshold (``ruin_threshold``, else
``risk.ruin_fraction`` of ``capacity``) writes ``<pack>.ruin_halt``: the agent is halted like the kill rule
(engine.autoloop.kill_rule lists it, the sweep and the planner stop) whatever its average pass rate, and the
gateway refuses its commands, until a human writes ``<pack>.ruin_lift``.

The capacity a stake is sized against is the slot's declared capital, in the slot's own unit.  The sweep's
model-spend budget is USD of provider calls, a different unit, and is not used as capacity.

    python -m engine.risk approve <pack> <risk_block_event_id> --reason TEXT [--db DSN]
    python -m engine.risk loss <pack> <agent> --slot S --amount X --why TEXT [--run RUN_ID] [--db DSN]
    python -m engine.risk lift <pack> <agent> --reason TEXT [--db DSN]
    python -m engine.risk status <pack> [--db DSN]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from engine.errors import EngineError
from engine.hashing import sha256_json
from engine.runtime import iso

_ALL = 1_000_000


def command_sha256(slot: str, cmd) -> str:
    return sha256_json({"slot": slot, "entity_id": cmd.entity_id, "action": cmd.action,
                        "params": cmd.params, "flags": cmd.flags})


def _cycle_start(engine) -> str:
    now = engine.clock.now()
    start = (now - timedelta(days=now.isocalendar().weekday - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return iso(start)


def _number(v) -> Decimal | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def slot_doc(pack, slot: str) -> dict:
    return dict(((pack.adapters_config or {}).get("slots") or {}).get(slot) or {})


def ruin_threshold(engine, pack, slot: str) -> Decimal | None:
    doc = slot_doc(pack, slot)
    if doc.get("ruin_threshold") is not None:
        return Decimal(str(doc["ruin_threshold"]))
    if doc.get("capacity") is not None:
        return Decimal(str(doc["capacity"])) * engine.config.risk["ruin_fraction"]
    return None


def ruin_halts(engine, pack) -> dict[str, str]:
    """{agent: why} for every agent with a ruin halt no human has lifted."""
    halts = engine.store.query_events(event_type=f"{pack.name}.ruin_halt", limit=_ALL, ascending=True)
    lifts = engine.store.query_events(event_type=f"{pack.name}.ruin_lift", limit=_ALL, ascending=True)
    lifted = {e["payload"]["ruin_halt_event_id"] for e in lifts if e["source"] == "human"}
    out: dict[str, str] = {}
    for e in halts:
        if e["event_id"] in lifted:
            continue
        p = e["payload"]
        out[p["agent"]] = (f"ruin halt: one loss of {p['loss']} on slot {p['slot']} reached the threshold "
                           f"{p['threshold']} (event {e['event_id']}); a human must lift it")
    return out


class RiskGuard:
    def __init__(self, engine, pack, events) -> None:
        self._engine, self._pack, self._events = engine, pack, events
        self._cfg = engine.config.risk

    def _sent(self, since: str | None) -> list[dict]:
        return self._engine.store.query_events(event_type=f"{self._pack.name}.command_sent", since=since,
                                               limit=_ALL, ascending=True)

    def _block(self, slot, adapter_id, cmd, digest, rule, attempted, cap, run_id, agent, command_result_cls):
        self._events.append(
            entity_type="adapter", entity_id=adapter_id, event_type=f"{self._pack.name}.risk_block",
            payload={"run_id": run_id, "agent": agent, "slot": slot, "rule": rule,
                     "attempted": None if attempted is None else float(attempted),
                     "cap": None if cap is None else float(cap),
                     "command": {"entity_id": cmd.entity_id, "action": cmd.action, "params": cmd.params,
                                 "flags": cmd.flags},
                     "command_sha256": digest},
            source=f"adapter:{adapter_id}", source_ref=run_id)
        return command_result_cls(accepted=False, blocked=True, reason=f"risk: {rule}")

    def check(self, slot: str, adapter_id: str, cmd, *, run_id: str | None, agent: str | None, result_cls):
        """(blocked CommandResult | None, at_risk, approval_event_id)."""
        digest = command_sha256(slot, cmd)
        doc = slot_doc(self._pack, slot)

        def block(rule, attempted=None, cap=None):
            return self._block(slot, adapter_id, cmd, digest, rule, attempted, cap, run_id, agent, result_cls), None, None

        if agent is not None and agent in ruin_halts(self._engine, self._pack):
            return block("ruin_halt")
        cycle = self._sent(_cycle_start(self._engine))
        if run_id is not None:
            in_run = sum(1 for e in cycle if e["payload"]["run_id"] == run_id)
            if in_run >= self._cfg["max_external_per_run"]:
                return block("max_external_per_run", in_run + 1, self._cfg["max_external_per_run"])
        if len(cycle) >= self._cfg["max_external_per_cycle"]:
            return block("max_external_per_cycle", len(cycle) + 1, self._cfg["max_external_per_cycle"])
        at_risk = None
        field = doc.get("exposure_field")
        if field:
            at_risk = _number(cmd.params.get(field))
            if at_risk is None or at_risk < 0:
                return block("stake_undeclared")
            open_exposure = sum((Decimal(str(e["payload"]["at_risk"])) for e in cycle
                                 if e["payload"]["slot"] == slot and e["payload"]["at_risk"] is not None), Decimal(0))
            if doc.get("max_exposure") is not None and open_exposure + at_risk > Decimal(str(doc["max_exposure"])):
                return block("max_exposure", open_exposure + at_risk, doc["max_exposure"])
            if doc.get("capacity") is not None:
                losses = self._engine.store.query_events(event_type=f"{self._pack.name}.loss", limit=_ALL)
                lost = sum((Decimal(str(e["payload"]["amount"])) for e in losses if e["payload"]["slot"] == slot),
                           Decimal(0))
                remaining = Decimal(str(doc["capacity"])) - lost - open_exposure
                fraction = Decimal(str(doc.get("max_fraction_per_action", self._cfg["max_fraction_per_action"])))
                cap = max(remaining, Decimal(0)) * fraction
                if at_risk > cap:
                    return block("stake", at_risk, cap)
        approval_id = None
        if doc.get("irreversible"):
            approvals = self._engine.store.query_events(event_type=f"{self._pack.name}.approval", limit=_ALL,
                                                        ascending=True)
            used = {e["payload"]["approval_event_id"] for e in self._sent(None)}
            free = [e for e in approvals if e["source"] == "human" and e["payload"]["command_sha256"] == digest
                    and e["event_id"] not in used]
            if not free:
                return block("irreversible_needs_approval")
            approval_id = free[0]["event_id"]
        return None, at_risk, approval_id

    def sent(self, slot: str, adapter_id: str, cmd, result, *, run_id, agent, at_risk, approval_id) -> dict:
        return self._events.append(
            entity_type="adapter", entity_id=adapter_id, event_type=f"{self._pack.name}.command_sent",
            payload={"run_id": run_id, "agent": agent, "slot": slot, "adapter": adapter_id,
                     "command_sha256": command_sha256(slot, cmd),
                     "at_risk": None if at_risk is None else float(at_risk), "accepted": bool(result.accepted),
                     "vendor_ref": result.vendor_ref, "approval_event_id": approval_id},
            source=f"adapter:{adapter_id}", source_ref=run_id)


# -- operator actions ---------------------------------------------------------------------------

def approve(engine, pack, gateway, events, risk_block_event_id: str, reason: str):
    """A human approves a pending irreversible command and the gateway sends it (every other rule still applies)."""
    from engine.adapters.base import Command
    block = engine.store.get_event(risk_block_event_id)
    if block is None or block["event_type"] != f"{pack.name}.risk_block":
        raise EngineError(f"no risk_block event {risk_block_event_id!r} in pack {pack.name!r}")
    p = block["payload"]
    if p["rule"] != "irreversible_needs_approval":
        raise EngineError(f"risk_block {risk_block_event_id} is rule {p['rule']!r}; only a pending irreversible "
                          f"command waits for approval")
    if not reason.strip():
        raise EngineError("an approval needs a reason")
    events.append(
        entity_type="adapter", entity_id=block["entity_id"], event_type=f"{pack.name}.approval",
        payload={"risk_block_event_id": risk_block_event_id, "command_sha256": p["command_sha256"], "reason": reason},
        source="human", source_ref=p["run_id"])
    cmd = Command(entity_id=p["command"]["entity_id"], action=p["command"]["action"],
                  params=p["command"]["params"], flags=p["command"]["flags"])
    return gateway.command(p["slot"], cmd, source_ref=p["run_id"], agent=p["agent"])


def record_loss(engine, pack, events, *, agent: str, slot: str, amount, why: str, run_id: str | None = None,
                source: str = "human") -> dict:
    """Record a realised loss; one at or above the slot's ruin threshold halts the agent."""
    amt = _number(amount)
    if amt is None or amt < 0:
        raise EngineError(f"loss amount must be a non-negative number, got {amount!r}")
    if slot not in ((pack.adapters_config or {}).get("slots") or {}):
        raise EngineError(f"no adapter slot {slot!r} in pack {pack.name!r}")
    row = events.append(entity_type="agent", entity_id=agent, event_type=f"{pack.name}.loss",
                        payload={"agent": agent, "slot": slot, "amount": float(amt), "run_id": run_id, "why": why},
                        source=source, source_ref=run_id)
    threshold = ruin_threshold(engine, pack, slot)
    if threshold is not None and amt >= threshold:
        events.append(entity_type="agent", entity_id=agent, event_type=f"{pack.name}.ruin_halt",
                      payload={"agent": agent, "slot": slot, "loss": float(amt), "threshold": float(threshold),
                               "loss_event_id": row["event_id"]},
                      source="pipeline:risk", source_ref=row["event_id"])
    return row


def lift(engine, pack, events, agent: str, reason: str) -> list[dict]:
    """A human lifts every open ruin halt of ``agent``."""
    if not reason.strip():
        raise EngineError("lifting a ruin halt needs a reason")
    halts = engine.store.query_events(event_type=f"{pack.name}.ruin_halt", entity_type="agent", entity_id=agent,
                                      limit=_ALL, ascending=True)
    lifts = engine.store.query_events(event_type=f"{pack.name}.ruin_lift", limit=_ALL)
    done = {e["payload"]["ruin_halt_event_id"] for e in lifts if e["source"] == "human"}
    open_halts = [h for h in halts if h["event_id"] not in done]
    if not open_halts:
        raise EngineError(f"agent {agent!r} has no open ruin halt")
    return [events.append(entity_type="agent", entity_id=agent, event_type=f"{pack.name}.ruin_lift",
                          payload={"agent": agent, "ruin_halt_event_id": h["event_id"], "reason": reason},
                          source="human") for h in open_halts]


def main(argv: list[str] | None = None) -> int:
    from engine.loop import Runner
    from engine.packs import load_pack
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.risk")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("approve"); a.add_argument("pack"); a.add_argument("event_id"); a.add_argument("--reason", required=True)
    lo = sub.add_parser("loss"); lo.add_argument("pack"); lo.add_argument("agent"); lo.add_argument("--slot", required=True)
    lo.add_argument("--amount", required=True); lo.add_argument("--why", required=True); lo.add_argument("--run")
    li = sub.add_parser("lift"); li.add_argument("pack"); li.add_argument("agent"); li.add_argument("--reason", required=True)
    st = sub.add_parser("status"); st.add_argument("pack")
    for sp in (a, lo, li, st):
        sp.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            pack = load_pack(args.pack)
            runner = Runner(engine, pack)
            if args.cmd == "approve":
                if runner.gateway is None:
                    raise EngineError(f"pack {pack.name!r} has no adapters")
                out = approve(engine, pack, runner.gateway, runner.events, args.event_id, args.reason).as_dict()
            elif args.cmd == "loss":
                out = record_loss(engine, pack, runner.events, agent=args.agent, slot=args.slot, amount=args.amount,
                                  why=args.why, run_id=args.run)
            elif args.cmd == "lift":
                out = lift(engine, pack, runner.events, args.agent, args.reason)
            else:
                out = ruin_halts(engine, pack)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
