"""Clock and id generation, injectable so the engine is deterministic under test.

ri_core forbids wall-clock reads inside the belief engine; the harness around
it needs real time for observed_at / recorded_at.  Both come through here so a
test can pin them.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Starts at *start* and advances by *step* on every read, so ordering holds."""

    def __init__(self, start: datetime, step: timedelta = timedelta(milliseconds=1)) -> None:
        if start.tzinfo is None:
            raise ValueError("FixedClock start must be timezone-aware")
        self._t = start
        self._step = step

    def now(self) -> datetime:
        t = self._t
        self._t = t + self._step
        return t


class IdGen(Protocol):
    def new(self) -> str: ...


class RandomIdGen:
    def new(self) -> str:
        return str(uuid.uuid4())


class SeededIdGen:
    """Deterministic UUIDs derived from a seed and a counter (tests, replays)."""

    def __init__(self, seed: str) -> None:
        self._seed = seed
        self._n = 0

    def new(self) -> str:
        self._n += 1
        digest = hashlib.sha256(f"{self._seed}:{self._n}".encode("utf-8")).digest()
        return str(uuid.UUID(bytes=digest[:16], version=4))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
