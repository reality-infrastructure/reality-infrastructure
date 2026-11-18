"""Mock vendor that rejects every command: the fixture a staged binding trial must refuse (engine.vendors)."""

from __future__ import annotations

from engine.adapters.base import Command, CommandResult

from _reference.adapters.mock_b import MockVendorB


class MockFlaky(MockVendorB):
    id = "mock_flaky"

    def command(self, cmd: Command) -> CommandResult:
        return CommandResult(accepted=False, reason="vendor timeout")
