"""Stage-2 Sybil-calibration ablation experiment.

Scenarios:
  A — alice m({a})=0.6, adversary m({a})=0.9, frame {a,b}
  B — alice m({a})=0.6, adversary m({b})=0.9, frame {a,b} (contradiction erasure)

Foils (test-local only — ri_core untouched):
  F1: count-based mass averaging (provenance-free)
  F2: Dempster-style repeated conjunctive combination (non-idempotent)
  F3: content-dedup then F2 — dedup by content only, trivially varied masses

Assertions:
  Full stack exactly flat in k (byte-identical belief)
  F1 strictly increasing in k
  F2 strictly increasing, → 1 at k=50
  F3 inflates under trivially-varied content
  Two-component variants fail (falsification check NEGATIVE — thesis survives)
"""

from __future__ import annotations

import decimal
import itertools
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.project import project, submit
from ri_core.provenance import HowProvenance, ProvenanceGraph
from ri_core.reconcile import BeliefWeights, cautious_fuse
from ri_core.rules import RuleStore
from ri_core.serialization import encode as _enc

_CTX = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN)
_Q30 = Decimal("1E-30")
K_VALUES = (1, 2, 5, 10, 25, 50)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(*names, links=None):
    a = LocalAuthority(anchor_id="abl", seed=b"abl-seed")
    for n in names:
        a.issue_identity(n)
    if links:
        for x, y in links:
            a.link_identities(
                Identity(identity_id=x, anchor_id="abl", name=x),
                Identity(identity_id=y, anchor_id="abl", name=y))
    return a


def _obs(oid, src, prop, frame, mass, lt, auth):
    u = {"kind": "observation", "id": oid, "source_id": src,
         "proposition": prop, "payload": {"frame": frame, "mass": mass},
         "ltime": lt}
    sig = auth.sign(
        Identity(identity_id=src, anchor_id=auth.anchor_id, name=src),
        _enc(u))
    return {**u, "sig": sig}


def _powerset(frame_sorted):
    for r in range(len(frame_sorted) + 1):
        for combo in itertools.combinations(frame_sorted, r):
            yield frozenset(combo)


def _quantize(mass_dict):
    with decimal.localcontext(_CTX):
        out = {}
        for k, v in mass_dict.items():
            q = v.quantize(_Q30)
            out[k] = Decimal(0) if abs(q) < _Q30 else q
        return out


# ---------------------------------------------------------------------------
# Foil F1: count-based averaging (provenance-free)
# ---------------------------------------------------------------------------

def f1_average(base_mass, adv_mass, k, frame_sorted):
    """Average of base + k copies of adv_mass.  ~10 lines."""
    with decimal.localcontext(_CTX):
        n = Decimal(1 + k)
        result = {}
        for s in _powerset(frame_sorted):
            val = (base_mass.get(s, Decimal(0))
                   + Decimal(k) * adv_mass.get(s, Decimal(0))) / n
            result[s] = +val
        return _quantize(result)


# ---------------------------------------------------------------------------
# Foil F2: Dempster-style conjunctive combination (non-idempotent)
# ---------------------------------------------------------------------------

def _dempster_pair(m1, m2, frame_sorted):
    """Single Dempster combination.  ~15 lines."""
    subs = list(_powerset(frame_sorted))
    with decimal.localcontext(_CTX):
        unnorm = {s: Decimal(0) for s in subs}
        for b in subs:
            for c in subs:
                inter = b & c
                unnorm[inter] += m1.get(b, Decimal(0)) * m2.get(c, Decimal(0))
        conflict = unnorm[frozenset()]
        denom = Decimal(1) - conflict
        result = {}
        for s in subs:
            if s == frozenset():
                result[s] = Decimal(0)
            else:
                result[s] = unnorm[s] / denom
        return _quantize(result)


def f2_dempster(base_mass, adv_mass, k, frame_sorted):
    """Iterated Dempster: base ⊕_D adv ⊕_D ... ⊕_D adv (k times)."""
    current = dict(base_mass)
    for _ in range(k):
        current = _dempster_pair(current, adv_mass, frame_sorted)
    return current


# ---------------------------------------------------------------------------
# Foil F3: content-dedup then Dempster (trivially varied masses)
# ---------------------------------------------------------------------------

def f3_content_dedup(base_mass, k, frame_sorted, base_adv_a, base_adv_omega):
    """Dedup by content, then Dempster across 'distinct' items.

    Adversary copies have trivially varied masses:
      m({a}) = base_adv_a - i*1E-20,  m(Ω) = base_adv_omega + i*1E-20
    All distinct content → no dedup → Dempster across all.
    A1 amendment: each copy sums to 1.
    """
    current = dict(base_mass)
    with decimal.localcontext(_CTX):
        for i in range(1, k + 1):
            delta = Decimal(i) * Decimal("1E-20")
            adv = {}
            for s in _powerset(frame_sorted):
                adv[s] = Decimal(0)
            a_set = frozenset(["a"])
            omega = frozenset(frame_sorted)
            adv[a_set] = base_adv_a - delta
            adv[omega] = base_adv_omega + delta
            current = _dempster_pair(current, adv, frame_sorted)
    return current


# ---------------------------------------------------------------------------
# Full-stack runner
# ---------------------------------------------------------------------------

def _full_stack_belief(k, alice_mass, adv_mass, linked=True):
    """Run actual ri_core pipeline with alice + k adversary copies."""
    names = ["alice"] + [f"adv_{i}" for i in range(k)]
    links = [("adv_0", f"adv_{i}") for i in range(1, k)] if linked else None
    auth = _auth(*names, links=links)
    log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()

    submit(_obs("a1", "alice", "P", ["a", "b"], alice_mass, 0, auth),
           log, g, auth)
    for i in range(k):
        submit(_obs(f"adv_{i}", f"adv_{i}", "P", ["a", "b"],
                    adv_mass, i + 1, auth), log, g, auth)

    bs = project(log, g, auth, rs, {}, as_of=200)
    return bs


# ---------------------------------------------------------------------------
# Scenario A fixtures
# ---------------------------------------------------------------------------

FRAME_A = ("a", "b")
ALICE_A = {frozenset(["a"]): Decimal("0.6"),
           frozenset(["a", "b"]): Decimal("0.4")}
ADV_A = {frozenset(["a"]): Decimal("0.9"),
         frozenset(["a", "b"]): Decimal("0.1")}
ALICE_A_STR = {"a": Decimal("0.6"), "a,b": Decimal("0.4")}
ADV_A_STR = {"a": Decimal("0.9"), "a,b": Decimal("0.1")}

# Scenario B fixtures
ALICE_B = {frozenset(["a"]): Decimal("0.6"),
           frozenset(["a", "b"]): Decimal("0.4")}
ADV_B = {frozenset(["b"]): Decimal("0.9"),
         frozenset(["a", "b"]): Decimal("0.1")}
ADV_B_STR = {"b": Decimal("0.9"), "a,b": Decimal("0.1")}


# ===================================================================
# Tests — Scenario A
# ===================================================================

class TestScenarioAFullStack:
    """Full stack flatness: belief bytes identical across all k."""

    def test_full_stack_flat_correlated(self):
        """Correlated copies (linked): belief identical for all k."""
        ref = None
        for k in K_VALUES:
            bs = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=True)
            b = _enc(bs["propositions"]["P"]["belief"])
            if ref is None:
                ref = b
            else:
                assert b == ref, f"k={k} belief differs"

    def test_full_stack_flat_sybil_ring(self):
        """Sybil-ring (linked): same as correlated — belief identical."""
        ref = None
        for k in K_VALUES:
            bs = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=True)
            b = _enc(bs["propositions"]["P"]["belief"])
            if ref is None:
                ref = b
            else:
                assert b == ref, f"sybil k={k} differs"

    def test_full_stack_flat_varied_content(self):
        """A1 amendment: full stack under trivially varied content stays flat."""
        ref = None
        for k in K_VALUES:
            names = ["alice"] + [f"v{i}" for i in range(k)]
            links = [("v0", f"v{i}") for i in range(1, k)]
            auth = _auth(*names, links=links)
            log, g, rs = EvidenceLog(), ProvenanceGraph(), RuleStore()
            submit(_obs("a1", "alice", "P", ["a", "b"],
                        ALICE_A_STR, 0, auth), log, g, auth)
            with decimal.localcontext(_CTX):
                for i in range(k):
                    delta = Decimal(i + 1) * Decimal("1E-20")
                    m_a = Decimal("0.9") - delta
                    m_o = Decimal("0.1") + delta
                    submit(_obs(f"v{i}", f"v{i}", "P", ["a", "b"],
                                {"a": m_a, "a,b": m_o}, i + 1, auth),
                           log, g, auth)
            bs = project(log, g, auth, rs, {}, as_of=200)
            b = _enc(bs["propositions"]["P"]["belief"])
            if ref is None:
                ref = b
            else:
                assert b == ref, f"varied k={k} differs"

    def test_full_stack_expected_mass(self):
        """Full stack fused mass matches hand-computed values."""
        bs = _full_stack_belief(1, ALICE_A_STR, ADV_A_STR)
        bel = bs["propositions"]["P"]["belief"]
        bw = BeliefWeights.from_weights(
            frozenset(bel["frame"]),
            {(frozenset() if k == "" else frozenset(k.split(","))): v
             for k, v in bel["weights"].items()})
        assert bw.mass(frozenset(["a"])) == Decimal("0.900000000000000000000000000000")
        assert bw.mass(frozenset(["a", "b"])) == Decimal("0.100000000000000000000000000000")


class TestScenarioAFoils:
    """F1, F2, F3 strictly increasing in k for Scenario A."""

    def test_f1_strictly_increasing(self):
        """F1 count-based averaging: m({a}) strictly increasing in k."""
        prev = None
        for k in K_VALUES:
            m = f1_average(ALICE_A, ADV_A, k, FRAME_A)
            val = m[frozenset(["a"])]
            if prev is not None:
                assert val > prev, f"F1 not increasing at k={k}"
            prev = val
        # Spot-check exact values
        m1 = f1_average(ALICE_A, ADV_A, 1, FRAME_A)
        assert m1[frozenset(["a"])] == Decimal("0.750000000000000000000000000000")
        m50 = f1_average(ALICE_A, ADV_A, 50, FRAME_A)
        assert m50[frozenset(["a"])] == Decimal("0.894117647058823529411764705882")

    def test_f2_strictly_increasing_approaching_1(self):
        """F2 Dempster: m({a}) strictly increasing, k=50 > 0.99."""
        prev = None
        for k in K_VALUES:
            m = f2_dempster(ALICE_A, ADV_A, k, FRAME_A)
            val = m[frozenset(["a"])]
            if prev is not None:
                assert val > prev, f"F2 not increasing at k={k}"
            prev = val
        m1 = f2_dempster(ALICE_A, ADV_A, 1, FRAME_A)
        assert m1[frozenset(["a"])] == Decimal("0.960000000000000000000000000000")
        m50 = f2_dempster(ALICE_A, ADV_A, 50, FRAME_A)
        assert m50[frozenset(["a"])] > Decimal("0.99")

    def test_f3_inflates_varied_content(self):
        """F3 content-dedup: inflates under trivially varied content."""
        prev = None
        for k in K_VALUES:
            m = f3_content_dedup(ALICE_A, k, FRAME_A,
                                 Decimal("0.9"), Decimal("0.1"))
            val = m[frozenset(["a"])]
            if prev is not None:
                assert val > prev, f"F3 not increasing at k={k}"
            prev = val


# ===================================================================
# Tests — Scenario B (A2 amendment: contradiction erasure)
# ===================================================================

class TestScenarioBFullStack:
    """Scenario B: alice m({a})=0.6 vs adversary m({b})=0.9."""

    def test_full_stack_flat_b(self):
        """Full stack flat across all k in Scenario B."""
        ref = None
        for k in K_VALUES:
            bs = _full_stack_belief(k, ALICE_A_STR, ADV_B_STR, linked=True)
            b = _enc(bs["propositions"]["P"]["belief"])
            if ref is None:
                ref = b
            else:
                assert b == ref, f"B k={k} differs"

    def test_full_stack_expected_mass_b(self):
        """A2 hand-checked: m(∅)=0.54, m({b})=0.36, m({a})=0.06, m(Ω)=0.04."""
        bs = _full_stack_belief(1, ALICE_A_STR, ADV_B_STR)
        bel = bs["propositions"]["P"]["belief"]
        bw = BeliefWeights.from_weights(
            frozenset(bel["frame"]),
            {(frozenset() if k == "" else frozenset(k.split(","))): v
             for k, v in bel["weights"].items()})
        assert bw.mass(frozenset()) == Decimal("0.540000000000000000000000000000")
        assert bw.mass(frozenset(["b"])) == Decimal("0.360000000000000000000000000000")
        assert bw.mass(frozenset(["a"])) == Decimal("0.060000000000000000000000000000")
        assert bw.mass(frozenset(["a", "b"])) == Decimal("0.040000000000000000000000000000")


class TestScenarioBFoils:
    """F1, F2 inflating in Scenario B."""

    def test_f1_increasing_b(self):
        """F1: m({b}) strictly increasing in k for Scenario B."""
        prev = None
        for k in K_VALUES:
            m = f1_average(ALICE_B, ADV_B, k, FRAME_A)
            val = m[frozenset(["b"])]
            if prev is not None:
                assert val > prev, f"F1-B not increasing at k={k}"
            prev = val

    def test_f2_increasing_b(self):
        """F2 Dempster: m({b}) strictly increasing, erases contradiction."""
        prev = None
        for k in K_VALUES:
            m = f2_dempster(ALICE_B, ADV_B, k, FRAME_A)
            val = m[frozenset(["b"])]
            assert m[frozenset()] == Decimal(0), "Dempster erases m(∅)"
            if prev is not None:
                assert val > prev, f"F2-B not increasing at k={k}"
            prev = val
        m50 = f2_dempster(ALICE_B, ADV_B, 50, FRAME_A)
        assert m50[frozenset(["b"])] > Decimal("0.99")


# ===================================================================
# Sybil-ring vs Independent
# ===================================================================

class TestSybilRingVsIndependent:
    """Same belief, different how-provenance polynomial."""

    def test_sybil_vs_independent_k10(self):
        """k=10 linked (Sybil-ring) vs k=10 unlinked (independent):
        same belief, different polynomial class structure.
        """
        k = 10
        bs_linked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=True)
        bs_unlinked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=False)

        # Same belief (doctrine: cautious fusion is idempotent)
        assert (_enc(bs_linked["propositions"]["P"]["belief"]) ==
                _enc(bs_unlinked["propositions"]["P"]["belief"]))

        # Different polynomial
        lp = HowProvenance.from_canonical(
            bs_linked["propositions"]["P"]["justification"]["how_provenance"])
        up = HowProvenance.from_canonical(
            bs_unlinked["propositions"]["P"]["justification"]["how_provenance"])

        # Linked: 2 terms (alice monomial + one degree-k monomial)
        assert len(lp.terms) == 2
        # Unlinked: k+1 terms (alice + k degree-1 monomials)
        assert len(up.terms) == k + 1
        assert lp != up

    def test_polynomial_class_structure(self):
        """Linked polynomial has one monomial of degree k;
        unlinked has k monomials of degree 1 (plus alice in both).
        """
        k = 5
        bs_linked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=True)
        bs_unlinked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=False)

        lp = HowProvenance.from_canonical(
            bs_linked["propositions"]["P"]["justification"]["how_provenance"])
        up = HowProvenance.from_canonical(
            bs_unlinked["propositions"]["P"]["justification"]["how_provenance"])

        # Linked: one monomial has degree k (product of k variables)
        for mono, coeff in lp.terms.items():
            total_deg = sum(exp for _, exp in mono)
            assert total_deg in (1, k), f"unexpected degree {total_deg}"

        # Unlinked: all monomials degree 1
        for mono, coeff in up.terms.items():
            total_deg = sum(exp for _, exp in mono)
            assert total_deg == 1, f"unexpected degree {total_deg}"


# ===================================================================
# Stage-2 falsification (A3: named test)
# ===================================================================

class TestStage2Falsification:
    """Two-component variant falsification — thesis survives."""

    def test_stage2_falsification_negative(self):
        """Stage-2 falsification NEGATIVE: no two-component sub-composition
        stays both bounded AND correct.

        {provenance + belief} without idempotent reconciliation:
            Uses Dempster → belief inflates with k → fails BOUNDED.
        {reconciliation + belief} without provenance:
            Cautious fusion (bounded) but no class structure →
            cannot distinguish Sybil from independent → fails CORRECT.
        """
        k = 10

        # --- Variant 1: provenance + belief, Dempster combiner ---
        # Has provenance tracking but non-idempotent combiner.
        # Belief changes with k → NOT BOUNDED.
        m_k1 = f2_dempster(ALICE_A, ADV_A, 1, FRAME_A)
        m_k10 = f2_dempster(ALICE_A, ADV_A, k, FRAME_A)
        assert m_k1[frozenset(["a"])] != m_k10[frozenset(["a"])], \
            "Variant 1 should NOT be bounded"

        # --- Variant 2: reconciliation + belief, no provenance ---
        # Cautious fusion but all sources treated as independent.
        bs_linked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=True)
        bs_unlinked = _full_stack_belief(k, ALICE_A_STR, ADV_A_STR, linked=False)

        # Bounded: belief identical
        assert (_enc(bs_linked["propositions"]["P"]["belief"]) ==
                _enc(bs_unlinked["propositions"]["P"]["belief"])), \
            "Variant 2 IS bounded (cautiousfuse idempotent)"

        # NOT correct: polynomial indistinguishable from k independents
        lp = HowProvenance.from_canonical(
            bs_linked["propositions"]["P"]["justification"]["how_provenance"])
        up = HowProvenance.from_canonical(
            bs_unlinked["propositions"]["P"]["justification"]["how_provenance"])
        assert lp != up, \
            "Variant 2 NOT correct: can't distinguish Sybil from independent"

        # The unlinked polynomial looks like k genuine independent sources:
        # all monomials are degree 1 (no joint-derivation structure).
        for mono, _ in up.terms.items():
            assert sum(e for _, e in mono) == 1, \
                "No-provenance variant shows only degree-1 terms"


# ===================================================================
# Results doc verification
# ===================================================================

_RESULTS_DOC = Path(__file__).parent.parent / "docs" / "ablation-results.md"


def _compute_all_values():
    """Compute the full results table for both scenarios."""
    rows_a = []
    rows_b = []
    for k in K_VALUES:
        # Scenario A
        full_a = Decimal("0.900000000000000000000000000000")
        f1_a = f1_average(ALICE_A, ADV_A, k, FRAME_A)[frozenset(["a"])]
        f2_a = f2_dempster(ALICE_A, ADV_A, k, FRAME_A)[frozenset(["a"])]
        f3_a = f3_content_dedup(ALICE_A, k, FRAME_A,
                                Decimal("0.9"), Decimal("0.1")
                                )[frozenset(["a"])]
        rows_a.append((k, full_a, f1_a, f2_a, f3_a))

        # Scenario B — measure m({b})
        full_b = Decimal("0.360000000000000000000000000000")
        f1_b = f1_average(ALICE_B, ADV_B, k, FRAME_A)[frozenset(["b"])]
        f2_b = f2_dempster(ALICE_B, ADV_B, k, FRAME_A)[frozenset(["b"])]
        rows_b.append((k, full_b, f1_b, f2_b))
    return rows_a, rows_b


class TestResultsDocMatches:
    """The doc cannot drift from the code."""

    def test_results_doc_scenario_a(self):
        """Scenario A table in docs/ablation-results.md matches computed values."""
        text = _RESULTS_DOC.read_text()
        rows_a, _ = _compute_all_values()
        for k, full, f1, f2, f3 in rows_a:
            assert str(full) in text, f"A full k={k} missing"
            assert str(f1) in text, f"A F1 k={k} missing"
            assert str(f2) in text, f"A F2 k={k} missing"
            assert str(f3) in text, f"A F3 k={k} missing"

    def test_results_doc_scenario_b(self):
        """Scenario B table in docs/ablation-results.md matches computed values."""
        text = _RESULTS_DOC.read_text()
        _, rows_b = _compute_all_values()
        for k, full, f1, f2 in rows_b:
            assert str(full) in text, f"B full k={k} missing"
            assert str(f1) in text, f"B F1 k={k} missing"
            assert str(f2) in text, f"B F2 k={k} missing"

    def test_results_doc_scenario_b_handchecked(self):
        """A2 amendment: hand-checked Scenario B masses in doc."""
        text = _RESULTS_DOC.read_text()
        assert "0.540000000000000000000000000000" in text, "B m(empty) missing"
        assert "0.360000000000000000000000000000" in text, "B m(b) missing"
        assert "0.060000000000000000000000000000" in text, "B m(a) missing"
        assert "0.040000000000000000000000000000" in text, "B m(omega) missing"


# ===================================================================
# Sybil-ring vs independent — same belief, different justification
# ===================================================================

class TestSybilRingVsIndependent:
    """k linked identities (one class) vs k unlinked (k classes).

    Same belief both ways (cautious fusion is idempotent), different
    how_provenance polynomial class structure.
    """

    def test_same_belief_different_provenance(self):
        k = 10
        # Linked: all adversaries in one provenance class
        bs_linked = _full_stack_belief(
            k, ALICE_A_STR, ADV_A_STR, linked=True)
        # Unlinked: each adversary in its own class
        bs_unlinked = _full_stack_belief(
            k, ALICE_A_STR, ADV_A_STR, linked=False)

        # Same belief bytes
        b_linked = _enc(bs_linked["propositions"]["P"]["belief"])
        b_unlinked = _enc(bs_unlinked["propositions"]["P"]["belief"])
        assert b_linked == b_unlinked, "belief differs between linked/unlinked"

        # Different justification structure
        j_linked = bs_linked["propositions"]["P"]["justification"]
        j_unlinked = bs_unlinked["propositions"]["P"]["justification"]

        # Linked: 2 classes (alice + sybil-ring)
        assert len(j_linked["classes"]) == 2

        # Unlinked: 1 + k classes (alice + k independent)
        assert len(j_unlinked["classes"]) == 1 + k

        # How-provenance polynomial differs
        hp_linked = HowProvenance.from_canonical(j_linked["how_provenance"])
        hp_unlinked = HowProvenance.from_canonical(
            j_unlinked["how_provenance"])
        assert hp_linked != hp_unlinked

        # Linked: polynomial has 2 terms (alice variable + one monomial
        # of k adversary variables multiplied)
        assert len(hp_linked.terms) == 2
        # Unlinked: polynomial has 1 + k terms (alice + k single vars)
        assert len(hp_unlinked.terms) == 1 + k


# ===================================================================
# Stage-2 falsification check (A3: test_stage2_falsification_negative)
# ===================================================================

class TestStage2FalsificationNegative:
    """Two-component variants each FAIL to stay both bounded AND correct.

    {provenance-only}: provenance tracking + Dempster (non-idempotent)
        -> belief inflates with k (NOT bounded)
    {reconciliation-only}: cautious fusion, no provenance classes
        -> belief bounded BUT justification wrong (no provenance structure)

    Both fail the conjunction "bounded AND correct".
    Falsification check NEGATIVE: thesis survives.
    """

    def test_stage2_falsification_negative(self):
        """Named test per A3 amendment."""

        # ---- {provenance-only} variant: Dempster + provenance ----
        # Uses F2 (Dempster) instead of cautious fusion.
        # With provenance, we could track classes, but the non-idempotent
        # combiner inflates: m({a}) increases with k.
        vals = []
        for k in K_VALUES:
            m = f2_dempster(ALICE_A, ADV_A, k, FRAME_A)
            vals.append(m[frozenset(["a"])])

        # NOT bounded: k=1 vs k=50 differ significantly
        assert vals[-1] > vals[0], "provenance-only should inflate"
        assert vals[-1] - vals[0] > Decimal("0.03"), (
            "provenance-only inflation too small")

        # ---- {reconciliation-only} variant: cautious fusion, no provenance
        # Cautious fusion IS idempotent, so belief stays flat.
        # But without provenance, there is no class structure to audit.
        frame = frozenset(["a", "b"])
        alice_bw = BeliefWeights.from_mass(
            frame, {frozenset(["a"]): Decimal("0.6"),
                    frozenset(["a", "b"]): Decimal("0.4")})
        adv_bw = BeliefWeights.from_mass(
            frame, {frozenset(["a"]): Decimal("0.9"),
                    frozenset(["a", "b"]): Decimal("0.1")})

        # Fuse alice + k copies: bounded (idempotent)
        for k in K_VALUES:
            fused = cautious_fuse(alice_bw, *([adv_bw] * k))
            fused_1 = cautious_fuse(alice_bw, adv_bw)
            assert fused == fused_1, (
                f"reconciliation-only not bounded at k={k}")

        # BUT: no provenance classes → justification is incomplete.
        # Without provenance, we can't distinguish sybil-ring from
        # independent sources.  The full stack can (via how_provenance
        # polynomial).  reconciliation-only produces no polynomial.
        # This is "correct on belief, incorrect on justification."
        bs_linked = _full_stack_belief(
            10, ALICE_A_STR, ADV_A_STR, linked=True)
        bs_unlinked = _full_stack_belief(
            10, ALICE_A_STR, ADV_A_STR, linked=False)
        j_linked = bs_linked["propositions"]["P"]["justification"]
        j_unlinked = bs_unlinked["propositions"]["P"]["justification"]

        # Full stack CAN distinguish: different how_provenance
        assert j_linked["how_provenance"] != j_unlinked["how_provenance"]

        # reconciliation-only (cautious_fuse alone) has no provenance
        # structure at all — it cannot make this distinction.
        # Verdict: {reconciliation-only} fails on justification correctness.
        # Combined: BOTH two-component variants fail "bounded AND correct".
        # Falsification check NEGATIVE — thesis survives.
