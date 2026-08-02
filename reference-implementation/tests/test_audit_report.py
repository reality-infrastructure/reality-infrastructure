"""M-RI-14: golden report test — the runner over a frozen synthetic fixture must
be byte-identical to the checked-in goldens, under two hash seeds (the
test_pilot.py determinism convention). No network; subprocess only."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "audit_mini"
GOLDEN = ROOT / "tests" / "golden" / "audit"
OUTPUTS = ["discrepancy_table.csv", "discrepancy_table.json",
           "audit-report-client-DO-NOT-SEND-PROSPECTS.md"]


@pytest.mark.parametrize("seed", ["0", "1"])
def test_runner_matches_golden_bytes(tmp_path, seed):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    proc = subprocess.run(
        [sys.executable, "-m", "audit.run_audit",
         "--snapdir", str(FIXTURE), "--outdir", str(tmp_path)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for name in OUTPUTS:
        got = (tmp_path / name).read_bytes()
        want = (GOLDEN / name).read_bytes()
        assert got == want, f"{name} deviates from golden (seed {seed})"


def test_golden_report_carries_banner_and_caveat():
    text = (GOLDEN / OUTPUTS[2]).read_text(encoding="utf-8")
    assert "CLIENT DELIVERABLE — NOT FOR PROSPECT USE" in text
    assert "no machine-readable record found in the queried datasets" in text
    assert "COOK COUNTY LAND BANK AUTH" in text  # near-miss surfaced verbatim
