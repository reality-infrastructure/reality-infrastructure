"""Tests for ri_core.clock — Lamport logical clock."""

from __future__ import annotations

import pytest

from ri_core.clock import LamportClock


class TestLamportClock:
    def test_initial_time_zero(self):
        assert LamportClock().time == 0

    def test_custom_initial(self):
        assert LamportClock(initial=10).time == 10

    def test_tick_increments(self):
        c = LamportClock()
        assert c.tick() == 1
        assert c.tick() == 2
        assert c.tick() == 3
        assert c.time == 3

    def test_observe_takes_max_plus_one(self):
        c = LamportClock()
        c.tick()  # time = 1
        assert c.observe(5) == 6  # max(1, 5) + 1

    def test_observe_local_higher(self):
        c = LamportClock(initial=10)
        assert c.observe(3) == 11  # max(10, 3) + 1

    def test_observe_equal(self):
        c = LamportClock(initial=5)
        assert c.observe(5) == 6  # max(5, 5) + 1

    def test_monotonic_over_many_ticks(self):
        c = LamportClock()
        prev = c.time
        for _ in range(100):
            t = c.tick()
            assert t > prev
            prev = t

    def test_reject_float_initial(self):
        with pytest.raises(TypeError):
            LamportClock(initial=1.0)

    def test_reject_bool_initial(self):
        with pytest.raises(TypeError):
            LamportClock(initial=True)

    def test_reject_negative_initial(self):
        with pytest.raises(ValueError):
            LamportClock(initial=-1)

    def test_reject_float_observe(self):
        with pytest.raises(TypeError):
            LamportClock().observe(1.0)

    def test_reject_bool_observe(self):
        with pytest.raises(TypeError):
            LamportClock().observe(True)


class TestThreeProcessMessageDiagram:
    """Three-process message diagram with known correct happened-before.

    Process A: a1, a2, send(a2) → B, a3
    Process B: b1, recv(a2), b2, send(b2) → C
    Process C: c1, c2, recv(b2), c3

    Causal chain: a1 → a2 → recv_B → b2 → recv_C → c3
    """

    def test_message_ordering(self):
        a = LamportClock()
        b = LamportClock()
        c = LamportClock()

        # Process A
        a1 = a.tick()         # 1
        a2 = a.tick()         # 2
        msg_a_to_b = a2
        a3 = a.tick()         # 3

        # Process B
        b1 = b.tick()         # 1
        b_recv = b.observe(msg_a_to_b)  # max(1,2)+1 = 3
        b2 = b.tick()         # 4
        msg_b_to_c = b2

        # Process C
        c1 = c.tick()         # 1
        c2 = c.tick()         # 2
        c_recv = c.observe(msg_b_to_c)  # max(2,4)+1 = 5
        c3 = c.tick()         # 6

        # Happened-before: if A → B then time(A) < time(B)
        assert a1 < a2 < a3                   # same process
        assert a2 < b_recv < b2               # cross-process via message
        assert b2 < c_recv < c3               # cross-process via message
        assert a1 < c3                        # transitive
        assert b1 < b_recv                    # same process
        assert c1 < c2 < c_recv              # same process

        # Verify exact values
        assert (a1, a2, a3) == (1, 2, 3)
        assert (b1, b_recv, b2) == (1, 3, 4)
        assert (c1, c2, c_recv, c3) == (1, 2, 5, 6)
