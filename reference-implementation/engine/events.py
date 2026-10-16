"""Event log API.  Every real action is one event; nothing is ever fabricated.

Event types are declared in the pack's events.yaml with a payload JSON Schema.
The engine adds its own types for a pack: ``<pack>.verdict``,
``<pack>.correction``, ``<pack>.command_blocked``, ``<pack>.latency_breach``
and ``compaction.summary``.  Undeclared types are rejected before any write.
Each accepted event is bound to the RI ledger in the same transaction.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from engine.config import CONFIG_DIR
from engine.errors import EventError
from engine.runtime import iso, parse_iso
from engine.schema import validation_errors
from engine.store import Engine, event_ledger_entry

_TYPE_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_SOURCE_RE = re.compile(r"^(human|agent:[A-Za-z0-9_.\-/]+|adapter:[A-Za-z0-9_.\-]+|pipeline:[A-Za-z0-9_.\-]+)$")
COMPACTION_TYPE = "compaction.summary"
ENGINE_ENTITY_TYPES = frozenset({"agent_run", "adapter", "compaction"})


def _engine_event_schemas() -> dict[str, dict]:
    path = CONFIG_DIR / "engine-events.json"
    return json.loads(path.read_text(encoding="utf-8"))


def engine_event_types(pack_name: str) -> dict[str, dict]:
    """Engine-owned event types for a pack, keyed by concrete type name."""
    out = {}
    for suffix, schema in _engine_event_schemas().items():
        name = suffix if "." in suffix else f"{pack_name}.{suffix}"
        out[name] = schema
    return out


class EventLog:
    def __init__(self, engine: Engine, pack) -> None:
        self._engine = engine
        self._pack = pack
        declared = dict(pack.event_types)
        for name, schema in engine_event_types(pack.name).items():
            if name in declared:
                raise EventError(f"pack {pack.name!r} redeclares engine-owned event type {name!r}")
            declared[name] = schema
        self._types = declared

    @property
    def declared_types(self) -> dict[str, dict]:
        return dict(self._types)

    # -- validation ------------------------------------------------------------

    def validate(self, event_type: str, payload: Any, entity_type: str, source: str) -> None:
        if not _TYPE_RE.match(event_type or ""):
            raise EventError(f"event_type {event_type!r} must look like <pack>.<verb>")
        schema = self._types.get(event_type)
        if schema is None:
            raise EventError(f"undeclared event type {event_type!r}; declare it in events.yaml")
        if not isinstance(payload, dict):
            raise EventError("payload must be an object")
        errs = validation_errors(schema, payload)
        if errs:
            raise EventError(f"payload for {event_type!r} failed schema: " + "; ".join(errs))
        if entity_type not in self._pack.entity_types and entity_type not in ENGINE_ENTITY_TYPES:
            raise EventError(f"entity_type {entity_type!r} is not declared in pack.yaml")
        if not _SOURCE_RE.match(source or ""):
            raise EventError(f"source {source!r} must be human | agent:<name> | adapter:<id> | pipeline:<id>")

    # -- writes -------------------------------------------------------------------

    def append(self, *, entity_type: str, entity_id: str, event_type: str, payload: dict,
               source: str, source_ref: str | None = None,
               observed_at: datetime | str | None = None) -> dict:
        self.validate(event_type, payload, entity_type, source)
        if not isinstance(entity_id, str) or not entity_id:
            raise EventError("entity_id must be a non-empty string")
        now = self._engine.clock.now()
        if observed_at is None:
            observed = now
        elif isinstance(observed_at, str):
            try:
                observed = parse_iso(observed_at)
            except ValueError as e:
                raise EventError(f"observed_at {observed_at!r} is not ISO-8601") from e
        else:
            observed = observed_at
        row = {
            "event_id": self._engine.ids.new(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "source_ref": source_ref,
            "observed_at": iso(observed),
            "recorded_at": iso(now),
        }
        with self._engine.store.transaction():
            receipt = self._engine.ledger.append(event_ledger_entry(row))
            row["ledger_index"] = receipt.index
            row["leaf_hash"] = receipt.leaf_hash
            self._engine.store.insert_event(row)
        return row

    def correction(self, *, entity_type: str, entity_id: str, corrects_event_id: str,
                   reason: str, payload: dict, source: str, source_ref: str | None = None) -> dict:
        target = self._engine.store.get_event(corrects_event_id)
        if target is None:
            raise EventError(f"cannot correct unknown event {corrects_event_id!r}")
        return self.append(
            entity_type=entity_type, entity_id=entity_id,
            event_type=f"{self._pack.name}.correction",
            payload={"corrects_event_id": corrects_event_id, "reason": reason, "payload": payload},
            source=source, source_ref=source_ref)

    # -- reads ----------------------------------------------------------------------

    def query(self, **filters) -> list[dict]:
        limit = filters.pop("limit", 50)
        if not isinstance(limit, int) or limit < 1:
            raise EventError("limit must be a positive integer")
        return self._engine.store.query_events(limit=limit, **filters)

    def get(self, event_id: str) -> dict | None:
        return self._engine.store.get_event(event_id)
