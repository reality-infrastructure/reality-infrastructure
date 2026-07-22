"""Conformance suite: C1–C9 per CONFORMANCE.md.

Each test cites its criterion id in the test name and docstring.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog, verify_consistency
from ri_core.project import project, submit
from ri_core.provenance import ProvenanceGraph
from ri_core.reconcile import BeliefWeights, ReconciliationError, cautious_fuse
from ri_core.replay import counterfactual, export_log, replay
from ri_core.rules import RuleStore
from ri_core.serialization import decode as _dec
from ri_core.serialization import encode as _enc


# -- Helpers -----------------------------------------------------------------

def _auth(*names, links=None):
    a = LocalAuthority(anchor_id="conf", seed=b"conf-seed")
    for n in names:
        a.issue_identity(n)
    if links:
        for x, y in links:
            a.link_identities(
                Identity(identity_id=x, anchor_id="conf", name=x),
                Identity(identity_id=y, anchor_id="conf", name=y))
    return a


def _obs(oid, src, prop, frame, mass, lt, auth):
    u = {"kind": "observation", "id": oid, "source_id": src,
         "proposition": prop, "payload": {"frame": frame, "mass": mass},
         "ltime": lt}
    ub = _enc(u)
    sig = auth.sign(
        Identity(identity_id=src, anchor_id=auth.anchor_id, name=src), ub)
    return {**u, "sig": sig}


# -- C1: Byte-identical replay -----------------------------------------------

class TestC1ByteIdenticalReplay:
    """C1: replay(export(log)) ≡ project(log) byte-for-byte.

    v0.1 scope: single implementation; cross-process byte-identity
    as proxy for the two-independent-implementations requirement.
    """

    def test_c1_replay_byte_identical(self):
        """C1: exported log → replay → byte-identical BeliefState."""
        auth = _auth("alice", "bob")
        log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
        for o in [_obs("a1", "alice", "P", ["a", "b"],
                       {"a": Decimal("0.7"), "a,b": Decimal("0.3")}, 0, auth),
                  _obs("b1", "bob", "P", ["a", "b"],
                       {"a": Decimal("0.5"), "a,b": Decimal("0.5")}, 1, auth)]:
            submit(o, log, g, auth)
        orig = project(log, g, auth, rs, {}, as_of=10)
        rep = replay(export_log(log), auth, {}, 10, log.root())
        assert _enc(rep) == _enc(orig)


# -- C2: Append-only ---------------------------------------------------------

class TestC2AppendOnly:
    """C2: no delete/mutate; consistency proofs verify every extension."""

    def test_c2_consistency_across_appends(self):
        """C2: every later tree extends every earlier tree."""
        auth = _auth("alice")
        log, g = EvidenceLog(), ProvenanceGraph()
        for i in range(5):
            submit(_obs(f"o{i}", "alice", "P", ["a", "b"],
                        {"a": Decimal("0.6"), "a,b": Decimal("0.4")},
                        i, auth), log, g, auth)
        for old in range(6):
            for new in range(old, 6):
                p = log.consistency_proof(old, new)
                assert verify_consistency(
                    p.old_size, p.new_size,
                    p.old_root, p.new_root, p.hashes)


# -- C3: Sybil-calibration ---------------------------------------------------

class TestC3SybilCalibration:
    """C3: k provenance-correlated duplicates leave confidence unchanged."""

    def test_c3_sybil_flat(self):
        """C3: belief bytes identical for k ∈ {1, 10, 50}."""
        ref = None
        for k in (1, 10, 50):
            names = ["alice"] + [f"s{i}" for i in range(k)]
            links = [("s0", f"s{i}") for i in range(1, k)]
            auth = _auth(*names, links=links)
            log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
            submit(_obs("a1", "alice", "P", ["a", "b"],
                        {"a": Decimal("0.6"), "a,b": Decimal("0.4")},
                        0, auth), log, g, auth)
            for i in range(k):
                submit(_obs(f"s{i}", f"s{i}", "P", ["a", "b"],
                            {"a": Decimal("0.9"), "a,b": Decimal("0.1")},
                            i + 1, auth), log, g, auth)
            bs = project(log, g, auth, rs, {}, as_of=100)
            b = _enc(bs["propositions"]["P"]["belief"])
            if ref is None:
                ref = b
            else:
                assert b == ref, f"k={k} belief differs"


# -- C4: Contradiction first-class --------------------------------------------

class TestC4ContradictionFirstClass:
    """C4: mutually exclusive support → explicit contradiction element."""

    def test_c4_contradiction(self):
        """C4: m(∅) > 0 when fusing {a}-support with {b}-support."""
        auth = _auth("alice", "bob")
        log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
        submit(_obs("a1", "alice", "P", ["a", "b"],
                    {"a": Decimal("0.9"), "a,b": Decimal("0.1")},
                    0, auth), log, g, auth)
        submit(_obs("b1", "bob", "P", ["a", "b"],
                    {"b": Decimal("0.9"), "a,b": Decimal("0.1")},
                    1, auth), log, g, auth)
        bs = project(log, g, auth, rs, {}, as_of=10)
        bel = bs["propositions"]["P"]["belief"]
        bw = BeliefWeights.from_weights(
            frozenset(bel["frame"]),
            {(frozenset() if k == "" else frozenset(k.split(","))): v
             for k, v in bel["weights"].items()})
        assert bw.is_contradictory()


# -- C5: Determinism ---------------------------------------------------------

class TestC5Determinism:
    """C5: same log ⇒ same bytes, across processes and hash seeds."""

    def test_c5_cross_process(self):
        """C5: two subprocesses, different PYTHONHASHSEED → identical bytes."""
        script = '''\
import sys, base64
from decimal import Decimal
from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.project import project, submit
from ri_core.provenance import ProvenanceGraph
from ri_core.rules import RuleStore
from ri_core.serialization import encode as enc
a = LocalAuthority(anchor_id="c5", seed=b"seed")
for n in ("alice", "bob"): a.issue_identity(n)
l, g, r = EvidenceLog(), ProvenanceGraph(), RuleStore()
def mk(i, s, m, t):
    u = {"kind": "observation", "id": i, "source_id": s, "proposition": "P",
         "payload": {"frame": ["a", "b"], "mass": m}, "ltime": t}
    return {**u, "sig": a.sign(
        Identity(identity_id=s, anchor_id="c5", name=s), enc(u))}
for o in [mk("a1","alice",{"a":Decimal("0.6"),"a,b":Decimal("0.4")},0),
          mk("b1","bob",{"a":Decimal("0.3"),"a,b":Decimal("0.7")},1)]:
    submit(o, l, g, a)
sys.stdout.write(base64.b64encode(enc(project(l,g,a,r,{},as_of=10))).decode())
'''
        root = str(Path(__file__).parent.parent)
        results = []
        for seed in ("1", "99999"):
            env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": root}
            p = subprocess.run([sys.executable, "-c", script],
                               capture_output=True, text=True, env=env,
                               cwd=root)
            assert p.returncode == 0, f"seed={seed}: {p.stderr}"
            results.append(p.stdout)
        assert results[0] == results[1], "Cross-process bytes differ"


# -- C6: No fabrication ------------------------------------------------------

class TestC6NoFabrication:
    """C6: every belief's provenance traces to the log."""

    def test_c6_provenance_in_log(self):
        """C6: every observation in justification exists at claimed log index."""
        auth = _auth("alice", "bob")
        log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
        for o in [_obs("a1", "alice", "P", ["a", "b"],
                       {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth),
                  _obs("b1", "bob", "P", ["a", "b"],
                       {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)]:
            submit(o, log, g, auth)
        bs = project(log, g, auth, rs, {}, as_of=10)
        for _, data in sorted(bs["propositions"].items()):
            for cls in data["justification"]["classes"]:
                for ref in cls["observations"]:
                    entry = _dec(log.entry(ref["log_index"]))
                    assert entry["kind"] == "observation"
                    assert f"obs:{entry['id']}" == ref["entity_id"]


# -- C7: Rules are evidence --------------------------------------------------

class TestC7RulesAreEvidence:
    """C7: versioned, logged, provenance-carrying; counterfactual defined."""

    def test_c7_rule_in_log(self):
        """C7: rule_version record in log after registration."""
        log, rs = EvidenceLog(), RuleStore()
        rec = rs.register("R1", 1,
                           ["ge", ["field", "ltime"], ["const", 0]], ltime=0)
        log.append(rec)
        entry = _dec(log.entry(0))
        assert entry["kind"] == "rule_version"
        assert entry["rule_id"] == "R1"

    def test_c7_counterfactual_rule(self):
        """C7: different rule version → different belief."""
        auth = _auth("alice", "bob")
        log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
        log.append(rs.register("R1", 1,
            ["eq", ["field", "source_id"], ["const", "alice"]], ltime=0))
        log.append(rs.register("R1", 2,
            ["eq", ["field", "source_id"], ["const", "bob"]], ltime=0))
        for o in [_obs("a1", "alice", "P", ["a", "b"],
                       {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth),
                  _obs("b1", "bob", "P", ["a", "b"],
                       {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)]:
            submit(o, log, g, auth)
        exp = export_log(log)
        bs1 = counterfactual(exp, {}, auth, {"P": ("R1", 1)}, as_of=10)
        bs2 = counterfactual(
            exp, {"rule_bindings_override": {"P": ("R1", 2)}},
            auth, {"P": ("R1", 1)}, as_of=10)
        assert _enc(bs1) != _enc(bs2)


# -- C8: Algebra (CAI) -------------------------------------------------------

class TestC8Algebra:
    """C8: ⊕ is commutative, associative, idempotent."""

    def _bw(self, m_a, m_omega):
        return BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["a"]): Decimal(m_a),
             frozenset(["a", "b"]): Decimal(m_omega)})

    def test_c8_commutative(self):
        """C8: fuse(a, b) == fuse(b, a)."""
        a, b = self._bw("0.6", "0.4"), self._bw("0.3", "0.7")
        assert cautious_fuse(a, b) == cautious_fuse(b, a)

    def test_c8_associative(self):
        """C8: fuse(fuse(a, b), c) == fuse(a, fuse(b, c))."""
        a = self._bw("0.6", "0.4")
        b = self._bw("0.3", "0.7")
        c = self._bw("0.5", "0.5")
        lhs = cautious_fuse(cautious_fuse(a, b), c)
        rhs = cautious_fuse(a, cautious_fuse(b, c))
        assert lhs == rhs

    def test_c8_idempotent(self):
        """C8: fuse(a, a) == a."""
        a = self._bw("0.6", "0.4")
        assert cautious_fuse(a, a) == a


# -- C9: Representation ------------------------------------------------------

class TestC9Representation:
    """C9: not bare scalar; conjunctive weights; dogmatic rejected."""

    def test_c9_not_scalar(self):
        """C9: belief is a structured dict with weights, not a number."""
        auth = _auth("alice")
        log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
        submit(_obs("a1", "alice", "P", ["a", "b"],
                    {"a": Decimal("0.6"), "a,b": Decimal("0.4")},
                    0, auth), log, g, auth)
        bel = project(log, g, auth, rs, {}, as_of=10
                      )["propositions"]["P"]["belief"]
        assert isinstance(bel, dict) and bel["kind"] == "belief_weights"
        assert "weights" in bel and "frame" in bel

    def test_c9_dogmatic_rejected(self):
        """C9: m(Ω)=0 (dogmatic) → ReconciliationError."""
        with pytest.raises(ReconciliationError, match="[Nn]on-dogmatic"):
            BeliefWeights.from_mass(
                frozenset(["a", "b"]),
                {frozenset(["a"]): Decimal("1")})
