"""Tests for ri_core.log — append-only Merkle evidence log.

Covers: inclusion proofs (exhaustive 1..17), consistency proofs (exhaustive
pairs), tamper detection, golden root hashes, cross-process determinism,
hypothesis property tests, and amendment A2 index-confusion negative test.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ri_core.log import (
    ConsistencyProof,
    EvidenceLog,
    InclusionProof,
    _EMPTY_ROOT,
    leaf_hash,
    node_hash,
    verify_consistency,
    verify_inclusion,
)

GOLDEN_DIR = Path(__file__).parent / "golden" / "log"


# ── Helpers ─────────────────────────────────────────────────────────

def _build_log(n: int) -> EvidenceLog:
    """Build a log with n entries: {"i": 0}, {"i": 1}, ..."""
    log = EvidenceLog()
    for i in range(n):
        log.append({"i": i})
    return log


# ── Golden fixtures ─────────────────────────────────────────────────

GOLDEN_FIXTURES = {
    "log_1entry": [{"id": "obs-001", "v": 1}],
    "log_4entries": [
        {"id": "obs-001", "v": 1},
        {"id": "obs-002", "v": 2},
        {"id": "obs-003", "v": 3},
        {"id": "obs-004", "v": 4},
    ],
    "log_7entries": [
        {"id": "obs-001", "v": 1},
        {"id": "obs-002", "v": 2},
        {"id": "obs-003", "v": 3},
        {"id": "obs-004", "v": 4},
        {"id": "obs-005", "v": 5},
        {"id": "obs-006", "v": 6},
        {"id": "obs-007", "v": 7},
    ],
}


def _generate_golden_files():
    """Generate golden .bin files from GOLDEN_FIXTURES.  Run once, freeze."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, entries in GOLDEN_FIXTURES.items():
        log = EvidenceLog()
        for entry in entries:
            log.append(entry)
        path = GOLDEN_DIR / f"{name}.bin"
        path.write_bytes(log.root())
        print(f"  wrote {path} ({log.root().hex()})")


# ── Basic tests ─────────────────────────────────────────────────────

class TestBasics:
    def test_empty_root(self):
        log = EvidenceLog()
        assert log.root() == _EMPTY_ROOT
        assert log.root() == hashlib.sha256(b'').digest()

    def test_len(self):
        log = EvidenceLog()
        assert len(log) == 0
        log.append("hello")
        assert len(log) == 1
        log.append("world")
        assert len(log) == 2

    def test_append_returns_index(self):
        log = EvidenceLog()
        assert log.append("a") == 0
        assert log.append("b") == 1
        assert log.append("c") == 2

    def test_entry_retrieval(self):
        from ri_core.serialization import encode
        log = EvidenceLog()
        log.append({"x": 1})
        assert log.entry(0) == encode({"x": 1})

    def test_entry_index_error(self):
        log = EvidenceLog()
        with pytest.raises(IndexError):
            log.entry(0)
        log.append("a")
        with pytest.raises(IndexError):
            log.entry(1)
        with pytest.raises(IndexError):
            log.entry(-1)

    def test_single_entry_root(self):
        from ri_core.serialization import encode
        log = EvidenceLog()
        log.append("hello")
        expected = leaf_hash(encode("hello"))
        assert log.root() == expected

    def test_root_at_size(self):
        log = _build_log(5)
        r3 = log.root(3)
        r5 = log.root(5)
        assert r3 != r5
        # root(3) should match a fresh 3-entry log
        log3 = _build_log(3)
        assert r3 == log3.root()

    def test_domain_separation(self):
        """Leaf hash and node hash use different prefixes."""
        data = b'test'
        lh = leaf_hash(data)
        nh = node_hash(data, data)
        assert lh != nh

    def test_no_mutate_api(self):
        """EvidenceLog has no delete/mutate methods."""
        log = EvidenceLog()
        assert not hasattr(log, '__setitem__')
        assert not hasattr(log, '__delitem__')
        assert not hasattr(log, 'pop')
        assert not hasattr(log, 'remove')
        assert not hasattr(log, 'clear')


# ── Exhaustive inclusion proofs (1..17) ─────────────────────────────

class TestInclusionExhaustive:
    """Inclusion proofs verify for EVERY index at every tree size 1..17."""

    MAX_SIZE = 17

    @pytest.fixture(scope="class")
    def log17(self):
        return _build_log(self.MAX_SIZE)

    def test_all_inclusion_proofs(self, log17):
        for size in range(1, self.MAX_SIZE + 1):
            for idx in range(size):
                proof = log17.inclusion_proof(idx, size)
                assert verify_inclusion(
                    proof.leaf_hash, proof.index, proof.tree_size,
                    proof.hashes, proof.root_hash,
                ), f"Inclusion failed: index={idx}, size={size}"


# ── Exhaustive consistency proofs (old ≤ new ≤ 17) ──────────────────

class TestConsistencyExhaustive:
    """Consistency proofs verify for EVERY (old, new) pair with old ≤ new ≤ 17."""

    MAX_SIZE = 17

    @pytest.fixture(scope="class")
    def log17(self):
        return _build_log(self.MAX_SIZE)

    def test_all_consistency_proofs(self, log17):
        for old in range(0, self.MAX_SIZE + 1):
            for new in range(old, self.MAX_SIZE + 1):
                proof = log17.consistency_proof(old, new)
                assert verify_consistency(
                    proof.old_size, proof.new_size,
                    proof.old_root, proof.new_root,
                    proof.hashes,
                ), f"Consistency failed: old={old}, new={new}"


# ── Tamper test ─────────────────────────────────────────────────────

class TestTamper:
    """Flipping any single bit of any leaf's bytes must break inclusion."""

    def test_bit_flip_breaks_inclusion(self):
        log = _build_log(8)
        for idx in range(8):
            proof = log.inclusion_proof(idx, 8)
            entry = log.entry(idx)
            for byte_pos in range(len(entry)):
                tampered = bytearray(entry)
                tampered[byte_pos] ^= 0x80  # flip high bit
                tampered_lh = leaf_hash(bytes(tampered))
                assert not verify_inclusion(
                    tampered_lh, proof.index, proof.tree_size,
                    proof.hashes, proof.root_hash,
                ), f"Tamper not detected: idx={idx}, byte={byte_pos}"


# ── A2: Index-confusion negative test ───────────────────────────────

class TestIndexConfusion:
    """A valid proof for index i must FAIL for index j != i (same leaf_hash,
    same hashes, wrong claimed index)."""

    def test_wrong_index_fails(self):
        log = _build_log(8)
        for idx in range(8):
            proof = log.inclusion_proof(idx, 8)
            for wrong_idx in range(8):
                if wrong_idx == idx:
                    continue
                assert not verify_inclusion(
                    proof.leaf_hash, wrong_idx, proof.tree_size,
                    proof.hashes, proof.root_hash,
                ), (
                    f"Index confusion: proof for {idx} accepted at {wrong_idx}"
                )


# ── Golden root-hash tests ──────────────────────────────────────────

class TestGolden:
    @pytest.mark.parametrize("name", sorted(GOLDEN_FIXTURES))
    def test_root_matches_golden(self, name):
        golden_path = GOLDEN_DIR / f"{name}.bin"
        expected = golden_path.read_bytes()
        log = EvidenceLog()
        for entry in GOLDEN_FIXTURES[name]:
            log.append(entry)
        assert log.root() == expected, f"Golden root mismatch for {name}"


# ── Cross-process determinism ───────────────────────────────────────

class TestCrossProcessDeterminism:
    def test_same_root_different_hashseed(self):
        root = str(Path(__file__).resolve().parent.parent)
        script = (
            "import sys\n"
            f"sys.path.insert(0, {root!r})\n"
            "from ri_core.log import EvidenceLog\n"
            "import base64\n"
            "log = EvidenceLog()\n"
            "for i in range(10):\n"
            "    log.append({'i': i, 'data': 'test'})\n"
            "print(base64.b64encode(log.root()).decode(), end='')\n"
        )
        results = []
        for seed in ["0", "42", "99999"]:
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env,
            )
            assert proc.returncode == 0, (
                f"Subprocess failed (seed={seed}): {proc.stderr}"
            )
            results.append(proc.stdout)
        assert results[0] == results[1] == results[2]


# ── Hypothesis property tests ───────────────────────────────────────

_safe_entry = st.fixed_dictionaries({
    'id': st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
                  min_size=1, max_size=20),
    'v': st.integers(min_value=0, max_value=10**9),
})


class TestHypothesis:
    @given(entries=st.lists(_safe_entry, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_inclusion_holds_for_all(self, entries):
        log = EvidenceLog()
        for e in entries:
            log.append(e)
        size = len(log)
        for idx in range(size):
            proof = log.inclusion_proof(idx, size)
            assert verify_inclusion(
                proof.leaf_hash, proof.index, proof.tree_size,
                proof.hashes, proof.root_hash,
            )

    @given(entries=st.lists(_safe_entry, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_consistency_holds_for_random_prefix(self, entries):
        log = EvidenceLog()
        for e in entries:
            log.append(e)
        new_size = len(log)
        # test consistency from every prefix
        for old_size in range(new_size + 1):
            proof = log.consistency_proof(old_size, new_size)
            assert verify_consistency(
                proof.old_size, proof.new_size,
                proof.old_root, proof.new_root,
                proof.hashes,
            )


# ── Runner for golden-file generation (not a test) ─────────────────

if __name__ == "__main__":
    print("Generating golden log files...")
    _generate_golden_files()
    print("Done.")
