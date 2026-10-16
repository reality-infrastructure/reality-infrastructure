"""Mock vendor A: payload shape ``{"records": [{"id", "value", "observed_at"}]}``."""

from __future__ import annotations

from typing import Any, Iterator

from engine.adapters.base import Adapter, Command, CommandResult, EventDraft


class MockVendorA(Adapter):
    id = "mock_a"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._suppressed = set(config.get("suppressed") or [])
        self._records: list[dict] = []
        self._commands: list[dict] = []

    def ingest(self, vendor_payload: Any) -> list[EventDraft]:
        drafts = []
        for rec in vendor_payload["records"]:
            self._records.append(dict(rec))
            drafts.append(EventDraft(
                entity_type="record", entity_id=str(rec["id"]),
                event_type="_reference.record_observed",
                payload={"record_id": str(rec["id"]), "value": rec["value"], "vendor": self.id},
                observed_at=rec["observed_at"], vendor_record_id=f"A:{rec['id']}"))
        return drafts

    def command(self, cmd: Command) -> CommandResult:
        ref = f"A-cmd-{len(self._commands) + 1}"
        self._commands.append({"ref": ref, "entity_id": cmd.entity_id, "action": cmd.action,
                               "params": dict(cmd.params), "flags": dict(cmd.flags)})
        return CommandResult(accepted=True, vendor_ref=ref,
                             transcript={"vendor": self.id, "echo": cmd.action})

    def suppression_check(self, entity_id: str) -> bool:
        return entity_id in self._suppressed

    def export_all(self, since: str | None) -> Iterator[dict]:
        for r in self._records:
            if since is None or r["observed_at"] >= since:
                yield {"kind": "record", "vendor": self.id, **r}
        for c in self._commands:
            yield {"kind": "command", "vendor": self.id, **c}
