"""Citation resolver.

Engine-wide citation format: ``{"ref": "<kind>:<table_or_path>:<id>", "field": "..."}``.
Kinds: ``event`` (event log row, inclusion-proof verified against the ledger),
``table`` (pack table row), ``file`` (granted file, optional line), ``run``
(certified output of a prior agent run).  A ref that does not resolve is a
CitationError; the guardrail turns that into a failed run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from engine.errors import CitationError
from engine.schema import get_path

CITATION_KEY = "citations"


@dataclass(frozen=True)
class Citation:
    ref: str
    field: str | None
    kind: str
    locator: str
    id: str


@dataclass(frozen=True)
class Resolved:
    citation: Citation
    source: Any           # the row / output / line that was cited

    def value(self):
        """The cited value; KeyError-free: raises CitationError when the field is absent."""
        c = self.citation
        if c.field is None:
            return self.source
        try:
            if c.kind == "event":
                payload = self.source["payload"]
                try:
                    return get_path(payload, c.field)
                except (KeyError, IndexError, ValueError):
                    return get_path(self.source, c.field)
            if c.kind == "run":
                return get_path(self.source["output"], c.field)
            if c.kind == "table":
                return get_path(self.source, c.field)
            if c.kind == "file":
                return self.source
        except (KeyError, IndexError, ValueError):
            pass
        raise CitationError(f"{c.ref}: field {c.field!r} not present in cited source")


def parse_ref(ref: str, kinds: frozenset[str]) -> Citation:
    if not isinstance(ref, str):
        raise CitationError(f"citation ref must be a string, got {type(ref).__name__}")
    parts = ref.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise CitationError(f"malformed citation ref {ref!r}; expected <kind>:<locator>:<id>")
    kind, locator, ident = parts
    if kind not in kinds:
        raise CitationError(f"unknown citation kind {kind!r} in {ref!r}")
    return Citation(ref=ref, field=None, kind=kind, locator=locator, id=ident)


def iter_citations(output: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], dict]]:
    """Walk an output and yield (path_to_owner, citation_dict) for every citation."""
    if isinstance(output, dict):
        cites = output.get(CITATION_KEY)
        if isinstance(cites, list):
            for c in cites:
                if isinstance(c, dict):
                    yield path, c
        for k, v in output.items():
            if k != CITATION_KEY:
                yield from iter_citations(v, path + (k,))
    elif isinstance(output, list):
        for i, v in enumerate(output):
            yield from iter_citations(v, path + (str(i),))


class CitationResolver:
    """Resolves refs against the engine store, the pack's tables, and granted files."""

    def __init__(self, *, engine, pack, access, kinds: frozenset[str]) -> None:
        self._engine = engine
        self._pack = pack
        self._access = access
        self._kinds = kinds

    def parse(self, citation: dict) -> Citation:
        c = parse_ref(citation.get("ref"), self._kinds)
        field = citation.get("field")
        if field is not None and not isinstance(field, str):
            raise CitationError(f"{c.ref}: field must be a string")
        return Citation(ref=c.ref, field=field, kind=c.kind, locator=c.locator, id=c.id)

    def resolve(self, citation: dict) -> Resolved:
        c = self.parse(citation)
        if c.kind == "event":
            if c.locator != "events":
                raise CitationError(f"{c.ref}: event refs use locator 'events'")
            row = self._engine.store.get_event(c.id)
            if row is None:
                raise CitationError(f"{c.ref}: no such event")
            self._engine.ledger.verify_row(row)
            return Resolved(c, row)
        if c.kind == "run":
            if c.locator != "agent_runs":
                raise CitationError(f"{c.ref}: run refs use locator 'agent_runs'")
            row = self._engine.store.get_run(c.id)
            if row is None:
                raise CitationError(f"{c.ref}: no such run")
            if row["status"] != "succeeded" or row["output"] is None:
                raise CitationError(f"{c.ref}: cited run did not succeed; only certified outputs may be cited")
            return Resolved(c, row)
        if c.kind == "table":
            row = self._pack.table_row(c.locator, c.id)
            if row is None:
                raise CitationError(f"{c.ref}: no row {c.id!r} in table {c.locator!r}")
            return Resolved(c, row)
        if c.kind == "file":
            try:
                path = self._access.check_file(c.locator, "read")
            except Exception as e:  # AccessDenied -> citation does not resolve for this agent
                raise CitationError(f"{c.ref}: {e}") from e
            if not path.is_file():
                raise CitationError(f"{c.ref}: file not found")
            lines = path.read_text(encoding="utf-8").splitlines()
            if c.id == "*":
                return Resolved(c, "\n".join(lines))
            try:
                n = int(c.id)
                return Resolved(c, lines[n - 1])
            except (ValueError, IndexError):
                raise CitationError(f"{c.ref}: line {c.id!r} not present") from None
        raise CitationError(f"{c.ref}: unsupported kind")
