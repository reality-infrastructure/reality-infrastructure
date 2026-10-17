"""Persistence: one Store interface, SQLite (stdlib) and Postgres (psycopg) backends,
plus the Ledger, an RI Merkle evidence log persisted through the store.

Every event row and every agent_runs row is bound to a ledger entry.  The row
carries ``ledger_index`` and ``leaf_hash``; the ledger entry carries the row's
identifying fields and a SHA-256 of its JSON body (payload or output).  The
citation resolver re-derives that hash from the stored row and checks the
inclusion proof, so a row that was altered after the fact cannot be cited.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from ri_core.log import EvidenceLog, leaf_hash, verify_inclusion
from ri_core.serialization import decode, encode

from engine.config import ENGINE_ROOT, EngineConfig, load_config
from engine.errors import CitationError, StoreError
from engine.hashing import sha256_json
from engine.runtime import Clock, IdGen, RandomIdGen, SystemClock

MIGRATIONS_DIR = ENGINE_ROOT / "migrations"
DEFAULT_SQLITE = ENGINE_ROOT / ".harness" / "engine.sqlite3"

RUN_JSON_COLUMNS = ("input", "iterations", "output", "judgement", "failure_reasons")
RUN_COLUMNS = (
    "run_id", "pack", "agent", "role", "manifest_hash", "agent_version", "provider",
    "model", "input_hash", "input", "iterations", "output", "status", "cost_usd",
    "latency_ms", "items_evaluated", "parent_run_id", "judgement", "judgement_hash",
    "access_denied", "failure_reasons", "ledger_index", "leaf_hash", "human_verdict",
    "verdict_reason", "verdict_at", "verdict_source", "verdict_ref", "created_at",
)
EVENT_COLUMNS = (
    "event_id", "entity_type", "entity_id", "event_type", "payload", "source",
    "source_ref", "observed_at", "recorded_at", "ledger_index", "leaf_hash",
)


def _migration_files(dialect: str) -> list[Path]:
    return sorted((MIGRATIONS_DIR / dialect).glob("*.sql"))


# ---------------------------------------------------------------------------
# Store interface
# ---------------------------------------------------------------------------

class Store:
    """Backend-neutral persistence.  Subclasses implement the ``_``-methods."""

    dialect: str

    # transactions ------------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[None]:
        raise NotImplementedError

    # ledger ---------------------------------------------------------------------
    def ledger_entries(self) -> Iterator[tuple[int, bytes, bytes]]:
        raise NotImplementedError

    def ledger_append(self, idx: int, entry: bytes, leaf: bytes) -> None:
        raise NotImplementedError

    # runs -----------------------------------------------------------------------
    def insert_run(self, row: dict) -> None:
        raise NotImplementedError

    def get_run(self, run_id: str) -> dict | None:
        raise NotImplementedError

    def list_runs(self, *, pack: str | None = None, agent: str | None = None,
                  status: str | None = None, since: str | None = None,
                  until: str | None = None, verdicted: bool | None = None,
                  parent_run_id: str | None = None, limit: int | None = None,
                  verdict_source: str | None = None) -> list[dict]:
        raise NotImplementedError

    def set_verdict(self, run_id: str, verdict: str, reason: str, at: str,
                    source: str = "human", ref: str | None = None) -> None:
        raise NotImplementedError

    # events ----------------------------------------------------------------------
    def insert_event(self, row: dict) -> None:
        raise NotImplementedError

    def get_event(self, event_id: str) -> dict | None:
        raise NotImplementedError

    def query_events(self, *, entity_type: str | None = None, entity_id: str | None = None,
                     event_type: str | None = None, source: str | None = None,
                     since: str | None = None, until: str | None = None,
                     limit: int = 50, ascending: bool = False) -> list[dict]:
        raise NotImplementedError

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

class SqliteStore(Store):
    dialect = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL") if self._path != ":memory:" else None
        self._depth = 0
        self.migrate()

    def migrate(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        applied = {r[0] for r in self._conn.execute("SELECT version FROM schema_migrations")}
        for path in _migration_files("sqlite"):
            if path.name in applied:
                continue
            # executescript manages its own transaction boundary (it commits any
            # pending transaction first), so the migration row follows it.
            self._conn.executescript("BEGIN;\n" + path.read_text(encoding="utf-8") + "\nCOMMIT;")
            self._conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                (path.name,))

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._depth == 0:
            self._conn.execute("BEGIN")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._conn.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self._conn.execute("COMMIT")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            return self._conn.execute(sql, params)
        except sqlite3.IntegrityError as e:
            raise StoreError(str(e)) from e

    # ledger
    def ledger_entries(self) -> Iterator[tuple[int, bytes, bytes]]:
        for r in self._conn.execute("SELECT idx, entry, leaf_hash FROM ledger ORDER BY idx"):
            yield int(r["idx"]), bytes(r["entry"]), bytes(r["leaf_hash"])

    def ledger_append(self, idx: int, entry: bytes, leaf: bytes) -> None:
        self.execute("INSERT INTO ledger (idx, entry, leaf_hash) VALUES (?, ?, ?)", (idx, entry, leaf))

    # runs
    def insert_run(self, row: dict) -> None:
        values = []
        for col in RUN_COLUMNS:
            v = row.get(col)
            if col in RUN_JSON_COLUMNS:
                v = None if v is None and col == "output" else json.dumps(v, sort_keys=True, allow_nan=False)
            elif col == "cost_usd":
                v = str(v)
            elif col == "access_denied":
                v = 1 if v else 0
            values.append(v)
        cols = ", ".join(RUN_COLUMNS)
        marks = ", ".join("?" for _ in RUN_COLUMNS)
        self.execute(f"INSERT INTO agent_runs ({cols}) VALUES ({marks})", tuple(values))

    @staticmethod
    def _run_from_row(r: sqlite3.Row) -> dict:
        d = {k: r[k] for k in r.keys()}
        for col in RUN_JSON_COLUMNS:
            d[col] = None if d[col] is None else json.loads(d[col])
        d["cost_usd"] = Decimal(d["cost_usd"])
        d["access_denied"] = bool(d["access_denied"])
        return d

    def get_run(self, run_id: str) -> dict | None:
        r = self._conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
        return None if r is None else self._run_from_row(r)

    def list_runs(self, *, pack=None, agent=None, status=None, since=None, until=None,
                  verdicted=None, parent_run_id=None, limit=None, verdict_source=None) -> list[dict]:
        where, params = ["1=1"], []
        for col, val in (("pack", pack), ("agent", agent), ("status", status),
                         ("parent_run_id", parent_run_id), ("verdict_source", verdict_source)):
            if val is not None:
                where.append(f"{col} = ?")
                params.append(val)
        if since is not None:
            where.append("created_at >= ?"); params.append(since)
        if until is not None:
            where.append("created_at < ?"); params.append(until)
        if verdicted is True:
            where.append("human_verdict IS NOT NULL")
        elif verdicted is False:
            where.append("human_verdict IS NULL")
        sql = f"SELECT * FROM agent_runs WHERE {' AND '.join(where)} ORDER BY created_at, run_id"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [self._run_from_row(r) for r in self._conn.execute(sql, tuple(params))]

    def set_verdict(self, run_id: str, verdict: str, reason: str, at: str,
                    source: str = "human", ref: str | None = None) -> None:
        cur = self.execute(
            "UPDATE agent_runs SET human_verdict = ?, verdict_reason = ?, verdict_at = ?, "
            "verdict_source = ?, verdict_ref = ? WHERE run_id = ?",
            (verdict, reason, at, source, ref, run_id))
        if cur.rowcount != 1:
            raise StoreError(f"no run {run_id!r}")

    # events
    def insert_event(self, row: dict) -> None:
        values = [json.dumps(row[c], sort_keys=True, allow_nan=False) if c == "payload" else row.get(c)
                  for c in EVENT_COLUMNS]
        cols = ", ".join(EVENT_COLUMNS)
        marks = ", ".join("?" for _ in EVENT_COLUMNS)
        self.execute(f"INSERT INTO events ({cols}) VALUES ({marks})", tuple(values))

    @staticmethod
    def _event_from_row(r: sqlite3.Row) -> dict:
        d = {k: r[k] for k in r.keys()}
        d["payload"] = json.loads(d["payload"])
        return d

    def get_event(self, event_id: str) -> dict | None:
        r = self._conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return None if r is None else self._event_from_row(r)

    def query_events(self, *, entity_type=None, entity_id=None, event_type=None, source=None,
                     since=None, until=None, limit=50, ascending=False) -> list[dict]:
        where, params = ["1=1"], []
        for col, val in (("entity_type", entity_type), ("entity_id", entity_id),
                         ("event_type", event_type), ("source", source)):
            if val is not None:
                where.append(f"{col} = ?")
                params.append(val)
        if since is not None:
            where.append("observed_at >= ?"); params.append(since)
        if until is not None:
            where.append("observed_at < ?"); params.append(until)
        order = "ASC" if ascending else "DESC"
        sql = (f"SELECT * FROM events WHERE {' AND '.join(where)} "
               f"ORDER BY observed_at {order}, ledger_index {order} LIMIT {int(limit)}")
        return [self._event_from_row(r) for r in self._conn.execute(sql, tuple(params))]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

class PostgresStore(Store):
    dialect = "postgres"

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as e:  # pragma: no cover - exercised only with psycopg installed
            raise StoreError("psycopg is required for a Postgres DATABASE_URL") from e
        self._Jsonb = Jsonb
        self._conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        self._depth = 0
        self.migrate()

    def migrate(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                        "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            cur.execute("SELECT version FROM schema_migrations")
            applied = {r["version"] for r in cur.fetchall()}
        for path in _migration_files("postgres"):
            if path.name in applied:
                continue
            with self.transaction(), self._conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._depth == 0:
            self._conn.autocommit = False
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._conn.rollback()
                self._conn.autocommit = True
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self._conn.commit()
                self._conn.autocommit = True

    def _exec(self, sql: str, params: tuple = ()):
        import psycopg
        try:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur
        except psycopg.errors.IntegrityError as e:
            raise StoreError(str(e)) from e

    def ledger_entries(self) -> Iterator[tuple[int, bytes, bytes]]:
        cur = self._exec("SELECT idx, entry, leaf_hash FROM ledger ORDER BY idx")
        for r in cur:
            yield int(r["idx"]), bytes(r["entry"]), bytes(r["leaf_hash"])

    def ledger_append(self, idx: int, entry: bytes, leaf: bytes) -> None:
        self._exec("INSERT INTO ledger (idx, entry, leaf_hash) VALUES (%s, %s, %s)", (idx, entry, leaf))

    def insert_run(self, row: dict) -> None:
        values = []
        for col in RUN_COLUMNS:
            v = row.get(col)
            if col in RUN_JSON_COLUMNS and v is not None:
                v = self._Jsonb(v)
            elif col == "cost_usd":
                v = Decimal(str(v))
            values.append(v)
        cols = ", ".join(RUN_COLUMNS)
        marks = ", ".join("%s" for _ in RUN_COLUMNS)
        self._exec(f"INSERT INTO agent_runs ({cols}) VALUES ({marks})", tuple(values))

    @staticmethod
    def _norm_run(d: dict) -> dict:
        d = dict(d)
        for col in ("run_id", "parent_run_id", "verdict_ref"):
            if d.get(col) is not None:
                d[col] = str(d[col])
        for col in ("verdict_at", "created_at"):
            if d.get(col) is not None:
                d[col] = d[col].isoformat(timespec="microseconds")
        d["cost_usd"] = Decimal(d["cost_usd"])
        return d

    def get_run(self, run_id: str) -> dict | None:
        r = self._exec("SELECT * FROM agent_runs WHERE run_id = %s", (run_id,)).fetchone()
        return None if r is None else self._norm_run(r)

    def list_runs(self, *, pack=None, agent=None, status=None, since=None, until=None,
                  verdicted=None, parent_run_id=None, limit=None, verdict_source=None) -> list[dict]:
        where, params = ["TRUE"], []
        for col, val in (("pack", pack), ("agent", agent), ("status", status),
                         ("parent_run_id", parent_run_id), ("verdict_source", verdict_source)):
            if val is not None:
                where.append(f"{col} = %s"); params.append(val)
        if since is not None:
            where.append("created_at >= %s"); params.append(since)
        if until is not None:
            where.append("created_at < %s"); params.append(until)
        if verdicted is True:
            where.append("human_verdict IS NOT NULL")
        elif verdicted is False:
            where.append("human_verdict IS NULL")
        sql = f"SELECT * FROM agent_runs WHERE {' AND '.join(where)} ORDER BY created_at, run_id"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [self._norm_run(r) for r in self._exec(sql, tuple(params)).fetchall()]

    def set_verdict(self, run_id: str, verdict: str, reason: str, at: str,
                    source: str = "human", ref: str | None = None) -> None:
        cur = self._exec(
            "UPDATE agent_runs SET human_verdict = %s, verdict_reason = %s, verdict_at = %s, "
            "verdict_source = %s, verdict_ref = %s WHERE run_id = %s",
            (verdict, reason, at, source, ref, run_id))
        if cur.rowcount != 1:
            raise StoreError(f"no run {run_id!r}")

    def insert_event(self, row: dict) -> None:
        values = [self._Jsonb(row[c]) if c == "payload" else row.get(c) for c in EVENT_COLUMNS]
        cols = ", ".join(EVENT_COLUMNS)
        marks = ", ".join("%s" for _ in EVENT_COLUMNS)
        self._exec(f"INSERT INTO events ({cols}) VALUES ({marks})", tuple(values))

    @staticmethod
    def _norm_event(d: dict) -> dict:
        d = dict(d)
        d["event_id"] = str(d["event_id"])
        for col in ("observed_at", "recorded_at"):
            d[col] = d[col].isoformat(timespec="microseconds")
        return d

    def get_event(self, event_id: str) -> dict | None:
        r = self._exec("SELECT * FROM events WHERE event_id = %s", (event_id,)).fetchone()
        return None if r is None else self._norm_event(r)

    def query_events(self, *, entity_type=None, entity_id=None, event_type=None, source=None,
                     since=None, until=None, limit=50, ascending=False) -> list[dict]:
        where, params = ["TRUE"], []
        for col, val in (("entity_type", entity_type), ("entity_id", entity_id),
                         ("event_type", event_type), ("source", source)):
            if val is not None:
                where.append(f"{col} = %s"); params.append(val)
        if since is not None:
            where.append("observed_at >= %s"); params.append(since)
        if until is not None:
            where.append("observed_at < %s"); params.append(until)
        order = "ASC" if ascending else "DESC"
        sql = (f"SELECT * FROM events WHERE {' AND '.join(where)} "
               f"ORDER BY observed_at {order}, ledger_index {order} LIMIT {int(limit)}")
        return [self._norm_event(r) for r in self._exec(sql, tuple(params)).fetchall()]

    def close(self) -> None:
        self._conn.close()


def open_store(dsn: str | None = None) -> Store:
    """Resolve a DSN: explicit arg, then DATABASE_URL, then a local SQLite file."""
    dsn = dsn or os.environ.get("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE.as_posix()}"
    if dsn.startswith("sqlite://"):
        rest = dsn[len("sqlite://"):]
        if rest in (":memory:", "/:memory:"):
            return SqliteStore(":memory:")
        return SqliteStore(rest.lstrip("/") if os.name == "nt" and rest.startswith("/") and rest[2:3] == ":" else rest)
    if dsn.startswith(("postgres://", "postgresql://")):
        return PostgresStore(dsn)
    raise StoreError(f"unsupported DATABASE_URL scheme in {dsn!r}")


# ---------------------------------------------------------------------------
# Ledger — the RI evidence log, persisted
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerReceipt:
    index: int
    leaf_hash: str
    root: str


class Ledger:
    """RFC 9162-style Merkle log (ri_core.log.EvidenceLog) with store persistence."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._log = EvidenceLog()
        self._reload()

    def _reload(self) -> None:
        self._log = EvidenceLog()
        for idx, entry, leaf in self._store.ledger_entries():
            if idx != len(self._log):
                raise StoreError(f"ledger gap at index {idx}")
            got = self._log.append(decode(entry))
            if self._log.entry(got) != entry or leaf_hash(entry) != leaf:
                raise StoreError(f"ledger entry {idx} does not re-encode to its stored bytes")

    def __len__(self) -> int:
        return len(self._log)

    def root(self) -> str:
        return self._log.root().hex()

    def entry(self, index: int):
        return decode(self._log.entry(index))

    def append(self, obj: dict) -> LedgerReceipt:
        """Append inside the caller's transaction.  In-memory state follows the store."""
        entry = encode(obj)
        idx = len(self._log)
        try:
            self._store.ledger_append(idx, entry, leaf_hash(entry))
        except Exception:
            self._reload()
            raise
        self._log.append(obj)
        return LedgerReceipt(index=idx, leaf_hash=leaf_hash(entry).hex(), root=self._log.root().hex())

    def verify_index(self, index: int, expected_leaf_hex: str) -> None:
        if index < 0 or index >= len(self._log):
            raise CitationError(f"ledger index {index} out of range")
        proof = self._log.inclusion_proof(index)
        if proof.leaf_hash.hex() != expected_leaf_hex:
            raise CitationError(f"ledger leaf mismatch at index {index}")
        if not verify_inclusion(proof.leaf_hash, proof.index, proof.tree_size, proof.hashes, proof.root_hash):
            raise CitationError(f"inclusion proof failed at index {index}")

    def verify_row(self, row: dict) -> None:
        """A stored event or run row must match its ledger entry, byte for byte."""
        entry = self.entry(int(row["ledger_index"]))
        kind = entry.get("kind")
        if kind == "event":
            expected = event_ledger_entry(row)
        elif kind == "agent_run":
            expected = run_ledger_entry(row)
        else:
            raise CitationError(f"ledger entry {row['ledger_index']} has unknown kind {kind!r}")
        if entry != expected:
            raise CitationError(
                f"row {row.get('event_id') or row.get('run_id')} does not match its ledger entry")
        self.verify_index(int(row["ledger_index"]), row["leaf_hash"])


def event_ledger_entry(row: dict) -> dict:
    """Ledger binding for an event row (payload bound by hash, so floats are allowed in payloads)."""
    return {
        "kind": "event",
        "event_id": row["event_id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "event_type": row["event_type"],
        "source": row["source"],
        "source_ref": row.get("source_ref"),
        "observed_at": row["observed_at"],
        "payload_sha256": sha256_json(row["payload"]),
    }


def run_ledger_entry(row: dict) -> dict:
    return {
        "kind": "agent_run",
        "run_id": row["run_id"],
        "pack": row["pack"],
        "agent": row["agent"],
        "role": row["role"],
        "manifest_hash": row["manifest_hash"],
        "agent_version": row["agent_version"],
        "model": f"{row['provider']}/{row['model']}",
        "input_hash": row["input_hash"],
        "status": row["status"],
        "output_sha256": None if row.get("output") is None else sha256_json(row["output"]),
        "judgement_root": row["judgement"]["root"],
        "parent_run_id": row.get("parent_run_id"),
    }


# ---------------------------------------------------------------------------
# Engine context
# ---------------------------------------------------------------------------

@dataclass
class Engine:
    """Everything a run needs from the substrate.  One per process (or per test)."""
    store: Store
    ledger: Ledger
    clock: Clock
    ids: IdGen
    config: EngineConfig

    @classmethod
    def open(cls, dsn: str | None = None, *, clock: Clock | None = None,
             ids: IdGen | None = None, config: EngineConfig | None = None) -> "Engine":
        store = open_store(dsn)
        return cls(store=store, ledger=Ledger(store), clock=clock or SystemClock(),
                   ids=ids or RandomIdGen(), config=config or load_config())

    def close(self) -> None:
        self.store.close()
