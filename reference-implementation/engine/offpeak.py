"""Tariff windows: the hours a provider bills at its off-peak rate.

A window is ``"HH:MM-HH:MM"`` (every day) or ``"Day-Day HH:MM-HH:MM"`` / ``"Day HH:MM-HH:MM"``
(those weekdays only), in UTC; ``24:00`` closes a window at midnight.  ``config/prices.yaml`` carries
them per model as ``off_peak: {windows_utc: [...], input, output, cache_read}``; the provider bills the
rate in force at the engine clock's time of the call, and ``engine.sweep --off-peak`` starts new work
only while a window is open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from engine.errors import EngineError

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_WINDOW_RE = re.compile(r"^(?:(?P<d0>[A-Z][a-z]{2})(?:-(?P<d1>[A-Z][a-z]{2}))?\s+)?"
                        r"(?P<h0>\d{2}):(?P<m0>\d{2})-(?P<h1>\d{2}):(?P<m1>\d{2})$")


@dataclass(frozen=True)
class Window:
    days: frozenset[int]          # weekday() numbers the window opens on
    start_min: int                # minutes after midnight UTC, inclusive
    end_min: int                  # exclusive; 1440 = midnight

    def contains(self, at: datetime) -> bool:
        t = at.astimezone(timezone.utc)
        minute = t.hour * 60 + t.minute
        return t.weekday() in self.days and self.start_min <= minute < self.end_min


def parse_window(text: str) -> Window:
    m = _WINDOW_RE.match(str(text).strip())
    if not m:
        raise EngineError(f"off-peak window {text!r} must look like 'HH:MM-HH:MM' or 'Mon-Fri HH:MM-HH:MM'")
    d0, d1 = m.group("d0"), m.group("d1")
    for d in (d0, d1):
        if d is not None and d not in DAYS:
            raise EngineError(f"off-peak window {text!r}: unknown day {d!r} (one of {', '.join(DAYS)})")
    if d0 is None:
        days = frozenset(range(7))
    else:
        a, b = DAYS.index(d0), DAYS.index(d1 or d0)
        days = frozenset(range(a, b + 1)) if a <= b else frozenset(list(range(a, 7)) + list(range(0, b + 1)))
    start = int(m.group("h0")) * 60 + int(m.group("m0"))
    end = int(m.group("h1")) * 60 + int(m.group("m1"))
    if not (0 <= start < end <= 1440) or int(m.group("m0")) > 59 or int(m.group("m1")) > 59:
        raise EngineError(f"off-peak window {text!r}: start must precede end within one day (00:00-24:00)")
    return Window(days=days, start_min=start, end_min=end)


def parse_windows(texts) -> tuple[Window, ...]:
    if not isinstance(texts, list) or not texts:
        raise EngineError("off_peak.windows_utc must be a non-empty list")
    return tuple(parse_window(t) for t in texts)


def in_windows(windows: tuple[Window, ...], at: datetime) -> bool:
    return any(w.contains(at) for w in windows)


def next_open(windows: tuple[Window, ...], at: datetime) -> datetime:
    """The first minute at or after ``at`` inside a window (a week ahead at most)."""
    t = at.astimezone(timezone.utc).replace(second=0, microsecond=0)
    if t < at:
        t += timedelta(minutes=1)
    for _ in range(7 * 24 * 60):
        if in_windows(windows, t):
            return t
        t += timedelta(minutes=1)
    raise EngineError("no off-peak window opens within a week")
