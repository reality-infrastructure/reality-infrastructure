"""Mock vendor B: a different wire shape ``{"items": [{"key", "amount", "ts"}]}``, same slot."""

from __future__ import annotations

from typing import Any, Iterator

from engine.adapters.base import Adapter, Command, CommandResult, EventDraft


class MockVendorB(Adapter):
    id = "mock_b"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._suppressed = set(config.get("suppressed") or [])
        self._items: list[dict] = []
        self._commands: list[dict] = []

    def ingest(self, vendor_payload: Any) -> list[EventDraft]:
        drafts = []
        for item in vendor_payload["items"]:
            self._items.append(dict(item))
            drafts.append(EventDraft(
                entity_type="record", entity_id=str(item["key"]),
                event_type="_reference.record_observed",
                payload={"record_id": str(item["key"]), "value": item["amount"], "vendor": self.id},
                observed_at=item["ts"], vendor_record_id=f"B:{item['key']}"))
        return drafts

    def command(self, cmd: Command) -> CommandResult:
        ref = f"B-{len(self._commands) + 1:04d}"
        self._commands.append({"ref": ref, "entity_id": cmd.entity_id, "action": cmd.action,
                               "params": dict(cmd.params), "flags": dict(cmd.flags)})
        return CommandResult(accepted=True, vendor_ref=ref, transcript={"vendor": self.id, "ok": True})

    def suppression_check(self, entity_id: str) -> bool:
        return entity_id in self._suppressed

    def export_all(self, since: str | None) -> Iterator[dict]:
        for it in self._items:
            if since is None or it["ts"] >= since:
                yield {"kind": "record", "vendor": self.id, "id": it["key"], "value": it["amount"],
                       "observed_at": it["ts"]}
        for c in self._commands:
            yield {"kind": "command", "vendor": self.id, **c}
