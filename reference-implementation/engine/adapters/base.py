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
        cfg = pack.adapters_config or {"slots": {}, "bindings": {}}
        for slot, sdoc in sorted(cfg["slots"].items()):
            binding = cfg["bindings"][sdoc["binding"]]
            mod = import_pack_module(pack.name, binding["module"], pack.root.parent)
            cls = getattr(mod, binding["class"], None)
            if cls is None or not (isinstance(cls, type) and issubclass(cls, Adapter)):
                raise EngineError(f"adapter binding {sdoc['binding']!r}: {binding['class']!r} is not an Adapter")
            adapter = cls(binding.get("config") or {})
            if not adapter.id:
                raise EngineError(f"adapter {binding['class']!r} must set a non-empty id")
            self._slots[slot] = BoundSlot(slot=slot, adapter=adapter,
                                          latency_sla_seconds=float(sdoc["latency_sla_seconds"]),
                                          required_flags=tuple(sdoc.get("required_flags") or ()))

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
        for draft in bound.adapter.ingest(vendor_payload):
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
        return bound.adapter.command(cmd)

    def export_all(self, slot: str, since: str | None = None) -> list[dict]:
        if since is not None:
            try:
                parse_iso(since)
            except ValueError as e:
                raise EventError(f"since {since!r} is not ISO-8601") from e
        return list(self.require_slot(slot).adapter.export_all(since))
