# Conformance Map — C1–C9

Criterion-to-test-name evidence table per CONFORMANCE.md.

| Criterion | Name | Test(s) | Notes |
|-----------|------|---------|-------|
| C1 | Byte-identical replay | `test_conformance.py::TestC1ByteIdenticalReplay::test_c1_replay_byte_identical` | v0.1 scope: single implementation, cross-process byte-identity as proxy |
| C2 | Append-only | `test_conformance.py::TestC2AppendOnly::test_c2_consistency_across_appends` | Consistency proofs for all (old, new) size pairs |
| C3 | Sybil-calibration | `test_conformance.py::TestC3SybilCalibration::test_c3_sybil_flat`; `test_ablation.py::TestScenarioAFullStack` (4 tests); `test_ablation.py::TestScenarioBFullStack` (2 tests); `test_ablation.py::TestSybilRingVsIndependent` (2 tests); `test_ablation.py::TestStage2Falsification::test_stage2_falsification_negative` | Full ablation battery with foils F1/F2/F3 |
| C4 | Contradiction first-class | `test_conformance.py::TestC4ContradictionFirstClass::test_c4_contradiction` | m(emptyset) > 0 for conflicting sources |
| C5 | Determinism | `test_conformance.py::TestC5Determinism::test_c5_cross_process` | Two subprocesses, different PYTHONHASHSEED |
| C6 | No fabrication | `test_conformance.py::TestC6NoFabrication::test_c6_provenance_in_log` | Every justification observation traces to log |
| C7 | Rules are evidence | `test_conformance.py::TestC7RulesAreEvidence::test_c7_rule_in_log`; `test_conformance.py::TestC7RulesAreEvidence::test_c7_counterfactual_rule` | rule_version logged; counterfactual substitution |
| C8 | Algebra (CAI) | `test_conformance.py::TestC8Algebra::test_c8_commutative`; `test_conformance.py::TestC8Algebra::test_c8_associative`; `test_conformance.py::TestC8Algebra::test_c8_idempotent` | Explicit triples; hypothesis-based tests permitted but not yet added |
| C9 | Representation | `test_conformance.py::TestC9Representation::test_c9_not_scalar`; `test_conformance.py::TestC9Representation::test_c9_dogmatic_rejected` | Structured dict with weights; m(Omega)=0 rejected |
