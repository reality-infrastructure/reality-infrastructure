"""Tests for examples/ scripts.

Runs each example as a subprocess, asserts exit 0, and compares stdout
byte-for-byte against a frozen golden transcript.  Cross-process
determinism is verified by running with two different PYTHONHASHSEED
values and asserting identical output.

Golden files live at tests/golden/examples/<name>.out (binary treatment
via .gitattributes — git never rewrites line endings).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_GOLDEN_DIR = _ROOT / "tests" / "golden" / "examples"


def _run_example(script_name, seed=None):
    """Run an example script and return (returncode, stdout_bytes, stderr)."""
    script = _ROOT / "examples" / script_name
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ROOT)
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        env=env,
        cwd=str(_ROOT),
    )
    return result.returncode, result.stdout, result.stderr.decode()


class TestTitleDossier:
    """Tests for examples/title_dossier.py."""

    SCRIPT = "title_dossier.py"
    GOLDEN = _GOLDEN_DIR / "title_dossier.out"

    def test_exit_zero(self):
        """Example exits 0."""
        rc, _stdout, stderr = _run_example(self.SCRIPT)
        assert rc == 0, f"Exit code {rc}, stderr:\n{stderr}"

    def test_golden_transcript(self):
        """Stdout byte-matches frozen golden transcript."""
        _rc, stdout, stderr = _run_example(self.SCRIPT)
        golden = self.GOLDEN.read_bytes()
        assert stdout == golden, (
            f"Transcript differs from golden file.\n"
            f"Golden length: {len(golden)}, actual length: {len(stdout)}\n"
            f"stderr:\n{stderr}"
        )

    def test_cross_process_determinism(self):
        """Identical output across two PYTHONHASHSEED values."""
        rc1, out1, err1 = _run_example(self.SCRIPT, seed=1)
        rc2, out2, err2 = _run_example(self.SCRIPT, seed=99999)
        assert rc1 == 0, f"seed=1 exit {rc1}: {err1}"
        assert rc2 == 0, f"seed=99999 exit {rc2}: {err2}"
        assert out1 == out2, "Cross-process stdout bytes differ"

    def test_transcript_contains_exclusion(self):
        """Transcript cites rule id + version for excluded record."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "freshness_check v1" in text
        assert "EXCLUDED" in text
        assert "rule_verdict_false" in text

    def test_transcript_contains_provenance_class_size_2(self):
        """Transcript shows a provenance class with 2 members (brokers)."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "data_broker_alpha, data_broker_beta" in text

    def test_transcript_contains_how_provenance_polynomial(self):
        """Transcript prints a how-provenance polynomial."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "data_broker_alpha*data_broker_beta" in text
        assert "HowProvenance(" in text

    def test_transcript_contains_conflict_gloss(self):
        """Transcript renders m(emptyset) with curative-work gloss."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "0.5600 [CONFLICT]" in text
        assert "curative" in text
        assert "quiet title action" in text

    def test_transcript_contains_foil_illustration(self):
        """Transcript contains foil ILLUSTRATION numbers."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "ILLUSTRATION" in text
        assert "60.00%" in text
        assert "50.00%" in text
        assert "10.00%" in text

    def test_transcript_contains_counterfactual_flip(self):
        """Transcript shows counterfactual belief change."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "deed removed" in text
        assert "0.4200 [CONFLICT]" in text
        assert "0.2800" in text

    def test_transcript_contains_replay_attestation(self):
        """Transcript contains Merkle root and byte-identical replay."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "Merkle root:" in text
        assert "byte-identical replay: OK" in text

    def test_transcript_contains_disclaimer(self):
        """Transcript contains fictional disclaimer."""
        _rc, stdout, _err = _run_example(self.SCRIPT)
        text = stdout.decode()
        assert "DISCLAIMER" in text
        assert "fictional" in text
