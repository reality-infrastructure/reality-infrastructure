"""Lamport logical clock realizing axiom A2 (partial order on events).

Implements the classic Lamport clock rules (Lamport, CACM 21(7), 1978):
- Local event: increment clock
- Receive event: max(local, received) + 1

No wall-clock reads. No floats. Pure integer counter.

This module imports nothing from ri_core (bottom of the dependency DAG
alongside serialization).
"""

from __future__ import annotations


class LamportClock:
    """Lamport logical clock.

    Maintains a monotonically increasing integer counter that realizes
    the happened-before partial order.  If event A causally precedes
    event B, then A's timestamp is strictly less than B's.
    """

    __slots__ = ('_time',)

    def __init__(self, initial: int = 0) -> None:
        if isinstance(initial, bool) or not isinstance(initial, int):
            raise TypeError(
                f"initial must be int, got {type(initial).__name__}"
            )
        if initial < 0:
            raise ValueError(f"initial must be non-negative, got {initial}")
        self._time = initial

    @property
    def time(self) -> int:
        """Current logical time (read-only)."""
        return self._time

    def tick(self) -> int:
        """Local event: increment and return new time."""
        self._time += 1
        return self._time

    def observe(self, remote_time: int) -> int:
        """Receive event: set clock = max(local, remote) + 1, return new time.

        Realizes Lamport's rule: on receiving a message with timestamp T,
        set clock = max(local, T) + 1.
        """
        if isinstance(remote_time, bool) or not isinstance(remote_time, int):
            raise TypeError(
                f"remote_time must be int, got {type(remote_time).__name__}"
            )
        self._time = max(self._time, remote_time) + 1
        return self._time
