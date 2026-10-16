"""Deny-by-default access runtime.

An agent's access.yaml is compiled into an AccessPolicy.  Every tool call is
checked here, in code, before anything executes; prompts never carry access.
Unlisted target -> AccessDenied -> the run fails closed with status
``access_denied``.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from engine.errors import AccessDenied, ManifestError

ENGINE_TABLES = frozenset({"agent_runs", "events", "ledger"})
_MODES = frozenset({"read", "write"})


@dataclass(frozen=True)
class Target:
    """What a tool call touches.  kind: table | file | network | tool | agent."""
    kind: str
    name: str
    mode: str = "read"


@dataclass(frozen=True)
class AccessPolicy:
    agent: str
    pack_root: Path
    tables_read: frozenset[str] = field(default_factory=frozenset)
    tables_write: frozenset[str] = field(default_factory=frozenset)
    files_read: tuple[str, ...] = ()
    files_write: tuple[str, ...] = ()
    network: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    agents: frozenset[str] = field(default_factory=frozenset)

    # -- construction -------------------------------------------------------

    @classmethod
    def from_doc(cls, doc: dict, *, agent: str, pack_root: Path,
                 tools: frozenset[str], agents: frozenset[str]) -> AccessPolicy:
        tables = doc.get("tables") or {}
        files = doc.get("files") or {}
        write_tables = frozenset(tables.get("write") or [])
        illegal = write_tables & (ENGINE_TABLES - {"events"})
        if illegal:
            raise ManifestError(
                f"access.yaml for {agent!r} grants write on engine table(s) "
                f"{sorted(illegal)}; engine tables are written only through engine APIs")
        return cls(
            agent=agent,
            pack_root=pack_root.resolve(),
            tables_read=frozenset(tables.get("read") or []),
            tables_write=write_tables,
            files_read=tuple(files.get("read") or []),
            files_write=tuple(files.get("write") or []),
            network=frozenset(doc.get("network") or []),
            tools=tools,
            agents=agents,
        )

    # -- checks ----------------------------------------------------------------

    def _deny(self, kind: str, name: str, mode: str) -> AccessDenied:
        return AccessDenied(kind, name, mode, self.agent)

    def check_table(self, name: str, mode: str) -> None:
        if mode not in _MODES:
            raise ValueError(f"bad mode {mode!r}")
        allowed = self.tables_write if mode == "write" else (self.tables_read | self.tables_write)
        if name not in allowed:
            raise self._deny("table", name, mode)

    def check_file(self, path: str, mode: str) -> Path:
        """Resolve *path* under the pack root and match it against the globs."""
        if mode not in _MODES:
            raise ValueError(f"bad mode {mode!r}")
        candidate = (self.pack_root / path).resolve()
        try:
            rel = candidate.relative_to(self.pack_root)
        except ValueError:
            raise self._deny("file", path, mode) from None
        rel_posix = PurePosixPath(rel).as_posix()
        globs = self.files_write if mode == "write" else (self.files_read + self.files_write)
        if not any(fnmatch.fnmatchcase(rel_posix, g) for g in globs):
            raise self._deny("file", path, mode)
        return candidate

    def check_network(self, host: str) -> None:
        if host not in self.network:
            raise self._deny("network", host, "read")

    def check_tool(self, tool_id: str) -> None:
        if tool_id not in self.tools:
            raise self._deny("tool", tool_id, "read")

    def check_agent(self, agent_ref: str) -> None:
        if agent_ref not in self.agents:
            raise self._deny("agent", agent_ref, "read")

    def check(self, target: Target) -> None:
        if target.kind == "table":
            self.check_table(target.name, target.mode)
        elif target.kind == "file":
            self.check_file(target.name, target.mode)
        elif target.kind == "network":
            self.check_network(target.name)
        elif target.kind == "tool":
            self.check_tool(target.name)
        elif target.kind == "agent":
            self.check_agent(target.name)
        else:
            raise self._deny(target.kind, target.name, target.mode)
