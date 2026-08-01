"""Song X acceptance tests (C1-P5) — the contract's acceptance criteria,
asserted, not eyeballed.

(a) The belief object's frame carries the A-majority and B-equal
    hypotheses and names the unresolved/ignorance set; the mass on
    unresolved exceeds the mass on every singleton hypothesis.
(b) The Merkle event log contains the contributing events, each with a
    verifiable inclusion proof.
(c) A replay run reconstructs the belief object byte-identically and
    exits nonzero when identity fails (exercised end to end here; the
    negative path is also covered in test_rights_replay.py).
Plus: the revocation event demonstrably changes the fused belief.

The end-to-end command is `python -m rights_events.song_x` followed by
`python -m rights_events.replay`; both are exercised via subprocess
exactly as documented.
"""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import rights_events
from ri_core.log import leaf_hash, verify_inclusion
from ri_core.serialization import encode
from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.pipeline import RightsPipeline
from rights_events.song_x import (
    HYP_A_MAJORITY,
    HYP_B_EQUAL,
    POST_AS_OF,
    PRE_AS_OF,
    QUESTION,
    SUBJECT,
)
from rights_events.song_x import main as song_x_main
from rights_events.replay import main as replay_main

FIXTURE = (Path(rights_events.__file__).parent / "fixtures"
           / "pro_conflict" / "song_x_SYNTHETIC.json")


def built_pipeline() -> RightsPipeline:
    pipeline = RightsPipeline()
    pipeline.ingest(parse_registrations(FIXTURE.read_text(encoding="utf-8")))
    return pipeline


class TestAcceptanceA_UnresolvedDominates:
    def test_frame_carries_both_hypotheses_and_names_unresolved(self):
        belief = built_pipeline().fold(SUBJECT, QUESTION, PRE_AS_OF)
        assert belief["frame"] == sorted([HYP_A_MAJORITY, HYP_B_EQUAL])
        assert belief["unresolved_set"] == ",".join(belief["frame"])
        assert belief["unresolved_mass"] == \
            belief["mass"][belief["unresolved_set"]]

    def test_unresolved_mass_exceeds_every_singleton(self):
        belief = built_pipeline().fold(SUBJECT, QUESTION, PRE_AS_OF)
        for hyp in belief["frame"]:
            assert belief["unresolved_mass"] > belief["mass"][hyp], (
                f"m(unresolved)={belief['unresolved_mass']} does not "
                f"dominate m({hyp})={belief['mass'][hyp]}")

    def test_exact_masses_match_plan_gate_math(self):
        belief = built_pipeline().fold(SUBJECT, QUESTION, PRE_AS_OF)
        assert belief["mass"][HYP_A_MAJORITY] == Decimal("0.2475")
        assert belief["mass"][HYP_B_EQUAL] == Decimal("0.2475")
        assert belief["unresolved_mass"] == Decimal("0.3025")
        assert belief["conflict_mass"] == Decimal("0.2025")


class TestAcceptanceB_InclusionProofs:
    def test_every_contributing_event_proves_inclusion(self):
        pipeline = built_pipeline()
        belief, _ = pipeline.commit(SUBJECT, QUESTION, POST_AS_OF)
        assert len(belief["contributing_events"]) == 4
        for c in belief["contributing_events"]:
            entry = pipeline.event_log.entry(c["log_index"])
            proof = pipeline.event_log.inclusion_proof(
                c["log_index"], belief["event_log_size"])
            assert verify_inclusion(
                leaf_hash(entry), proof.index, proof.tree_size,
                proof.hashes, proof.root_hash)
            assert proof.root_hash == belief["event_log_root"]


class TestAcceptanceC_ReplayByteIdentity:
    def test_replay_reconstructs_byte_identically(self, tmp_path):
        pipeline = built_pipeline()
        belief, index = pipeline.commit(SUBJECT, QUESTION, PRE_AS_OF)
        run = tmp_path / "run.ri"
        pipeline.save(run)
        loaded = RightsPipeline.load(run)
        refolded = loaded.fold(SUBJECT, QUESTION, belief["as_of"],
                               at_size=belief["event_log_size"])
        assert encode(refolded) == loaded.belief_log.entry(index)


class TestRevocationDelta:
    def test_revocation_changes_the_fused_belief(self):
        pipeline = built_pipeline()
        pre = pipeline.fold(SUBJECT, QUESTION, PRE_AS_OF)
        post = pipeline.fold(SUBJECT, QUESTION, POST_AS_OF)
        assert pre["frame"] == post["frame"]
        assert pre["mass"] != post["mass"]
        assert post["mass"][HYP_A_MAJORITY] == Decimal("0.45")
        assert post["mass"][HYP_B_EQUAL] == Decimal("0")
        assert post["unresolved_mass"] == Decimal("0.55")
        assert post["conflict_mass"] == Decimal("0")


class TestEndToEndCommand:
    def test_in_process_end_to_end(self, tmp_path, capsys):
        out = tmp_path / "song_x_run.ri"
        code = song_x_main(["--out", str(out)])
        printed = capsys.readouterr().out
        assert code == 0
        assert "SYNTHETIC" in printed
        assert "PASS  A1" in printed
        assert "PASS  A2" in printed
        assert "PASS  A3" in printed
        assert "PASS  A4" in printed
        assert "SONG X END-TO-END: OK" in printed
        assert out.exists()

        replay_code = replay_main(
            ["--run", str(out), "--subject", SUBJECT])
        replay_out = capsys.readouterr().out
        assert replay_code == 0
        assert "byte-identity:       IDENTICAL" in replay_out
        assert "REPLAY: OK" in replay_out

    def test_documented_commands_via_subprocess(self, tmp_path):
        package_root = Path(rights_events.__file__).parent.parent
        out = tmp_path / "song_x_run.ri"
        run1 = subprocess.run(
            [sys.executable, "-m", "rights_events.song_x",
             "--out", str(out)],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=120)
        assert run1.returncode == 0, run1.stdout + run1.stderr
        assert "SONG X END-TO-END: OK" in run1.stdout

        run2 = subprocess.run(
            [sys.executable, "-m", "rights_events.replay",
             "--run", str(out), "--subject", SUBJECT],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=120)
        assert run2.returncode == 0, run2.stdout + run2.stderr
        assert "REPLAY: OK" in run2.stdout

    def test_run_file_bytes_are_machine_stable(self, tmp_path):
        # Two independent end-to-end runs produce byte-identical run
        # files (Contract 1 Constraint 4).
        out1, out2 = tmp_path / "a.ri", tmp_path / "b.ri"
        assert song_x_main(["--out", str(out1)]) == 0
        assert song_x_main(["--out", str(out2)]) == 0
        assert out1.read_bytes() == out2.read_bytes()
