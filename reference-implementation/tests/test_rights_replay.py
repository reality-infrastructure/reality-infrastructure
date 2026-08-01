"""Tests for the replay CLI (C1-P4).

Covers: byte-identity verification (exit 0 and IDENTICAL output),
nonzero exit on tampered belief entries (the acceptance instrument:
replay exits nonzero if identity fails), belief selection by index and
by latest match, --expected-root pinning, anchoring to the commit-time
log size after the log grows, and the documented `python -m
rights_events.replay` invocation via subprocess.
"""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import rights_events
from ri_core.serialization import decode, encode
from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.adapters.tdmrep import parse_robots_txt
from rights_events.pipeline import RightsPipeline
from rights_events.policy import ltime_for
from rights_events.replay import main

FIXTURES = Path(rights_events.__file__).parent / "fixtures"

SUBJECT = "work:song-x"
QUESTION = "ownership_shares"
PRE = ltime_for("2026-06-09")
POST = ltime_for("2026-07-01")


def committed_run(tmp_path, commits=((SUBJECT, QUESTION, PRE),)) -> Path:
    events = parse_registrations(
        (FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
            encoding="utf-8"))
    pipeline = RightsPipeline()
    pipeline.ingest(events)
    for subject, question, as_of in commits:
        pipeline.commit(subject, question, as_of)
    run_path = tmp_path / "run.ri"
    pipeline.save(run_path)
    return run_path


class TestReplayHappyPath:
    def test_exit_zero_and_identical(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        code = main(["--run", str(run), "--subject", SUBJECT])
        out = capsys.readouterr().out
        assert code == 0
        assert "byte-identity:       IDENTICAL" in out
        assert "event log root:      MATCH" in out
        assert "belief inclusion:    VERIFIED" in out
        assert "event inclusions:    3/3 verified" in out
        assert "REPLAY: OK" in out

    def test_prints_mass_assignments_with_omega_named(self, tmp_path,
                                                      capsys):
        run = committed_run(tmp_path)
        code = main(["--run", str(run), "--subject", SUBJECT])
        out = capsys.readouterr().out
        assert code == 0
        assert "unresolved (ignorance set Omega)" in out
        assert "conflict: empty set" in out
        assert "unresolved_mass = 0.3025" in out
        assert "conflict_mass   = 0.2025" in out

    def test_latest_match_selected_by_default(self, tmp_path, capsys):
        run = committed_run(
            tmp_path, commits=((SUBJECT, QUESTION, PRE),
                               (SUBJECT, QUESTION, POST)))
        code = main(["--run", str(run), "--subject", SUBJECT])
        out = capsys.readouterr().out
        assert code == 0
        assert f"as_of {POST}" in out

    def test_belief_index_selects_specific_entry(self, tmp_path, capsys):
        run = committed_run(
            tmp_path, commits=((SUBJECT, QUESTION, PRE),
                               (SUBJECT, QUESTION, POST)))
        code = main(["--run", str(run), "--subject", SUBJECT,
                     "--belief-index", "0"])
        out = capsys.readouterr().out
        assert code == 0
        assert f"as_of {PRE}" in out

    def test_expected_root_match(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        pipeline = RightsPipeline.load(run)
        root_hex = pipeline.event_log.root(4).hex()
        code = main(["--run", str(run), "--subject", SUBJECT,
                     "--expected-root", root_hex])
        out = capsys.readouterr().out
        assert code == 0
        assert "--expected-root:     MATCH" in out

    def test_replay_after_log_grows(self, tmp_path, capsys):
        # Commit at size 4, then ingest unrelated events; the belief
        # must stay byte-reproducible via its recorded event_log_size.
        events = parse_registrations(
            (FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
                encoding="utf-8"))
        pipeline = RightsPipeline()
        pipeline.ingest(events)
        pipeline.commit(SUBJECT, QUESTION, PRE)
        robots = parse_robots_txt(
            (FIXTURES / "tdmrep" / "nytimes_robots.txt").read_text(
                encoding="utf-8"),
            site_host="www.nytimes.com",
            source_url="https://www.nytimes.com/robots.txt",
            observed_date="2026-08-01")
        pipeline.ingest(robots)
        run = tmp_path / "grown.ri"
        pipeline.save(run)

        code = main(["--run", str(run), "--subject", SUBJECT])
        out = capsys.readouterr().out
        assert code == 0
        assert "byte-identity:       IDENTICAL" in out


class TestReplayFailures:
    def test_tampered_belief_entry_exits_nonzero(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        data = decode(run.read_bytes())
        belief = decode(data["belief_log"]["entries"][0])
        belief["mass"][""] = Decimal("0.1")  # falsify the conflict mass
        data["belief_log"]["entries"][0] = encode(belief)
        tampered = tmp_path / "tampered.ri"
        tampered.write_bytes(encode(data))

        code = main(["--run", str(tampered), "--subject", SUBJECT])
        out = capsys.readouterr().out
        assert code == 1
        assert "byte-identity:       FAIL" in out
        assert "REPLAY: FAILED" in out

    def test_unknown_subject_exits_two(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        code = main(["--run", str(run), "--subject", "work:unknown"])
        assert code == 2
        assert "ERROR" in capsys.readouterr().out

    def test_unreadable_run_exits_two(self, tmp_path, capsys):
        bad = tmp_path / "bad.ri"
        bad.write_bytes(b"\x01not json")
        code = main(["--run", str(bad), "--subject", SUBJECT])
        assert code == 2

    def test_wrong_expected_root_exits_nonzero(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        code = main(["--run", str(run), "--subject", SUBJECT,
                     "--expected-root", "00" * 32])
        out = capsys.readouterr().out
        assert code == 1
        assert "--expected-root:     FAIL" in out

    def test_belief_index_out_of_range_exits_two(self, tmp_path, capsys):
        run = committed_run(tmp_path)
        code = main(["--run", str(run), "--subject", SUBJECT,
                     "--belief-index", "9"])
        assert code == 2


class TestDocumentedInvocation:
    def test_python_dash_m_invocation(self, tmp_path):
        run = committed_run(tmp_path)
        package_root = Path(rights_events.__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "rights_events.replay",
             "--run", str(run), "--subject", SUBJECT],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "REPLAY: OK" in result.stdout

    def test_python_dash_m_nonzero_on_tamper(self, tmp_path):
        run = committed_run(tmp_path)
        data = decode(run.read_bytes())
        belief = decode(data["belief_log"]["entries"][0])
        belief["unresolved_mass"] = Decimal("0.9")
        data["belief_log"]["entries"][0] = encode(belief)
        tampered = tmp_path / "tampered.ri"
        tampered.write_bytes(encode(data))
        package_root = Path(rights_events.__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "rights_events.replay",
             "--run", str(tampered), "--subject", SUBJECT],
            capture_output=True, text=True, cwd=str(package_root),
            timeout=120)
        assert result.returncode == 1
