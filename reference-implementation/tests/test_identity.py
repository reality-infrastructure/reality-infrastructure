"""Tests for ri_core.identity — identity anchor + shared provenance."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from ri_core.identity import Identity, IdentityError, LocalAuthority
from ri_core.serialization import encode


# ── Sign / verify ───────────────────────────────────────────────────

class TestSignVerify:
    def test_roundtrip(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        data = encode({"msg": "hello"})
        sig = auth.sign(alice, data)
        assert auth.verify(alice, data, sig)

    def test_tampered_bytes_fails(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        data = encode({"msg": "hello"})
        sig = auth.sign(alice, data)
        assert not auth.verify(alice, data + b'\x00', sig)

    def test_wrong_identity_fails(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        bob = auth.issue_identity("bob")
        data = encode({"msg": "hello"})
        sig = auth.sign(alice, data)
        assert not auth.verify(bob, data, sig)

    def test_verify_unissued_returns_false(self):
        """A1: verify with unknown identity returns False, does not raise."""
        auth = LocalAuthority(seed=b'test')
        fake = Identity(identity_id="fake", anchor_id="local", name="fake")
        assert not auth.verify(fake, b'data', b'\x00' * 32)

    def test_sign_unissued_raises(self):
        """A1: sign with unknown identity raises IdentityError."""
        auth = LocalAuthority(seed=b'test')
        fake = Identity(identity_id="fake", anchor_id="local", name="fake")
        with pytest.raises(IdentityError, match="not issued"):
            auth.sign(fake, b'data')

    def test_sig_is_32_bytes(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        assert len(auth.sign(alice, encode("x"))) == 32

    def test_empty_data(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        sig = auth.sign(alice, b'')
        assert auth.verify(alice, b'', sig)


# ── Duplicate identity (A2) ────────────────────────────────────────

class TestDuplicateIdentity:
    def test_duplicate_name_raises(self):
        auth = LocalAuthority(seed=b'test')
        auth.issue_identity("alice")
        with pytest.raises(IdentityError, match="already issued"):
            auth.issue_identity("alice")

    def test_different_names_ok(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("alice")
        b = auth.issue_identity("bob")
        assert a.identity_id != b.identity_id


# ── Key derivation domain separation (A3) ──────────────────────────

class TestKeyDerivation:
    def test_different_anchors_different_sigs(self):
        """Same seed, different anchor_id → different keys → different sigs."""
        auth_a = LocalAuthority(seed=b'shared', anchor_id='anchor-a')
        auth_b = LocalAuthority(seed=b'shared', anchor_id='anchor-b')
        alice_a = auth_a.issue_identity("alice")
        alice_b = auth_b.issue_identity("alice")
        data = encode({"msg": "hello"})
        assert auth_a.sign(alice_a, data) != auth_b.sign(alice_b, data)

    def test_same_config_deterministic(self):
        """Same seed + anchor_id → same key → same sig (determinism)."""
        auth1 = LocalAuthority(seed=b'seed', anchor_id='auth')
        auth2 = LocalAuthority(seed=b'seed', anchor_id='auth')
        a1 = auth1.issue_identity("alice")
        a2 = auth2.issue_identity("alice")
        data = encode({"msg": "hello"})
        assert auth1.sign(a1, data) == auth2.sign(a2, data)

    def test_cross_verify_fails(self):
        """Sig from anchor A does not verify under anchor B."""
        auth_a = LocalAuthority(seed=b'shared', anchor_id='anchor-a')
        auth_b = LocalAuthority(seed=b'shared', anchor_id='anchor-b')
        alice_a = auth_a.issue_identity("alice")
        alice_b = auth_b.issue_identity("alice")
        data = encode({"msg": "hello"})
        sig = auth_a.sign(alice_a, data)
        assert not auth_b.verify(alice_b, data, sig)


# ── Shared provenance ──────────────────────────────────────────────

class TestSharedProvenance:
    def test_reflexive(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        assert auth.shared_provenance(a, a)

    def test_symmetric(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        b = auth.issue_identity("b")
        auth.link_identities(a, b)
        assert auth.shared_provenance(a, b)
        assert auth.shared_provenance(b, a)

    def test_transitive_chain(self):
        """link(a,b), link(b,c) ⇒ shared_provenance(a,c)."""
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        b = auth.issue_identity("b")
        c = auth.issue_identity("c")
        auth.link_identities(a, b)
        auth.link_identities(b, c)
        assert auth.shared_provenance(a, c)

    def test_not_linked(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        b = auth.issue_identity("b")
        assert not auth.shared_provenance(a, b)

    def test_unknown_identity_returns_false(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        fake = Identity(identity_id="fake", anchor_id="x", name="fake")
        assert not auth.shared_provenance(a, fake)
        assert not auth.shared_provenance(fake, a)

    def test_link_unknown_raises(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        fake = Identity(identity_id="fake", anchor_id="x", name="fake")
        with pytest.raises(IdentityError, match="not issued"):
            auth.link_identities(a, fake)

    def test_no_unlink_method(self):
        auth = LocalAuthority(seed=b'test')
        assert not hasattr(auth, 'unlink_identities')
        assert not hasattr(auth, 'unlink')

    def test_link_idempotent(self):
        auth = LocalAuthority(seed=b'test')
        a = auth.issue_identity("a")
        b = auth.issue_identity("b")
        auth.link_identities(a, b)
        auth.link_identities(a, b)  # should not error
        assert auth.shared_provenance(a, b)

    def test_longer_chain(self):
        auth = LocalAuthority(seed=b'test')
        ids = [auth.issue_identity(f"id-{i}") for i in range(5)]
        auth.link_identities(ids[0], ids[1])
        auth.link_identities(ids[1], ids[2])
        auth.link_identities(ids[2], ids[3])
        auth.link_identities(ids[3], ids[4])
        # All pairwise shared
        for i in range(5):
            for j in range(5):
                assert auth.shared_provenance(ids[i], ids[j])


# ── Sybil cost ──────────────────────────────────────────────────────

class TestSybilCost:
    def test_monotone_increase(self):
        auth = LocalAuthority(seed=b'test', kappa=10)
        costs = [auth.cumulative_cost()]
        for i in range(5):
            auth.issue_identity(f"id-{i}")
            costs.append(auth.cumulative_cost())
        for i in range(len(costs) - 1):
            assert costs[i + 1] > costs[i]
        assert costs == [0, 10, 20, 30, 40, 50]

    def test_kappa_knob(self):
        a1 = LocalAuthority(seed=b't', kappa=1)
        a2 = LocalAuthority(seed=b't', kappa=100)
        a1.issue_identity("x")
        a2.issue_identity("x")
        assert a1.cumulative_cost() == 1
        assert a2.cumulative_cost() == 100

    def test_initial_cost_zero(self):
        assert LocalAuthority(seed=b'test').cumulative_cost() == 0


# ── Identity immutability ──────────────────────────────────────────

class TestIdentityImmutable:
    def test_frozen(self):
        auth = LocalAuthority(seed=b'test')
        alice = auth.issue_identity("alice")
        with pytest.raises(AttributeError):
            alice.identity_id = "tampered"


# ── Hypothesis: equivalence-relation laws ──────────────────────────

class TestHypothesisEquivalence:
    @given(
        n=st.integers(min_value=1, max_value=10),
        links=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=9),
                st.integers(min_value=0, max_value=9),
            ),
            max_size=20,
        ),
    )
    @settings(max_examples=200)
    def test_equivalence_relation(self, n, links):
        auth = LocalAuthority(seed=b'hyp')
        ids = [auth.issue_identity(f"id-{i}") for i in range(n)]

        for i, j in links:
            if i < n and j < n:
                auth.link_identities(ids[i], ids[j])

        # Reflexivity
        for i in range(n):
            assert auth.shared_provenance(ids[i], ids[i])

        # Symmetry
        for i in range(n):
            for j in range(n):
                if auth.shared_provenance(ids[i], ids[j]):
                    assert auth.shared_provenance(ids[j], ids[i])

        # Transitivity
        for i in range(n):
            for j in range(n):
                if auth.shared_provenance(ids[i], ids[j]):
                    for k in range(n):
                        if auth.shared_provenance(ids[j], ids[k]):
                            assert auth.shared_provenance(ids[i], ids[k])
