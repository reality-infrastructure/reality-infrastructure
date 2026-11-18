"""Vendor record and staged binding trials (JH-C11 wpF, G-NCD7).

Naval: play a repeat game, and judge a counterparty by its record, not its pitch.  The adapter
gateway writes a ``<pack>.vendor_record`` event for every command outcome and every ingest (or ingest
failure); with the gateway's own ``latency_breach`` and ``command_blocked`` events that is each vendor's
record, and the crank renders the scorecard from it instead of a hand-written file.

A slot in adapters.yaml may name a ``trial`` binding.  The gateway then sends ``adapters.trial_share`` of
the slot's commands (chosen by a hash of the slot and the command's sequence number, never at random)
to the trial vendor; once the trial has ``adapters.trial_min_events`` commands, it is promoted to the
whole slot only if its error rate is no worse than the incumbent's (``<pack>.binding_promoted``), else
refused (``<pack>.binding_refused``).  The decision is an event, so a new gateway honours it.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

RECORD_KINDS = ("command_ok", "command_error", "ingest_ok", "ingest_error")


def note(events, pack, *, slot: str, adapter_id: str, binding: str, kind: str, detail: str | None = None,
         trial: bool = False) -> dict:
    return events.append(entity_type="adapter", entity_id=adapter_id, event_type=f"{pack.name}.vendor_record",
                         payload={"slot": slot, "adapter": adapter_id, "binding": binding, "kind": kind,
                                  "detail": None if detail is None else str(detail)[:300], "trial": trial},
                         source=f"adapter:{adapter_id}")


def _events(engine, pack, suffix: str, since: str | None, until: str | None) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{suffix}", since=since, until=until, limit=1000000, ascending=True)


def record_of(engine, pack, adapter_id: str, *, slot: str | None = None, since: str | None = None,
              until: str | None = None, trial: bool | None = None) -> dict:
    """One vendor's record over a period, from the gateway's own events."""
    recs = [e["payload"] for e in _events(engine, pack, "vendor_record", since, until)
            if e["payload"]["adapter"] == adapter_id and (slot is None or e["payload"]["slot"] == slot)
            and (trial is None or e["payload"].get("trial") == trial)]
    breaches = [e for e in _events(engine, pack, "latency_breach", since, until) if e["payload"]["adapter"] == adapter_id
                and (slot is None or e["payload"]["slot"] == slot)]
    blocked = [e for e in _events(engine, pack, "command_blocked", since, until) if e["payload"]["adapter"] == adapter_id
               and (slot is None or e["payload"]["slot"] == slot)]
    commands = sum(1 for r in recs if r["kind"] in ("command_ok", "command_error"))
    cmd_err = sum(1 for r in recs if r["kind"] == "command_error")
    ingested = sum(int(r["detail"] or 0) for r in recs if r["kind"] == "ingest_ok")
    ing_err = sum(1 for r in recs if r["kind"] == "ingest_error")
    units = commands + ingested
    errors = cmd_err + ing_err + len(breaches)
    return {"adapter": adapter_id, "commands": commands, "command_errors": cmd_err, "records_ingested": ingested,
            "ingest_errors": ing_err, "latency_breaches": len(breaches), "commands_blocked": len(blocked),
            "error_rate": None if not units else str((Decimal(errors) / units).quantize(Decimal("0.0001")))}


def routes_to_trial(slot: str, seq: int, share: float) -> bool:
    h = int(hashlib.sha256(f"trial:{slot}:{seq}".encode()).hexdigest()[:8], 16)
    return h / 0xFFFFFFFF < share


def decision(engine, pack, slot: str, binding: str) -> str | None:
    """'promoted' or 'refused' when the trial of ``binding`` on ``slot`` was decided, else None."""
    for kind in ("binding_promoted", "binding_refused"):
        if any(e["payload"]["slot"] == slot and e["payload"]["binding"] == binding for e in _events(engine, pack, kind, None, None)):
            return kind.split("_")[1]
    return None


def no_worse(trial: dict, incumbent: dict) -> bool:
    t = Decimal(trial["error_rate"] or "0")
    i = Decimal(incumbent["error_rate"] or "0")
    return t <= i


def scorecard(engine, pack, week: str) -> list[dict]:
    from engine.crank import week_bounds
    from engine.runtime import iso
    cfg = pack.adapters_config
    if not cfg:
        return []
    start, end = week_bounds(week)
    out = []
    for slot, sdoc in sorted(cfg["slots"].items()):
        for role, binding in (("incumbent", sdoc["binding"]), ("trial", sdoc.get("trial"))):
            if binding is None:
                continue
            adapter_id = _adapter_id(pack, binding)
            out.append({"slot": slot, "binding": binding, "role": role, "decision": decision(engine, pack, slot, binding) if role == "trial" else None,
                        "week": record_of(engine, pack, adapter_id, slot=slot, since=iso(start), until=iso(end)),
                        "all_time": record_of(engine, pack, adapter_id, slot=slot)})
    return out


def _adapter_id(pack, binding: str) -> str:
    from engine.packs import import_pack_module
    b = pack.adapters_config["bindings"][binding]
    return getattr(getattr(import_pack_module(pack.name, b["module"], pack.root.parent), b["class"]), "id", binding)


def render(report_: dict) -> list[str]:
    L = ["", "## Vendor record (from the gateway's own events)", ""]
    if not report_["vendor_record"]:
        return L + ["- the pack binds no adapter"]
    L += ["| slot | binding | role | commands | errors | ingested | ingest errors | latency breaches | blocked | error rate (all time) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for v in report_["vendor_record"]:
        a = v["all_time"]
        L.append(f"| {v['slot']} | {v['binding']} | {v['role']}{' (' + v['decision'] + ')' if v['decision'] else ''} | {a['commands']} | "
                 f"{a['command_errors']} | {a['records_ingested']} | {a['ingest_errors']} | {a['latency_breaches']} | "
                 f"{a['commands_blocked']} | {a['error_rate'] or '—'} |")
    return L
