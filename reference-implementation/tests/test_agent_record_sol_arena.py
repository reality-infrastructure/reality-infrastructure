"""Gates for the arena on Solana (PREREG A48, P43: R223-R230, S131-S134). Deterministic, no network:
synthetic blocks and transactions in the public node's own json shape."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from rights_events import sol_arena as sa
from rights_events.adapters import sol_arena as ad
from rights_events.adapters.common import AdapterError

ROOT = Path(__file__).resolve().parents[1]
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
JUP = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
SYS = "11111111111111111111111111111111"
MINT_A = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1"
MINT_B = "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB1"
HASH = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
T0, T1 = 1_795_132_800, 1_795_737_599          # 2026-11-20T00:00:00Z .. 2026-11-26T23:59:59Z
SOL = 1_000_000_000


def addr(n: int) -> str:
    digits = "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    s, x = "", n
    for _ in range(6):
        s, x = digits[x % len(digits)] + s, x // len(digits)
    return ("Wa11et" + s).ljust(40, "x")


W, OTHER = addr(1), addr(2)


def tx(sig, slot, bt, signers, programs=(PUMP,), inner=(), wallet=None, sol_delta=0, tokens=None,
       err=None, fee=5000, extra=()):
    """One transaction as getTransaction / getBlock (json) serve it. tokens: {mint: (pre, post)} owned by wallet."""
    keys = list(signers) + [k for k in extra if k not in signers]
    for p in list(programs) + list(inner):
        if p not in keys:
            keys.append(p)
    if wallet and wallet not in keys:
        keys.insert(len(signers), wallet)
    pre = [10 * SOL] * len(keys)
    post = list(pre)
    if wallet:
        post[keys.index(wallet)] += sol_delta
    tb_pre, tb_post = [], []
    for i, (m, (a, b)) in enumerate(sorted((tokens or {}).items())):
        tb_pre.append({"accountIndex": 50 + i, "mint": m, "owner": wallet, "uiTokenAmount": {"amount": str(a)}})
        tb_post.append({"accountIndex": 50 + i, "mint": m, "owner": wallet, "uiTokenAmount": {"amount": str(b)}})
    return {"slot": slot, "blockTime": bt, "version": 0,
            "transaction": {"signatures": [sig], "message": {
                "accountKeys": keys, "header": {"numRequiredSignatures": len(signers)},
                "instructions": [{"programIdIndex": keys.index(p), "accounts": [], "data": ""} for p in programs]}},
            "meta": {"err": err, "fee": fee, "preBalances": pre, "postBalances": post,
                     "preTokenBalances": tb_pre, "postTokenBalances": tb_post,
                     "innerInstructions": [{"index": 0, "instructions": [{"programIdIndex": keys.index(p)} for p in inner]}] if inner else [],
                     "loadedAddresses": {"writable": [], "readonly": []}}}


# --- R223: the sample ------------------------------------------------------------------------------

def test_the_residue_and_the_sample_are_r223s():
    r = ad.residue(HASH)
    assert r == int(ad.sha256_hex(HASH.encode())[:8], 16) % 864
    slots = ad.sampled_slots(470_000_000, 470_216_000, r)
    assert all(s % 864 == r for s in slots) and slots[0] < 470_000_000 + 864
    assert len(slots) == 250 and all(b - a == 864 for a, b in zip(slots, slots[1:]))
    with pytest.raises(AdapterError, match="S131"):
        ad.residue("not base58 0OIl")


# --- R223-R224: the universe -----------------------------------------------------------------------

def test_the_universe_is_every_payer_signer_of_a_successful_venue_swap():
    a, b, c, d, e = (addr(i) for i in range(10, 15))
    block = {"transactions": [
        tx("s1", 1, T0, [a]),                                   # a swap: in
        tx("s2", 1, T0, [b], err={"InstructionError": [0, 1]}),  # failed: out
        tx("s3", 1, T0, [c], programs=(SYS,)),                   # no venue: out
        tx("s4", 1, T0, [d], programs=(SYS,), inner=(JUP,)),     # venue as inner instruction: in
        tx("s5", 1, T0, [e, a]),                                 # e pays: in
    ]}
    assert ad.universe_from_blocks([block], {}) == sorted([a, d, e])
    assert ad.universe_from_blocks([block], {d: "a program, not a wallet"}) == sorted([a, e])
    with pytest.raises(AdapterError, match="S131"):
        ad.universe_from_blocks([block], {b: "outside the universe"})
    with pytest.raises(AdapterError, match="S131"):
        ad.universe_from_blocks([block], {a: ""})


# --- R225: the draw --------------------------------------------------------------------------------

def test_the_draw_is_rederivable_and_refuses_a_planted_address():
    u = sorted(addr(i) for i in range(100, 160))
    g = ad.draw(u, 10)
    assert g == sorted(u, key=lambda x: ad.sha256_hex(("S1" + x).encode()))[:10]
    ad.check_draw(u, g, 10)
    with pytest.raises(AdapterError, match="S132"):
        ad.check_draw(u, g[:-1] + [addr(999)], 10)
    with pytest.raises(AdapterError, match="S132"):
        ad.draw(u + [u[0]], 10)


# --- R226 + SETTLED_SOLANA.md: round trips ---------------------------------------------------------

def test_a_round_trip_nets_sol_with_fees_and_wsol_and_ignores_what_is_not_the_wallets():
    txs = [
        tx("buy", 10, T0 + 10, [W], wallet=W, sol_delta=-1 * SOL - 5000, tokens={MINT_A: (0, 100)}),
        tx("spam", 11, T0 + 11, [OTHER], wallet=W, sol_delta=0, tokens={MINT_A: (100, 0)}),       # not signed by W
        tx("fail", 12, T0 + 12, [W], wallet=W, sol_delta=-5000, tokens={MINT_A: (100, 0)}, err={"x": 1}),
        tx("sell1", 13, T0 + 13, [W], wallet=W, sol_delta=SOL // 2 - 5000, tokens={MINT_A: (100, 40)}),
        tx("sell2", 14, T0 + 14, [W], wallet=W, sol_delta=-5000,
           tokens={MINT_A: (40, 0), ad.WSOL_MINT: (0, SOL)}),                                            # paid in wSOL
    ]
    g = ad.grade_wallet(W, txs, T0, T1)
    assert g["round_trips"] == 1 and g["transactions_counted"] == 3
    assert g["net_lamports"] == SOL // 2 - 15000 and g["net_sol"] == "0.499985000"
    assert g["fees_sol"] == "0.000015000" and g["win_rate"] == "1/1"
    assert g["trips"][0]["first_signature"] == "buy" and g["trips"][0]["last_signature"] == "sell2"


def test_what_is_listed_and_never_netted_and_what_is_held():
    txs = [
        tx("carried", 10, T0 + 10, [W], wallet=W, sol_delta=SOL, tokens={MINT_A: (50, 0)}),          # bought before t0
        tx("gift", 11, T0 + 11, [W], programs=(SYS,), wallet=W, tokens={MINT_B: (0, 70)}),            # no swap in
        tx("sellgift", 12, T0 + 12, [W], wallet=W, sol_delta=3 * SOL, tokens={MINT_B: (70, 0)}),
        tx("hold", 13, T0 + 13, [W], wallet=W, sol_delta=-2 * SOL, tokens={"MintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1": (0, 9)}),
        tx("late", 14, T1 + 1, [W], wallet=W, sol_delta=9 * SOL, tokens={"MintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1": (9, 0)}),
    ]
    g = ad.grade_wallet(W, txs, T0, T1)
    assert g["round_trips"] == 0 and g["net_lamports"] == 0 and g["win_rate"] is None
    assert sorted(x["why"] for x in g["listed_not_netted"]) == ["carried into the window", "received without a swap"]
    assert [h["mint"] for h in g["held_at_t1"]] == ["MintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC1"]


def test_a_two_mint_swap_taints_the_run():
    txs = [
        tx("b", 10, T0 + 1, [W], wallet=W, sol_delta=-SOL, tokens={MINT_A: (0, 10)}),
        tx("route", 11, T0 + 2, [W], wallet=W, tokens={MINT_A: (10, 0), MINT_B: (0, 5)}),
    ]
    g = ad.grade_wallet(W, txs, T0, T1)
    assert g["round_trips"] == 0 and [x["why"] for x in g["listed_not_netted"]] == ["multi-mint swap"]
    assert [h["mint"] for h in g["held_at_t1"]] == [MINT_B]


def test_the_status_words_are_r119s_over_sol():
    assert ad.status_for(False, "FULL", 5) == "OPEN"
    assert ad.status_for(True, "PARTIAL", 5) == "UNDECIDED"
    assert ad.status_for(True, "FULL", 1) == "KEEP"
    assert ad.status_for(True, "FULL", 0) == "DROP"
    assert ad.sol(-1) == "-0.000000001" and ad.sol(1_500_000_000) == "1.500000000"


# --- the cohort end to end: verify and grade from pinned files --------------------------------------

def _write(p: Path, b: bytes) -> dict:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b)
    return {"bytes": len(b), "sha256": ad.sha256_hex(b)}


def build_cohort(tmp: Path, b: int = 3) -> dict:
    first, last = 1000, 1000 + 864 * 3
    r = ad.residue(HASH)
    slots = ad.sampled_slots(first, last, r)
    files = {"header_1000.json": _write(tmp / "header_1000.json", json.dumps({"result": {"blockhash": HASH}}).encode())}
    sampled, payers = [], [addr(200 + i) for i in range(8)]
    for i, s in enumerate(slots):
        block = {"result": {"blockhash": HASH, "transactions": [tx(f"u{i}{j}", s, T0 - 100, [p]) for j, p in enumerate(payers[i::len(slots)])]}}
        raw = json.dumps(block).encode()
        name = f"blocks/{s}.json.gz"
        files[name] = _write(tmp / name, gzip.compress(raw, 9, mtime=0))
        sampled.append({"slot": s, "status": "pinned", "file": name, "raw_sha256": ad.sha256_hex(raw), **files[name]})
    universe = sorted(payers)
    cap = {"kind": "proof_of_outcome_arena_solana_capture", "prereg": "A48", "cohort": "S1",
           "settled_solana_sha256": sa.settled_sha(), "observation_day": "2026-11-19",
           "first_slot": first, "last_slot": last, "first_blockhash": HASH, "header_file": "header_1000.json",
           "modulus": 864, "residue": r, "sampled": sampled, "venues": dict(ad.VENUES), "excluded": {},
           "universe_count": len(universe), "universe": universe, "b": b, "draw_tag": "S1",
           "graded": ad.draw(universe, b),
           "window": {"t0_date": "2026-11-20", "t1_date": "2026-11-26", "t0": T0, "t1": T1, "k": 7}}
    files["capture_SOL_S1.json"] = _write(tmp / "capture_SOL_S1.json", json.dumps(cap, indent=1, sort_keys=True).encode())
    (tmp / "MANIFEST_SOL_S1.json").write_bytes(json.dumps({"cohort": "S1", "files": files}).encode())
    return cap


def write_day(tmp: Path, day: str, recs: dict) -> None:
    ddir = tmp / "days" / day
    files = {}
    for w, rec in recs.items():
        rec = {"address": w, "day": day, "reached_start": True, "pages": 1, "first_served_signature": None,
               "listed": 0, "dropped_failed": 0, "refused": [], "transactions": [], **rec}
        files[f"{w}.json.gz"] = _write(ddir / f"{w}.json.gz", gzip.compress(json.dumps(rec).encode(), 9, mtime=0))
    (ddir / "MANIFEST.json").write_bytes(json.dumps({"day": day, "files": files}).encode())


def test_a_cohort_verifies_and_grades_from_its_pinned_bytes(tmp_path):
    cap = build_cohort(tmp_path)
    assert sa.verify_capture(tmp_path)["universe_count"] == 8
    g1, g2, g3 = cap["graded"]
    days = [f"2026-11-{d}" for d in range(20, 27)]
    for i, d in enumerate(days):
        recs = {g1: {}, g2: {}, g3: {}}
        if i == 0:
            recs[g1] = {"transactions": [tx("b", 1, T0 + 5, [g1], wallet=g1, sol_delta=-SOL, tokens={MINT_A: (0, 1)})]}
            recs[g2] = {"transactions": [tx("b2", 1, T0 + 5, [g2], wallet=g2, sol_delta=-SOL, tokens={MINT_A: (0, 1)})]}
        if i == 1:
            recs[g1] = {"transactions": [tx("s", 2, T0 + 86_400 + 5, [g1], wallet=g1, sol_delta=2 * SOL, tokens={MINT_A: (1, 0)})]}
            recs[g2] = {"transactions": [tx("s2", 2, T0 + 86_400 + 5, [g2], wallet=g2, sol_delta=SOL // 2, tokens={MINT_A: (1, 0)})]}
        if i == 2:
            recs[g3] = {"reached_start": False, "pages": 30, "first_served_signature": "zzz"}
        write_day(tmp_path, d, recs)
    mid = sa.grade(tmp_path, "2026-11-23")
    assert mid["days_pinned"] == days[:3] and mid["counts"]["OPEN"] == 3
    done = sa.grade(tmp_path, "2026-11-27")
    by = {r["address"]: r for r in done["rows"]}
    assert by[g1]["status"] == "KEEP" and by[g1]["net_sol"] == "1.000000000"
    assert by[g2]["status"] == "DROP" and by[g2]["net_sol"] == "-0.500000000"
    assert by[g3]["status"] == "UNDECIDED" and "30 pages" in by[g3]["coverage_reasons"][0]
    assert done["counts"] == {"KEEP": 1, "DROP": 1, "UNDECIDED": 1, "OPEN": 0}
    assert "UNIVERSE, NOT GRADED" in done["what_is_not_claimed"] and by[g1]["solscan"].endswith(g1)
    assert sa.render_md(done).count("| KEEP |") == 1


def test_a_changed_byte_a_planted_address_and_another_rule_are_refused(tmp_path):
    cap = build_cohort(tmp_path)
    blk = tmp_path / cap["sampled"][0]["file"]
    good = blk.read_bytes()
    blk.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))
    with pytest.raises(AdapterError, match="S131"):
        sa.verify_capture(tmp_path)
    blk.write_bytes(good)
    sa.verify_capture(tmp_path)

    capf = tmp_path / "capture_SOL_S1.json"
    planted = dict(cap, graded=cap["graded"][:-1] + [addr(999)])
    b = json.dumps(planted, indent=1, sort_keys=True).encode()
    capf.write_bytes(b)
    man = json.loads((tmp_path / "MANIFEST_SOL_S1.json").read_bytes())
    man["files"]["capture_SOL_S1.json"] = {"bytes": len(b), "sha256": ad.sha256_hex(b)}
    (tmp_path / "MANIFEST_SOL_S1.json").write_bytes(json.dumps(man).encode())
    with pytest.raises(AdapterError, match="S132"):
        sa.verify_capture(tmp_path)

    other = tmp_path / "OTHER.md"
    other.write_bytes(b"another rule\n")
    with pytest.raises(AdapterError, match="SETTLED_SOLANA"):
        sa.verify_capture(tmp_path, other)


def test_without_the_blocks_the_universe_is_said_not_rederived_and_a_half_set_is_refused(tmp_path):
    cap = build_cohort(tmp_path)
    man = json.loads((tmp_path / "MANIFEST_SOL_S1.json").read_bytes())
    man["files"] = {k: v for k, v in man["files"].items() if not k.startswith("blocks/")}
    (tmp_path / "MANIFEST_SOL_S1.json").write_bytes(json.dumps(man).encode())
    files = [tmp_path / s["file"] for s in cap["sampled"]]
    files[0].unlink()
    with pytest.raises(AdapterError, match="S131: 1 of"):
        sa.verify_capture(tmp_path, require_blocks=False)
    for f in files[1:]:
        f.unlink()
    with pytest.raises(AdapterError, match="not here"):
        sa.verify_capture(tmp_path)
    v = sa.verify_capture(tmp_path, require_blocks=False)
    assert v["universe_rederived"] is False
    assert sa.grade(tmp_path, "2026-11-21", require_blocks=False)["universe_rederived"] is False


def test_the_capture_runs_under_the_ratified_rule():
    assert sa.settled_sha().startswith("b99d88ec")


# --- S133: no leaderboard, ranking site or indexer list in the code that makes S1 --------------------

def test_no_leaderboard_is_read_by_the_code_that_makes_s1():
    files = [ROOT / "rights_events" / "sol_arena.py", ROOT / "rights_events" / "adapters" / "sol_arena.py",
             *sorted((ROOT / "rights_events" / "fixtures" / "agent_record" / "arena_sol").glob("*.py"))]
    assert len(files) == 5
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        for word in ("leaderboard", "gmgn", "top_traders", "birdeye", "api.solscan", "pro-api.solscan", "gdex", "helius"):
            assert word not in text, f"{f.name} names {word}"
    rpc = (ROOT / "rights_events" / "fixtures" / "agent_record" / "arena_sol" / "rpc.py").read_text(encoding="utf-8")
    assert 'PUBLIC_RPC = "https://api.mainnet-beta.solana.com"' in rpc and rpc.count("https://") == 1
