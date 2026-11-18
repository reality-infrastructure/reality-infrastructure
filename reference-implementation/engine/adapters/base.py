"""Adapter interface and gateway.

Non-negotiable terms, enforced in code and in tests:
- every vendor record lands as an event within the slot's declared latency SLA
  (a breach is itself logged as ``<pack>.latency_breach``);
- the suppression list is checked before every outbound command, and a block
  is logged as ``<pack>.command_blocked``;
- required disclosure/opt-out flags are carried on every command where the
  slot requires them, or the command is blocked;
- ``export_all`` returns everything the vendor holds about the pack's entities;
- a vendor swap is an adapters.yaml binding change; orchestrator and
  specialist code never name an adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

from engine import vendors
from engine.errors import EngineError, EventError
from engine.events import EventLog
from engine.packs import Pack, import_pack_module
from engine.runtime import parse_iso
from engine.store import Engine


@dataclass(frozen=True)
class EventDraft:
    entity_type: str
    entity_id: str
    event_type: str
    payload: dict
    observed_at: str                 # ISO-8601, when the vendor observed it
    vendor_record_id: str | None = None


@dataclass(frozen=True)
class Command:
    entity_id: str
    action: str
    params: dict = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)   # disclosure, opt_out_honored, ...


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    blocked: bool = False
    reason: str | None = None
    vendor_ref: str | None = None
    transcript: dict | None = None

    def as_dict(self) -> dict:
        return {"accepted": self.accepted, "blocked": self.blocked, "reason": self.reason,
                "vendor_ref": self.vendor_ref, "transcript": self.transcript}


class Adapter(ABC):
    """Implement one per licensed component.  Constructed with the binding's config."""

    id: str = ""

    def __init__(self, config: dict) -> None:
        self.config = dict(config)

    @abstractmethod
    def ingest(self, vendor_payload: Any) -> list[EventDraft]: ...

    @abstractmethod
    def command(self, cmd: Command) -> CommandResult: ...

    @abstractmethod
    def suppression_check(self, entity_id: str) -> bool:
        """True when the entity is suppressed (must NOT be contacted / acted on)."""

    @abstractmethod
    def export_all(self, since: str | None) -> Iterator[dict]: ...


@dataclass
class BoundSlot:
    slot: str
    adapter: Adapter
    latency_sla_seconds: float
    required_flags: tuple[str, ...]


class AdapterGateway:
    """The only path between agents and licensed components."""

    def __init__(self, engine: Engine, pack: Pack, events: EventLog) -> None:
        self._engine = engine
        self._pack = pack
        self._events = events
        self._slots: dict[str, BoundSlot] = {}
        self._bindings: dict[str, str] = {}                  # slot -> binding name serving it
        self._trials: dict[str, tuple[str, Adapter]] = {}     # slot -> (trial binding, adapter) while a trial runs
        self._seq: dict[str, int] = {}
        cfg = pack.adapters_config or {"slots": {}, "bindings": {}}
        for slot, sdoc in sorted(cfg["slots"].items()):
            adapter = self._build(cfg, sdoc["binding"])
            self._bindings[slot] = sdoc["binding"]
            self._slots[slot] = BoundSlot(slot=slot, adapter=adapter,
                                          latency_sla_seconds=float(sdoc["latency_sla_seconds"]),
                                          required_flags=tuple(sdoc.get("required_flags") or ()))
            if sdoc.get("trial"):
                self._open_trial(cfg, slot, sdoc["trial"])

    def _build(self, cfg: dict, name: str) -> Adapter:
        binding = cfg["bindings"][name]
        mod = import_pack_module(self._pack.name, binding["module"], self._pack.root.parent)
        cls = getattr(mod, binding["class"], None)
        if cls is None or not (isinstance(cls, type) and issubclass(cls, Adapter)):
            raise EngineError(f"adapter binding {name!r}: {binding['class']!r} is not an Adapter")
        adapter = cls(binding.get("config") or {})
        if not adapter.id:
            raise EngineError(f"adapter {binding['class']!r} must set a non-empty id")
        return adapter

    # -- vendor record and staged trials (engine.vendors) ----------------------------------

    def _open_trial(self, cfg: dict, slot: str, name: str) -> None:
        if name not in cfg["bindings"]:
            raise EngineError(f"slot {slot!r} trials unknown adapter binding {name!r}")
        done = vendors.decision(self._engine, self._pack, slot, name)
        if done == "promoted":
            self._slots[slot].adapter = self._build(cfg, name)
            self._bindings[slot] = name
        elif done is None:
            self._trials[slot] = (name, self._build(cfg, name))
            self._seq[slot] = sum(1 for e in self._engine.store.query_events(
                event_type=f"{self._pack.name}.vendor_record", limit=1000000)
                if e["payload"]["slot"] == slot and e["payload"]["kind"] in ("command_ok", "command_error"))

    def trial(self, slot: str) -> str | None:
        """The binding on trial for a slot, while its trial runs."""
        return self._trials[slot][0] if slot in self._trials else None

    def _route(self, slot: str) -> tuple[Adapter, str, bool]:
        seq = self._seq.get(slot, 0)
        self._seq[slot] = seq + 1
        share = float(self._engine.config.analytics["adapters"]["trial_share"])
        if slot in self._trials and vendors.routes_to_trial(slot, seq, share):
            name, adapter = self._trials[slot]
            return adapter, name, True
        return self._slots[slot].adapter, self._bindings[slot], False

    def _decide_trial(self, slot: str) -> None:
        name, adapter = self._trials[slot]
        trial = vendors.record_of(self._engine, self._pack, adapter.id, slot=slot, trial=True)
        if trial["commands"] < int(self._engine.config.analytics["adapters"]["trial_min_events"]):
            return
        incumbent = vendors.record_of(self._engine, self._pack, self._slots[slot].adapter.id, slot=slot, trial=False)
        promoted = vendors.no_worse(trial, incumbent)
        self._events.append(
            entity_type="adapter", entity_id=adapter.id,
            event_type=f"{self._pack.name}.binding_{'promoted' if promoted else 'refused'}",
            payload={"slot": slot, "binding": name, "incumbent": self._bindings[slot], "trial_record": trial,
                     "incumbent_record": incumbent},
            source="pipeline:gateway")
        del self._trials[slot]
        if promoted:
            self._slots[slot].adapter = adapter
            self._bindings[slot] = name

    def slots(self) -> list[str]:
        return sorted(self._slots)

    def require_slot(self, slot: str | None) -> BoundSlot:
        if slot is None or slot not in self._slots:
            raise EngineError(f"no adapter bound to slot {slot!r}")
        return self._slots[slot]

    def bound(self, slot: str) -> Adapter:
        return self.require_slot(slot).adapter

    # -- vendor -> event log -------------------------------------------------------

    def ingest(self, slot: str, vendor_payload: Any) -> list[dict]:
        bound = self.require_slot(slot)
        source = f"adapter:{bound.adapter.id}"
        rows = []
        try:
            drafts = bound.adapter.ingest(vendor_payload)
        except Exception as e:  # noqa: BLE001 - an ingest gap goes on the vendor's record, then re-raised
            vendors.note(self._events, self._pack, slot=slot, adapter_id=bound.adapter.id, binding=self._bindings[slot],
                         kind="ingest_error", detail=f"{type(e).__name__}: {e}")
            raise
        for draft in drafts:
            row = self._events.append(
                entity_type=draft.entity_type, entity_id=draft.entity_id,
                event_type=draft.event_type, payload=draft.payload, source=source,
                source_ref=draft.vendor_record_id, observed_at=draft.observed_at)
            rows.append(row)
            latency = (parse_iso(row["recorded_at"]) - parse_iso(row["observed_at"])).total_seconds()
            if latency > bound.latency_sla_seconds:
                self._events.append(
                    entity_type="adapter", entity_id=bound.adapter.id,
                    event_type=f"{self._pack.name}.latency_breach",
                    payload={"slot": slot, "adapter": bound.adapter.id, "event_id": row["event_id"],
                             "latency_seconds": latency, "sla_seconds": bound.latency_sla_seconds},
                    source=source, source_ref=draft.vendor_record_id)
        vendors.note(self._events, self._pack, slot=slot, adapter_id=bound.adapter.id, binding=self._bindings[slot],
                     kind="ingest_ok", detail=str(len(rows)))
        return rows

    # -- your system -> vendor --------------------------------------------------------

    def command(self, slot: str, cmd: Command, *, source_ref: str | None = None) -> CommandResult:
        bound = self.require_slot(slot)
        source = f"adapter:{bound.adapter.id}"

        def block(reason: str) -> CommandResult:
            self._events.append(
                entity_type="adapter", entity_id=bound.adapter.id,
                event_type=f"{self._pack.name}.command_blocked",
                payload={"slot": slot, "adapter": bound.adapter.id, "reason": reason,
                         "command": {"entity_id": cmd.entity_id, "action": cmd.action,
                                     "params": cmd.params, "flags": cmd.flags}},
                source=source, source_ref=source_ref)
            return CommandResult(accepted=False, blocked=True, reason=reason)

        if bound.adapter.suppression_check(cmd.entity_id):
            return block(f"entity {cmd.entity_id!r} is on the suppression list")
        missing = [f for f in bound.required_flags if not cmd.flags.get(f)]
        if missing:
            return block(f"command lacks required flag(s): {', '.join(missing)}")
        adapter, name, on_trial = self._route(slot)
        try:
            result = adapter.command(cmd)
        except Exception as e:  # noqa: BLE001 - a vendor failure goes on its record, then re-raised
            vendors.note(self._events, self._pack, slot=slot, adapter_id=adapter.id, binding=name, kind="command_error",
                         detail=f"{type(e).__name__}: {e}", trial=on_trial)
            raise
        vendors.note(self._events, self._pack, slot=slot, adapter_id=adapter.id, binding=name,
                     kind="command_ok" if result.accepted else "command_error",
                     detail=None if result.accepted else result.reason, trial=on_trial)
        if on_trial:
            self._decide_trial(slot)
        return result

    def export_all(self, slot: str, since: str | None = None) -> list[dict]:
        if since is not None:
            try:
                parse_iso(since)
            except ValueError as e:
                raise EventError(f"since {since!r} is not ISO-8601") from e
        return list(self.require_slot(slot).adapter.export_all(since))
