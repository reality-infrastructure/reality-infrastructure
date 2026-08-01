"""Parcel runner and structural-identity tests (C2-P3).

The Contract 2 acceptance instrument: real Cook County parcels flow
through the layer Contract 1 shipped, unchanged, and a contested
parcel's belief object is structurally congruent with Song X's —
programmatically asserted, key set by key set. The unchanged replay
CLI verifies parcel runs with the same commands and flags it had.

The redemption/lien-release delta test is NOT here: it is
conditionally blocked on the operator's R2 export (see PROGRESS.md,
finding F2). Nothing synthetic substitutes for it.
"""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import rights_events
from ri_core.serialization import decode, encode
from rights_events.adapters.cook_parcels import parse_all
from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.parcels import QUESTION
from rights_events.parcels import main as parcels_main
from rights_events.pipeline import RightsPipeline
from rights_events.policy import ltime_for
from rights_events.replay import main as replay_main
from rights_events.song_x import PRE_AS_OF
from rights_events.song_x import SUBJECT as SONG_X_SUBJECT

FIXTURES = Path(rights_events.__file__).parent / "fixtures"

# The two named contested parcels asserted in acceptance.
CONTESTED_DOLTON = "parcel:29024080530000"
CONTESTED_CHAIN = "parcel:29033140260000"


def parcels_pipeline():
    fx = FIXTURES / "parcels"
    events = parse_all(
        (fx / "deeds.json").read_text(encoding="utf-8"),
        (fx / "assessor_owners.json").read_text(encoding="utf-8"),
        (fx / "tax_sale_forfeitures.json").read_text(encoding="utf-8"))
    pipeline = RightsPipeline()
    pipeline.ingest(events)
    as_of = max(ltime_for(e.observed_date) for e in events)
    return pipeline, as_of


def song_x_belief():
    pipeline = RightsPipeline()
    pipeline.ingest(parse_registrations(
        (FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
            encoding="utf-8")))
    return pipeline.fold(SONG_X_SUBJECT, QUESTION, PRE_AS_OF)


class TestContestedParcels:
    def test_dolton_belief_competing_claims_conflict_and_omega(self):
        pipeline, as_of = parcels_pipeline()
        belief = pipeline.fold(CONTESTED_DOLTON, QUESTION, as_of)
        positive = [h for h in belief["frame"]
                    if belief["mass"][h] > 0]
        assert len(positive) == 5
        assert belief["conflict_mass"] == Decimal("0.91296")
        assert belief["unresolved_mass"] == Decimal("0.01024")

    def test_chain_break_parcel_includes_county_interest(self):
        pipeline, as_of = parcels_pipeline()
        belief = pipeline.fold(CONTESTED_CHAIN, QUESTION, as_of)
        assert "shares:COOK COUNTY=100" in belief["frame"]
        positive = [h for h in belief["frame"]
                    if belief["mass"][h] > 0]
        assert len(positive) == 4

    def test_contributing_events_carry_real_provenance(self):
        pipeline, as_of = parcels_pipeline()
        for subject in (CONTESTED_DOLTON, CONTESTED_CHAIN):
            belief = pipeline.fold(subject, QUESTION, as_of)
            for c in belief["contributing_events"]:
                obs = decode(pipeline.event_log.entry(c["log_index"]))
                event = obs["payload"]["event"]
                assert event["source_url"].startswith("https://")
                assert len(event["observed_date"]) == 10


class TestStructuralIdentity:
    """A parcel belief object and the Song X belief object are the
    same structure; only the domain content differs."""

    def parcel_belief(self):
        pipeline, as_of = parcels_pipeline()
        return pipeline.fold(CONTESTED_DOLTON, QUESTION, as_of)

    def test_same_top_level_keys(self):
        assert set(self.parcel_belief()) == set(song_x_belief())

    def test_same_mass_report_shape(self):
        for belief in (self.parcel_belief(), song_x_belief()):
            assert belief["kind"] == "rights_belief"
            assert belief["policy_version"] == "rights-mass-policy-v1"
            omega = ",".join(sorted(belief["frame"]))
            assert belief["unresolved_set"] == omega
            assert belief["unresolved_mass"] == belief["mass"][omega]
            assert belief["conflict_mass"] == belief["mass"][""]
            for hyp in belief["frame"]:
                assert hyp in belief["mass"]
            assert isinstance(belief["event_log_root"], bytes)

    def test_same_contributing_event_record_shape(self):
        parcel_keys = {frozenset(c)
                       for c in self.parcel_belief()["contributing_events"]}
        song_keys = {frozenset(c)
                     for c in song_x_belief()["contributing_events"]}
        assert parcel_keys == song_keys

    def test_both_replay_byte_identically(self, tmp_path):
        for name, (pipeline, subject, as_of) in {
            "parcel": (*_committed(parcels_pipeline, CONTESTED_DOLTON),),
            "song": (*_committed_song(),),
        }.items():
            run = tmp_path / f"{name}.ri"
            pipeline.save(run)
            loaded = RightsPipeline.load(run)
            belief = decode(loaded.belief_log.entry(0))
            refolded = loaded.fold(subject, QUESTION, as_of,
                                   at_size=belief["event_log_size"])
            assert encode(refolded) == loaded.belief_log.entry(0)


def _committed(factory, subject):
    pipeline, as_of = factory()
    pipeline.commit(subject, QUESTION, as_of)
    return pipeline, subject, as_of


def _committed_song():
    pipeline = RightsPipeline()
    pipeline.ingest(parse_registrations(
        (FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
            encoding="utf-8")))
    pipeline.commit(SONG_X_SUBJECT, QUESTION, PRE_AS_OF)
    return pipeline, SONG_X_SUBJECT, PRE_AS_OF


class TestRunnerEndToEnd:
    def test_in_process_run(self, tmp_path, capsys):
        out = tmp_path / "parcels_run.ri"
        code = parcels_main(["--out", str(out)])
        printed = capsys.readouterr().out
        assert code == 0
        assert "PASS  B1" in printed
        assert "PASS  B2" in printed
        assert "PASS  B3" in printed
        assert "RECORDS DISAGREE" in printed
        assert "PARCELS END-TO-END: OK" in printed
        assert out.exists()

    def test_two_runs_byte_identical(self, tmp_path):
        out1, out2 = tmp_path / "a.ri", tmp_path / "b.ri"
        assert parcels_main(["--out", str(out1)]) == 0
        assert parcels_main(["--out", str(out2)]) == 0
        assert out1.read_bytes() == out2.read_bytes()

    def test_unchanged_replay_cli_verifies_parcel_run(self, tmp_path,
                                                      capsys):
        out = tmp_path / "parcels_run.ri"
        assert parcels_main(["--out", str(out)]) == 0
        capsys.readouterr()
        code = replay_main(["--run", str(out),
                            "--subject", CONTESTED_DOLTON])
        printed = capsys.readouterr().out
        assert code == 0
        assert "byte-identity:       IDENTICAL" in printed
        assert "REPLAY: OK" in printed

    def test_replay_cli_tamper_exits_nonzero(self, tmp_path, capsys):
        out = tmp_path / "parcels_run.ri"
        assert parcels_main(["--out", str(out)]) == 0
        capsys.readouterr()
        data = decode(out.read_bytes())
        belief = decode(data["belief_log"]["entries"][0])
        belief["conflict_mass"] = Decimal("0")  # falsify the conflict
        data["belief_log"]["entries"][0] = encode(belief)
        tampered = tmp_path / "tampered.ri"
        tampered.write_bytes(encode(data))
        code = replay_main(["--run", str(tampered),
                            "--subject", CONTESTED_DOLTON,
                            "--belief-index", "0"])
        assert code == 1

    def test_documented_commands_via_subprocess(self, tmp_path):
        package_root = Path(rights_events.__file__).parent.parent
        out = tmp_path / "parcels_run.ri"
        run1 = subprocess.run(
            [sys.executable, "-m", "rights_events.parcels",
             "--out", str(out)],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=180)
        assert run1.returncode == 0, run1.stdout + run1.stderr
        assert "PARCELS END-TO-END: OK" in run1.stdout

        run2 = subprocess.run(
            [sys.executable, "-m", "rights_events.replay",
             "--run", str(out), "--subject", CONTESTED_CHAIN],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=180)
        assert run2.returncode == 0, run2.stdout + run2.stderr
        assert "REPLAY: OK" in run2.stdout
