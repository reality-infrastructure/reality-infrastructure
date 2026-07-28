"""Tests for pilot/dolton_dossier.py (M-RI-11) and
pilot/dolton_dossier_typed.py (M-RI-13).

Runs the dossier as a subprocess over the frozen snapshots in
pilot/snapshots/ (no network anywhere), asserts exit 0, compares stdout
byte-for-byte against the frozen golden transcript, and verifies
cross-process determinism under two PYTHONHASHSEED values.

Hand-check assertions (amendment A3, frozen at observation-mapping
approval 2026-07-27). Hand computation, cautious rule (pointwise min of
conjunctive weights; for two disjoint simple support functions this
equals the conjunctive rule):

  sslbda_disposition -- O3 (CRM: conveyed 0.5/Omega 0.5),
                        O4 (deed: not_conveyed 0.8/Omega 0.2):
    weights: w({conveyed}) = 0.5, w({not_conveyed}) = 0.2
    commonalities: Q({conveyed}) = 0.2, Q({not_conveyed}) = 0.5,
                   Q(Omega) = 0.1
    masses: m(Omega) = 0.1
            m({conveyed}) = 0.2 - 0.1 = 0.10
            m({not_conveyed}) = 0.5 - 0.1 = 0.40
            m(emptyset) = 1 - 0.2 - 0.5 + 0.1 = 0.40

  current_owner -- O1 (deed: CSMA BLT LLC 0.8/Omega 0.2),
                   O2 (assessor: FIRSTKEY HOMES 0.6/Omega 0.4):
    weights: w({CSMA}) = 0.2, w({FIRSTKEY}) = 0.4
    commonalities: Q({CSMA}) = 0.4, Q({FIRSTKEY}) = 0.2, Q(Omega) = 0.08
    masses: m(Omega) = 0.08
            m({CSMA BLT LLC}) = 0.4 - 0.08 = 0.32
            m({FIRSTKEY HOMES}) = 0.2 - 0.08 = 0.12
            m(emptyset) = 1 - 0.4 - 0.2 + 0.08 = 0.48

  counterfactual (remove O3): only O4 remains:
    m({not_conveyed}) = 0.8, m(Omega) = 0.2, m(emptyset) = 0.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_GOLDEN = _ROOT / "tests" / "golden" / "pilot" / "dolton_dossier.out"


def _run_dossier(seed=None):
    """Run the pilot dossier and return (returncode, stdout_bytes, stderr)."""
    script = _ROOT / "pilot" / "dolton_dossier.py"
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


class TestDoltonDossier:
    """Tests for pilot/dolton_dossier.py over frozen snapshots."""

    def test_exit_zero(self):
        """Dossier exits 0 (inline A3/A4 assertions all pass)."""
        rc, _stdout, stderr = _run_dossier()
        assert rc == 0, f"Exit code {rc}, stderr:\n{stderr}"

    def test_golden_transcript(self):
        """Stdout byte-matches frozen golden transcript."""
        _rc, stdout, stderr = _run_dossier()
        golden = _GOLDEN.read_bytes()
        assert stdout == golden, (
            f"Transcript differs from golden file.\n"
            f"Golden length: {len(golden)}, actual length: {len(stdout)}\n"
            f"stderr:\n{stderr}"
        )

    def test_cross_process_determinism(self):
        """Identical output across two PYTHONHASHSEED values."""
        rc1, out1, err1 = _run_dossier(seed=1)
        rc2, out2, err2 = _run_dossier(seed=99999)
        assert rc1 == 0, f"seed=1 exit {rc1}: {err1}"
        assert rc2 == 0, f"seed=99999 exit {rc2}: {err2}"
        assert out1 == out2, "Cross-process stdout bytes differ"

    # -- A3 hand-check assertions (exact frozen values) -----------------

    def test_sslbda_disposition_masses(self):
        """sslbda_disposition: emptyset 0.40, not_conveyed 0.40,
        conveyed 0.10, Omega 0.10."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        section = text.split("SECTION 5")[1].split("SECTION 6")[0]
        section = re.sub(r" +", " ", section.split(
            "Proposition: sslbda_disposition")[1])
        assert "m(emptyset) = 0.4000 [CONFLICT]" in section
        assert "m({not_conveyed}) = 0.4000" in section
        assert "m({conveyed}) = 0.1000" in section
        assert "m({conveyed,not_conveyed}) = 0.1000" in section

    def test_current_owner_masses(self):
        """current_owner: emptyset 0.48, CSMA 0.32, FIRSTKEY 0.12,
        Omega 0.08."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        section = text.split("SECTION 5")[1].split("SECTION 6")[0]
        section = re.sub(r" +", " ", section.split(
            "Proposition: current_owner")[1].split(
            "Proposition: sslbda_disposition")[0])
        assert "m(emptyset) = 0.4800 [CONFLICT]" in section
        assert "m({CSMA BLT LLC}) = 0.3200" in section
        assert "m({FIRSTKEY HOMES}) = 0.1200" in section
        assert "m({CSMA BLT LLC,FIRSTKEY HOMES}) = 0.0800" in section

    def test_counterfactual_masses(self):
        """Counterfactual (remove CRM obs): not_conveyed 0.8, Omega 0.2."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        section = re.sub(r" +", " ", text.split(
            "After (CRM observation removed):")[1].split("SECTION 8")[0])
        assert "m({not_conveyed}) = 0.8000" in section
        assert "m({conveyed,not_conveyed}) = 0.2000" in section
        assert "m(emptyset) = 0.0000" in section

    # -- M-RI-11 acceptance-criteria transcript content -----------------

    def test_intake_three_real_sources(self):
        """Evidence intake covers >= 3 real sources with records."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "ccao_parcel_sales" in text
        assert "cc_assessor" in text
        assert "sslbda_crm" in text
        assert "from 3 real sources with records" in text

    def test_mass_table_verbatim(self):
        """Pre-registered mass table printed and cited."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "pilot/mass_assignments.md" in text
        assert "Recorded deed / sale record   0.8 focal / 0.2 Omega" in text
        assert "Assessor taxpayer-of-record   0.6 focal / 0.4 Omega" in text
        assert "CRM entry (SSLBDA)            0.5 focal / 0.5 Omega" in text

    def test_conflict_gloss_names_records(self):
        """m(emptyset) > 0 rendered with curative gloss naming the
        conflicting records (deed doc number and CRM feature)."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "[CONFLICT]" in text
        assert "curative" in text
        assert "1717247010" in text
        assert "feature 258" in text

    def test_counterfactual_gloss(self):
        """Counterfactual framed as 'if the CRM entry were corrected'."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "if the CRM entry were corrected" in text

    def test_replay_attestation(self):
        """Merkle root printed and replay byte-identical."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "Merkle root:" in text
        assert "byte-identical replay: OK" in text

    def test_methodology_note(self):
        """Methodology note: attestation model, mass-table citation,
        retrieval-dates reference, R3 tax framing, A2 inference."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "SECTION 9: METHODOLOGY NOTE" in text
        assert "signs on each" in text
        assert "pilot/MANIFEST.md" in text
        assert ("no machine-readable tax record found in the"
                in text)
        assert "tax-clear" in text
        assert "INFERENCE (printed per amendment A2)" in text

    def test_disclaimer(self):
        """Real-records disclaimer replaces the fictional one (g)."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "Informational analysis of public records" in text
        assert "NOT a title opinion" in text
        assert "fictional" not in text

    def test_frame_and_alias_printing(self):
        """Full 10-entity alias table and 2-entity frame both print (R6)."""
        _rc, stdout, _err = _run_dossier()
        text = stdout.decode()
        assert "Alias-resolved entities (10):" in text
        assert ("current_owner frame (2 entities): CSMA BLT LLC,"
                " FIRSTKEY HOMES" in text)
        assert "RICHARD  THORTON" in text  # raw, two spaces, verbatim
        assert "ruling R6" in text


# ---------------------------------------------------------------------------
# M-RI-13: EP-typed re-run (pilot/dolton_dossier_typed.py)
# ---------------------------------------------------------------------------

_GOLDEN_TYPED = _ROOT / "tests" / "golden" / "pilot" / "dolton_dossier_typed.out"

# R2 drift tripwire: the M-RI-11 golden is frozen; ANY byte change is the
# drift branch of the pre-registered replay invariant
# (pilot/ep_typing_preregistration.md section 3) regardless of cause.
_M_RI_11_GOLDEN_SHA256 = (
    "6ece101e4d96c2d81ee61b816597f6025a0644f44e49320e635cc664a32f93a2")


def _run_typed_dossier(seed=None):
    """Run the typed dossier and return (returncode, stdout_bytes, stderr)."""
    script = _ROOT / "pilot" / "dolton_dossier_typed.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ROOT) + os.pathsep + str(_ROOT / "pilot")
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        env=env,
        cwd=str(_ROOT),
    )
    return result.returncode, result.stdout, result.stderr.decode()


class TestDoltonDossierTyped:
    """Tests for the M-RI-13 EP-typed re-run over the same frozen snapshots."""

    def test_exit_zero(self):
        """Typed dossier exits 0 (all pre-registered asserts pass in-process:
        baseline masses, belief bytes typed==untyped, justification types ==
        pre-registered map, typed replay byte-identical, untyped rebuild
        root == frozen M-RI-11 root)."""
        rc, _stdout, stderr = _run_typed_dossier()
        assert rc == 0, f"Exit code {rc}, stderr:\n{stderr}"

    def test_golden_transcript(self):
        """Stdout byte-matches the NEW typed golden (R2: own golden path)."""
        _rc, stdout, stderr = _run_typed_dossier()
        golden = _GOLDEN_TYPED.read_bytes()
        assert stdout == golden, (
            f"Typed transcript differs from golden file.\n"
            f"Golden length: {len(golden)}, actual length: {len(stdout)}\n"
            f"stderr:\n{stderr}"
        )

    def test_cross_process_determinism(self):
        """Identical output across two PYTHONHASHSEED values."""
        rc1, out1, err1 = _run_typed_dossier(seed=1)
        rc2, out2, err2 = _run_typed_dossier(seed=99999)
        assert rc1 == 0, f"seed=1 exit {rc1}: {err1}"
        assert rc2 == 0, f"seed=99999 exit {rc2}: {err2}"
        assert out1 == out2, "Cross-process stdout bytes differ"

    def test_m_ri_11_golden_untouched(self):
        """R2 drift tripwire: the M-RI-11 golden's bytes are unchanged."""
        import hashlib
        actual = hashlib.sha256(_GOLDEN.read_bytes()).hexdigest()
        assert actual == _M_RI_11_GOLDEN_SHA256, (
            "M-RI-11 golden bytes changed -- pre-registered DRIFT branch, "
            f"halt: {actual}")

    def test_types_printed_per_preregistered_map(self):
        """Every claim prints its pre-registered set-valued type."""
        _rc, stdout, _err = _run_typed_dossier()
        text = stdout.decode()
        intake = text.split("SECTION 1")[1].split("SECTION 2")[0]
        o1 = intake.split("obs_o1_ccao_owner")[1].split("obs_o2")[0]
        o2 = intake.split("obs_o2_assessor_owner")[1].split("obs_o3")[0]
        o3 = intake.split("obs_o3_crm_disposition")[1].split("obs_o4")[0]
        o4 = intake.split("obs_o4_ccao_disposition")[1]
        assert "uncertaintyType: [measured]" in o1
        assert "uncertaintyType: [measured]" in o2
        assert "uncertaintyType: [asserted-by-interested-party]" in o3
        assert "uncertaintyType: [inferred-from-proxy, measured]" in o4

    def test_o4_prints_both_terms_with_proxy_explanation(self):
        """GO ruling R1: O4 prints both terms with the A2 inference sentence
        as the proxy explanation."""
        _rc, stdout, _err = _run_typed_dossier()
        text = stdout.decode()
        assert "[inferred-from-proxy, measured]" in text
        assert "PROXY EXPLANATION (A2 inference):" in text
        assert ("names grantor RICHARD THORTON,"
                " not SSLBDA" in text)

    def test_baseline_masses_unchanged(self):
        """Typed-run masses equal the M-RI-11 baseline (pre-registration 2)."""
        _rc, stdout, _err = _run_typed_dossier()
        text = re.sub(r" +", " ", stdout.decode())
        assert "m(emptyset) = 0.4800 [CONFLICT]" in text
        assert "m({CSMA BLT LLC}) = 0.3200" in text
        assert "m({FIRSTKEY HOMES}) = 0.1200" in text
        assert "m({CSMA BLT LLC,FIRSTKEY HOMES}) = 0.0800" in text
        assert "m(emptyset) = 0.4000 [CONFLICT]" in text
        assert "m({not_conveyed}) = 0.4000" in text
        assert "m({conveyed}) = 0.1000" in text
        assert "m({conveyed,not_conveyed}) = 0.1000" in text

    def test_belief_bytes_identical_typed_vs_untyped(self):
        """Typing enriched justification only (pre-registration 2)."""
        _rc, stdout, _err = _run_typed_dossier()
        text = stdout.decode()
        assert ("Belief bytes, typed vs untyped pipeline: IDENTICAL"
                in text)

    def test_epistemic_justification_reads_from_ri_core(self):
        """Justification section states types flow through project()."""
        _rc, stdout, _err = _run_typed_dossier()
        text = stdout.decode()
        assert "SECTION 4: EPISTEMIC JUSTIFICATION" in text
        assert "read back from the ri_core justification" in text
        assert "DISCOUNTED as an interested-party assertion" in text
        assert "SELF-CONTRADICTS" in text

    def test_replay_and_hash_classification(self):
        """Typed replay OK; untyped rebuild reproduces the frozen M-RI-11
        root (schema-vs-drift classification, pre-registration 3)."""
        _rc, stdout, _err = _run_typed_dossier()
        text = stdout.decode()
        assert "byte-identical replay (typed log): OK" in text
        assert "Untyped rebuild == M-RI-11 root: MATCH" in text
        assert ("68b45d8b431f84a3fddf8a9ff0dbe0f9a20de75ce537d1161ea19a"
                "8fa22a39fa" in text)
        assert "SCHEMA change, not" in text
