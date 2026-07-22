"""Tests for ri_core.replay — replay and counterfactual engine.

Covers all M-RI-08 acceptance criteria:
- T1: replay of unmodified export ≡ original projection (byte-identical)
- Tamper: flipped byte and truncated bytes → ReplayError at root check
- Counterfactual REMOVE: remove contradicting observation → not contradictory
- Counterfactual ADD: retroactive observation → belief reflects it
- Counterfactual RULE SUBSTITUTION: v1 vs v2 → different exclusion sets
- Empty delta ≡ replay (byte-identical)
- S6 determinism: cross-process, golden file match
- A3: duplicate rule_version in add_entries → ReplayError wrapping RuleError
- Unknown entry kind → ReplayError
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
from ri_core.log import EvidenceLog
from ri_core.project import project, submit
from ri_core.provenance import ProvenanceGraph
from ri_core.reconcile import BeliefWeights, cautious_fuse
from ri_core.replay import ReplayError, counterfactual, export_log, replay
from ri_core.rules import RuleStore
from ri_core.rules import evaluate as _rule_evaluate
from ri_core.serialization import decode as _ser_decode
from ri_core.serialization import encode as _ser_encode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "golden" / "replay"


def _make_authority(*names: str) -> LocalAuthority:
    auth = LocalAuthority(anchor_id="test", seed=b"test-seed")
    for name in names:
        auth.issue_identity(name)
    return auth


def _make_obs(
    obs_id: str,
    source_id: str,
    proposition: str,
    frame: list[str],
    mass: dict[str, Decimal],
    ltime: int,
    authority: LocalAuthority,
) -> dict:
    unsigned = {
        "kind": "observation",
        "id": obs_id,
        "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": frame, "mass": mass},
        "ltime": ltime,
    }
    ub = _ser_encode(unsigned)
    identity = Identity(
        identity_id=source_id,
        anchor_id=authority.anchor_id,
        name=source_id,
    )
    sig = authority.sign(identity, ub)
    obs = dict(unsigned)
    obs["sig"] = sig
    return obs


def _build_e2e_fixture():
    """Build the full M-RI-07 end-to-end fixture WITH rule_version logged.

    Returns (log, graph, rule_store, authority, rule_bindings, as_of,
             belief_state).
    """
    auth = _make_authority("alice", "bob", "charlie")
    log = EvidenceLog()
    graph = ProvenanceGraph()
    rs = RuleStore()

    # Register rule R1 and LOG it (SPEC §11: rules as first-class evidence).
    record = rs.register(
        "R1", 1,
        ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
        ltime=0)
    log.append(record)

    obs_a1 = _make_obs(
        "a1", "alice", "P1", ["a", "b"],
        {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
    obs_b1 = _make_obs(
        "b1", "bob", "P1", ["a", "b"],
        {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
    obs_a2 = _make_obs(
        "a2", "alice", "P2", ["a", "b"],
        {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
    obs_c2 = _make_obs(
        "c2", "charlie", "P2", ["a", "b"],
        {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 1, auth)

    for obs in [obs_a1, obs_b1, obs_a2, obs_c2]:
        submit(obs, log, graph, auth)

    rule_bindings = {"P2": ("R1", 1)}
    as_of = 10
    bs = project(log, graph, auth, rs, rule_bindings, as_of)
    return log, graph, rs, auth, rule_bindings, as_of, bs


# ---------------------------------------------------------------------------
# T1: Replay byte-identity
# ---------------------------------------------------------------------------


class TestReplayByteIdentity:
    """T1: replay of unmodified export == original projection, byte-for-byte."""

    def test_replay_byte_identical(self):
        log, graph, rs, auth, bindings, as_of, original_bs = (
            _build_e2e_fixture())

        export = export_log(log)
        expected_root = log.root()

        replayed_bs = replay(
            export, auth, bindings, as_of, expected_root)

        assert _ser_encode(replayed_bs) == _ser_encode(original_bs)

    def test_replay_root_identical(self):
        log, graph, rs, auth, bindings, as_of, original_bs = (
            _build_e2e_fixture())

        export = export_log(log)
        expected_root = log.root()

        # After replay, export the replayed log and verify root matches.
        replayed_bs = replay(
            export, auth, bindings, as_of, expected_root)

        # Reconstruct replay log to check root.
        replay_log = EvidenceLog()
        for entry_bytes in export["entries"]:
            replay_log.append(_ser_decode(entry_bytes))
        assert replay_log.root() == expected_root

    def test_replay_entry_for_entry(self):
        """A1 postcondition: export_log(replay_log) entries match original."""
        log, graph, rs, auth, bindings, as_of, original_bs = (
            _build_e2e_fixture())

        export = export_log(log)
        expected_root = log.root()

        # Reconstruct replay log.
        replay_log = EvidenceLog()
        for entry_bytes in export["entries"]:
            replay_log.append(_ser_decode(entry_bytes))

        replay_export = export_log(replay_log)
        assert len(replay_export["entries"]) == len(export["entries"])
        for i, (orig, rep) in enumerate(
                zip(export["entries"], replay_export["entries"])):
            assert orig == rep, f"entry mismatch at index {i}"


# ---------------------------------------------------------------------------
# Tamper test
# ---------------------------------------------------------------------------


class TestTamper:
    """Root-check catches tampered entries."""

    def test_flipped_byte(self):
        log, graph, rs, auth, bindings, as_of, _ = _build_e2e_fixture()
        export = export_log(log)
        expected_root = log.root()

        # Flip one byte in the middle of the second entry (ASCII region).
        tampered = list(export["entries"])
        original_entry = tampered[1]
        flipped = bytearray(original_entry)
        # Flip byte at position 10 (inside the JSON, ASCII safe).
        flipped[10] ^= 0x01
        tampered[1] = bytes(flipped)

        tampered_export = {"kind": "log_export", "entries": tampered}
        # May be root_mismatch (content changed) or malformed_entry
        # (JSON decode failure) depending on which byte was hit.
        with pytest.raises(ReplayError):
            replay(tampered_export, auth, bindings, as_of, expected_root)

    def test_truncated_entry(self):
        """A2 amendment: truncated bytes → ReplayError(malformed_entry)."""
        log, graph, rs, auth, bindings, as_of, _ = _build_e2e_fixture()
        export = export_log(log)
        expected_root = log.root()

        tampered = list(export["entries"])
        tampered[0] = tampered[0][:2]  # Truncate to just version byte + 1

        tampered_export = {"kind": "log_export", "entries": tampered}
        with pytest.raises(ReplayError, match="malformed_entry"):
            replay(tampered_export, auth, bindings, as_of, expected_root)

    def test_empty_bytes_entry(self):
        """Empty bytes → malformed_entry before root check."""
        log, graph, rs, auth, bindings, as_of, _ = _build_e2e_fixture()
        export = export_log(log)
        expected_root = log.root()

        tampered = list(export["entries"])
        tampered[0] = b""

        tampered_export = {"kind": "log_export", "entries": tampered}
        with pytest.raises(ReplayError, match="malformed_entry"):
            replay(tampered_export, auth, bindings, as_of, expected_root)


# ---------------------------------------------------------------------------
# Counterfactual REMOVE
# ---------------------------------------------------------------------------


class TestCounterfactualRemove:
    """Removing contradicting observation flips is_contradictory."""

    def test_remove_contradicting(self):
        auth = _make_authority("alice", "bob")
        log = EvidenceLog()
        graph = ProvenanceGraph()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.9"), "a,b": Decimal("0.1")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"b": Decimal("0.9"), "a,b": Decimal("0.1")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        original_bs = project(log, graph, auth, rs, {}, as_of=10)

        # Original belief IS contradictory: fuse gives m(∅) > 0.
        bw_orig = cautious_fuse(
            BeliefWeights.from_mass(
                frozenset(["a", "b"]),
                {frozenset(["a"]): Decimal("0.9"),
                 frozenset(["a", "b"]): Decimal("0.1")}),
            BeliefWeights.from_mass(
                frozenset(["a", "b"]),
                {frozenset(["b"]): Decimal("0.9"),
                 frozenset(["a", "b"]): Decimal("0.1")}),
        )
        assert bw_orig.is_contradictory()
        assert original_bs["propositions"]["P"]["belief"] == bw_orig.to_dict()

        export = export_log(log)

        # Remove bob's contradicting observation (index 1).
        cf_bs = counterfactual(
            export,
            {"remove_entry_indices": [1]},
            auth, {}, as_of=10)

        # Counterfactual belief is NOT contradictory (alice only).
        cf_belief = cf_bs["propositions"]["P"]["belief"]
        expected = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["a"]): Decimal("0.9"),
             frozenset(["a", "b"]): Decimal("0.1")})
        assert not expected.is_contradictory()
        assert cf_belief == expected.to_dict()


# ---------------------------------------------------------------------------
# Counterfactual ADD
# ---------------------------------------------------------------------------


class TestCounterfactualAdd:
    """Adding a retroactive observation is reflected in belief."""

    def test_add_retroactive(self):
        auth = _make_authority("alice", "bob")
        log = EvidenceLog()
        graph = ProvenanceGraph()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs_a, log, graph, auth)

        original_bs = project(log, graph, auth, rs, {}, as_of=10)

        export = export_log(log)

        # Add bob's observation retroactively (ltime=1 ≤ as_of=10).
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        new_entry_bytes = _ser_encode(obs_b)

        cf_bs = counterfactual(
            export,
            {"add_entries": [new_entry_bytes]},
            auth, {}, as_of=10)

        # Counterfactual now has both observations fused.
        cf_belief = cf_bs["propositions"]["P"]["belief"]
        expected = cautious_fuse(
            BeliefWeights.from_mass(
                frozenset(["a", "b"]),
                {frozenset(["a"]): Decimal("0.6"),
                 frozenset(["a", "b"]): Decimal("0.4")}),
            BeliefWeights.from_mass(
                frozenset(["a", "b"]),
                {frozenset(["a"]): Decimal("0.3"),
                 frozenset(["a", "b"]): Decimal("0.7")}),
        )
        assert cf_belief == expected.to_dict()

        # Derived entity id reflects new log size (2 entries vs 1).
        # Original has size:1 in entity id; counterfactual has size:2.
        cf_just = cf_bs["propositions"]["P"]["justification"]
        assert len(cf_just["classes"]) == 2  # Two provenance classes.


# ---------------------------------------------------------------------------
# Counterfactual RULE SUBSTITUTION
# ---------------------------------------------------------------------------


class TestCounterfactualRuleSubstitution:
    """Same log, rule v1 vs v2 → different exclusion sets, different beliefs."""

    def test_rule_substitution(self):
        auth = _make_authority("alice", "bob", "charlie")
        log = EvidenceLog()
        graph = ProvenanceGraph()
        rs = RuleStore()

        # Register rule R1 v1: source_id in [alice, bob].
        record_v1 = rs.register(
            "R1", 1,
            ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
            ltime=0)
        log.append(record_v1)

        # Register rule R1 v2: source_id in [alice, charlie].
        record_v2 = rs.register(
            "R1", 2,
            ["in", ["field", "source_id"], ["const", ["alice", "charlie"]]],
            ltime=0)
        log.append(record_v2)

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        obs_c = _make_obs(
            "oc", "charlie", "P", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 2, auth)

        for obs in [obs_a, obs_b, obs_c]:
            submit(obs, log, graph, auth)

        export = export_log(log)

        # With v1: alice + bob pass, charlie excluded.
        bs_v1 = counterfactual(
            export, {},
            auth, {"P": ("R1", 1)}, as_of=10)

        # With v2: alice + charlie pass, bob excluded.
        bs_v2 = counterfactual(
            export,
            {"rule_bindings_override": {"P": ("R1", 2)}},
            auth, {"P": ("R1", 1)}, as_of=10)

        # Different beliefs.
        assert _ser_encode(bs_v1) != _ser_encode(bs_v2)

        # Verify exclusion sets differ.
        v1_excluded = bs_v1["propositions"]["P"]["justification"]["excluded"]
        v2_excluded = bs_v2["propositions"]["P"]["justification"]["excluded"]
        v1_ids = {e["entity_id"] for e in v1_excluded}
        v2_ids = {e["entity_id"] for e in v2_excluded}
        assert "obs:oc" in v1_ids  # charlie excluded by v1
        assert "obs:ob" in v2_ids  # bob excluded by v2

        # Both justifications pass the independent checker
        # (reading rule specs FROM LOG BYTES).
        for bs, bound_v in [(bs_v1, 1), (bs_v2, 2)]:
            self._check_justification_from_log(
                export["entries"], bs, bound_v)

    def _check_justification_from_log(
        self, entries: list[bytes], bs: dict, bound_version: int,
    ) -> None:
        """A2-correct independent checker: reads rule specs from log bytes."""
        # Extract rule specs from log entries.
        rule_specs: dict[tuple[str, int], dict] = {}
        for entry_bytes in entries:
            decoded = _ser_decode(entry_bytes)
            if isinstance(decoded, dict) and decoded.get("kind") == "rule_version":
                key = (decoded["rule_id"], decoded["version"])
                rule_specs[key] = decoded

        for prop_name, prop_data in bs["propositions"].items():
            just = prop_data["justification"]
            belief = prop_data["belief"]

            if belief is None:
                assert len(just["classes"]) == 0
                continue

            # Collect observation entries from log.
            obs_entries = []
            for cls in just["classes"]:
                for obs_ref in cls["observations"]:
                    log_idx = obs_ref["log_index"]
                    entry = _ser_decode(entries[log_idx])
                    obs_entries.append(entry)

            # Re-evaluate rules using spec FROM LOG BYTES.
            if "rule_applied" in just:
                r_id = just["rule_applied"]["rule_id"]
                r_ver = just["rule_applied"]["version"]
                r_spec = rule_specs[(r_id, r_ver)]
                passing = []
                for entry in obs_entries:
                    eval_obs = {
                        k: v for k, v in entry.items() if k != "sig"}
                    vr = _rule_evaluate(r_spec, eval_obs)
                    assert vr["verdict"], (
                        f"Checker: obs {entry['id']} in classes "
                        f"but fails rule")
                    passing.append(entry)
            else:
                passing = obs_entries

            # Reconstruct and compare beliefs.
            recomputed = []
            for entry in passing:
                from ri_core.project import _parse_payload
                frame, mass_dict = _parse_payload(entry["payload"])
                recomputed.append(
                    BeliefWeights.from_mass(frame, mass_dict))

            recomputed_fused = cautious_fuse(*recomputed)
            assert recomputed_fused.to_dict() == belief, (
                f"Checker failed for proposition {prop_name!r}")


# ---------------------------------------------------------------------------
# Empty delta ≡ replay
# ---------------------------------------------------------------------------


class TestEmptyDelta:
    """Counterfactual with empty delta == replay, byte-identical."""

    def test_empty_delta_byte_identical(self):
        log, graph, rs, auth, bindings, as_of, original_bs = (
            _build_e2e_fixture())

        export = export_log(log)
        expected_root = log.root()

        replayed = replay(export, auth, bindings, as_of, expected_root)
        cf_empty = counterfactual(export, {}, auth, bindings, as_of)

        assert _ser_encode(replayed) == _ser_encode(cf_empty)


# ---------------------------------------------------------------------------
# S6 determinism: cross-process + golden file
# ---------------------------------------------------------------------------


class TestCrossProcessDeterminism:
    """S6: same counterfactual in 2 subprocesses, different PYTHONHASHSEED."""

    def test_cross_process_determinism(self):
        script = '''\
import sys, base64
from decimal import Decimal
from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.project import submit
from ri_core.provenance import ProvenanceGraph
from ri_core.rules import RuleStore
from ri_core.replay import export_log, counterfactual
from ri_core.serialization import encode as _ser_encode

auth = LocalAuthority(anchor_id="test", seed=b"test-seed")
for n in ["alice", "bob", "charlie"]:
    auth.issue_identity(n)

log = EvidenceLog()
graph = ProvenanceGraph()
rs = RuleStore()

record_v1 = rs.register("R1", 1,
    ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
    ltime=0)
log.append(record_v1)

record_v2 = rs.register("R1", 2,
    ["in", ["field", "source_id"], ["const", ["alice", "charlie"]]],
    ltime=0)
log.append(record_v2)

def make_obs(obs_id, source_id, proposition, frame, mass, ltime):
    unsigned = {
        "kind": "observation", "id": obs_id, "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": frame, "mass": mass}, "ltime": ltime,
    }
    ub = _ser_encode(unsigned)
    identity = Identity(identity_id=source_id, anchor_id="test", name=source_id)
    sig = auth.sign(identity, ub)
    obs = dict(unsigned)
    obs["sig"] = sig
    return obs

for obs in [
    make_obs("oa", "alice", "P", ["a","b"],
             {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0),
    make_obs("ob", "bob", "P", ["a","b"],
             {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1),
    make_obs("oc", "charlie", "P", ["a","b"],
             {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 2),
]:
    submit(obs, log, graph, auth)

export = export_log(log)

# Counterfactual: remove bob, override to v2.
cf_bs = counterfactual(
    export,
    {"remove_entry_indices": [3],
     "rule_bindings_override": {"P": ("R1", 2)}},
    auth, {"P": ("R1", 1)}, as_of=10)

sys.stdout.write(base64.b64encode(_ser_encode(cf_bs)).decode())
'''
        project_root = str(Path(__file__).parent.parent)
        results = []
        for seed in ["42", "9999"]:
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = project_root
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env,
                cwd=project_root,
            )
            assert proc.returncode == 0, (
                f"seed={seed} failed:\n{proc.stderr}")
            results.append(proc.stdout)

        assert results[0] == results[1], (
            "Cross-process determinism failed")

        # Golden file byte-match.
        encoded = base64.b64decode(results[0])
        golden_path = GOLDEN_DIR / "counterfactual_belief_state.bin"
        if not golden_path.exists():
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_bytes(encoded)
        expected = golden_path.read_bytes()
        assert encoded == expected, "golden file mismatch"


# ---------------------------------------------------------------------------
# A3 amendment: duplicate rule_version in add_entries → ReplayError
# ---------------------------------------------------------------------------


class TestDeltaRuleConflict:
    """A3: add_entries with conflicting rule_version → ReplayError."""

    def test_duplicate_rule_version(self):
        auth = _make_authority("alice")
        log = EvidenceLog()
        graph = ProvenanceGraph()
        rs = RuleStore()

        record = rs.register(
            "R1", 1,
            ["ge", ["field", "ltime"], ["const", 0]],
            ltime=0)
        log.append(record)

        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
        submit(obs, log, graph, auth)

        export = export_log(log)

        # Add a duplicate rule_version (R1 v1 already in log).
        dup_record = {
            "kind": "rule_version",
            "rule_id": "R1",
            "version": 1,
            "fn_spec": ["ge", ["field", "ltime"], ["const", 0]],
            "ltime": 0,
        }
        dup_bytes = _ser_encode(dup_record)

        with pytest.raises(ReplayError, match="rule registration failed"):
            counterfactual(
                export,
                {"add_entries": [dup_bytes]},
                auth, {"P": ("R1", 1)}, as_of=10)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """Validation errors produce typed ReplayError."""

    def test_bad_export_kind(self):
        with pytest.raises(ReplayError, match="kind"):
            replay({"kind": "wrong", "entries": []},
                   _make_authority(), {}, 0, b"\x00" * 32)

    def test_remove_index_out_of_range(self):
        auth = _make_authority("alice")
        log = EvidenceLog()
        graph = ProvenanceGraph()

        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
        submit(obs, log, graph, auth)

        export = export_log(log)
        with pytest.raises(ReplayError, match="remove_index_out_of_range"):
            counterfactual(export, {"remove_entry_indices": [99]},
                           auth, {}, as_of=10)

    def test_malformed_add_entry(self):
        auth = _make_authority("alice")
        log = EvidenceLog()
        export = export_log(log)

        with pytest.raises(ReplayError, match="malformed_entry"):
            counterfactual(export, {"add_entries": [b"\x01{bad"]},
                           auth, {}, as_of=10)

    def test_unknown_entry_kind(self):
        auth = _make_authority("alice")
        log = EvidenceLog()
        graph = ProvenanceGraph()

        # Manually add a non-observation, non-rule entry.
        log.append({"kind": "unknown_thing", "data": 1})

        export = export_log(log)
        expected_root = log.root()

        with pytest.raises(ReplayError, match="unknown_entry_kind"):
            replay(export, auth, {}, as_of=10,
                   expected_root=expected_root)
