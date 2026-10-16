"""Exception hierarchy for the engine.  One base, one class per failure family."""

from __future__ import annotations


class EngineError(Exception):
    """Base for every engine-raised error."""


class ManifestError(EngineError):
    """Manifest, pack, or onboarding file failed to load or validate."""


class AccessDenied(EngineError):
    """A tool call targeted something outside the agent's access.yaml.

    Carries the target so the trace can record exactly what was refused.
    """

    def __init__(self, kind: str, target: str, mode: str, agent: str) -> None:
        self.kind = kind
        self.target = target
        self.mode = mode
        self.agent = agent
        super().__init__(
            f"access denied: agent {agent!r} may not {mode} {kind} {target!r}")


class ToolError(EngineError):
    """A tool call failed validation or execution."""


class ProviderError(EngineError):
    """A model provider call failed."""


class EventError(EngineError):
    """An event was rejected: undeclared type, payload schema, or ledger failure."""


class CitationError(EngineError):
    """A citation reference could not be resolved."""


class StoreError(EngineError):
    """Persistence failure or an attempted mutation of append-only data."""


class GateError(EngineError):
    """A gated operation (export, downgrade) was refused because its gate is unmet."""


class EvalError(EngineError):
    """Golden set malformed or eval could not run."""
