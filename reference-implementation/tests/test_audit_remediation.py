"""M-RI-16: the remediated run — cause-traced delta, banners, contested set.

The remediation's soundness claims, pinned: every transition vs the M-RI-15
attested baseline is reproduced by at least one counterfactual (attestation-only
/ amendment-only); the shipped artifacts match the live machine; the two
Recorder-bannered verdicts are flagged and excluded from exhibits; the contested
manifest is exactly the CONTRADICTED ∪ AMBIGUOUS of the shipped run.
"""
import hashlib
import json
from pathlib import Path

import pytest

from audit import engine, rules, rerun_remediated
from audit.attestation import events as att

AUDIT_DIR = Path(__file__).parent.parent / "audit"
OUT = AUDIT_DIR / "out" / "attested-remediated-2026-08-02"


@pytest.fixture(scope="module")
def run():
    events = att.load_events()
    snaps = engine.load_snapshots(AUDIT_DIR / "snapshots")
    baseline_path = (AUDIT_DIR / "out" / "attested-2026-08-02"
                     / "discrepancy_table.json")
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes)["verdicts"]
    # meta must match main()'s exactly — it is embedded in the shipped artifacts
    meta = {
        "attestations_sha256": hashlib.sha256(
            att.DEFAULT_PATH.read_bytes()).hexdigest(),
        "baseline": str(baseline_path.as_posix()),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "snapdir": str((AUDIT_DIR / "snapshots").as_posix()),
    }
    return baseline, rerun_remediated.build_all(snaps, baseline, events, meta)


def test_every_transition_reproduced_by_a_counterfactual(run):
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    assert delta, "remediation changed nothing — expected transitions"
    assert labels and all(lab in ("attestation", "amendment", "both")
                          for lab in labels.values()), (
        "UNTRACED transition: the comparison is not sound")
    assert set(labels) == {d["pin"] for d in delta}


def test_counterfactual_labels_sum_cleanly(run):
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    counts = {c: sum(1 for x in labels.values() if x == c)
              for c in ("attestation", "amendment", "both")}
    assert sum(counts.values()) == len(delta)


def test_shipped_artifacts_match_live_machine(run):
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    for name in ("discrepancy_table.json", "delta_table.json",
                 "contested-set-manifest.json"):
        assert (OUT / name).read_text(encoding="utf-8") == outputs[name], (
            f"{name} on disk drifted from the live machine")


def test_known_answer_survives_remediation(run):
    baseline, (full, *_ ) = run
    ka = [v for v in full if v["pin14"] == rules.KNOWN_ANSWER_PIN14]
    assert ka and ka[0]["verdict"] == rules.KNOWN_ANSWER_VERDICT


def test_bannered_verdicts_flagged_and_excluded(run):
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    manifest = json.loads(outputs["contested-set-manifest.json"])
    flagged = {p["pin"] for p in manifest["parcels"] if p["recorder_banner"]}
    assert flagged == set(rerun_remediated.BANNERED_PINS)
    rescore = (OUT / "exhibit-rescore.md").read_text(encoding="utf-8")
    for pin in rerun_remediated.BANNERED_PINS:
        assert f"| {pin} | PASS | FAIL" in rescore
        assert "EXCLUDED BY CONSTRUCTION" in rescore


def test_contested_manifest_is_exactly_the_contested_set(run):
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    manifest = json.loads(outputs["contested-set-manifest.json"])
    expected = {v["pin"] for v in full
                if v["verdict"] in (rules.CONTRADICTED, rules.AMBIGUOUS)}
    assert {p["pin"] for p in manifest["parcels"]} == expected
    assert manifest["run_sha256"] == run_sha
    assert (manifest["counts"]["CONTRADICTED"]
            + manifest["counts"]["AMBIGUOUS"]) == len(expected)


def test_f1_cohort_disposition_matches_the_finding(run):
    """The F1 cohorts land where the gate predicted: 16 CONTRADICTED ->
    AMBIGUOUS; 92 UNSUPPORTED -> 86 SUPPORTED + 6 AMBIGUOUS."""
    baseline, (full, cf_att, cf_amd, labels, delta, outputs, run_sha) = run
    base_by_pin = {v["pin"]: v for v in baseline}
    vc = [d for d in delta if d["verdict_changed"]]
    from_c = [d for d in vc
              if base_by_pin[d["pin"]]["verdict"] == rules.CONTRADICTED]
    from_u = [d for d in vc
              if base_by_pin[d["pin"]]["verdict"]
              == rules.UNSUPPORTED_NO_RECORD]
    assert len(from_c) == 16
    assert all(d["to_verdict"] == rules.AMBIGUOUS for d in from_c)
    assert len(from_u) == 92
    assert sum(1 for d in from_u
               if d["to_verdict"] == rules.SUPPORTED) == 86
    assert sum(1 for d in from_u
               if d["to_verdict"] == rules.AMBIGUOUS) == 6
