"""THE ARENA ON SOLANA — the pure adapter (PREREG A48, R223-R230, S131-S134; SETTLED_SOLANA.md).

Pure functions of pinned public-node bytes: no network, no clock, no randomness. Everything that
fetches lives in fixtures/agent_record/arena_sol/ (the capture tools) and never here.

  residue / sampled_slots     R223: the day's sample, one slot in 864, the residue from the day's
                              first blockhash
  universe_from_blocks        R223-R224: every fee payer that signed a successful transaction
                              invoking a named venue program in a sampled block
  draw / check_draw           R225: the first B of the universe by sha256("S1" + address)
  grade_wallet                R226 + SETTLED_SOLANA.md 2-4, 6a-6c: round trips in SOL
  status_for                  R230 with R119's words

Amounts are integers (lamports and raw token units); a SOL figure is printed from lamports with nine
decimals and never converted.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Mapping

from rights_events.adapters.common import AdapterError

MODULUS = 864
DRAW_TAG = "S1"
WSOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000

# R224: frozen for cohort S1.
VENUES: Mapping[str, str] = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PumpSwap",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CAMMCzo5YL8w4VFF8KVHrK9vMFXTpfdpkjCTQqJw7Mmm": "Raydium CLMM",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "Raydium CPMM",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YaVaPDRn": "Meteora DLMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter v6",
}

_B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def is_address(a: object) -> bool:
    return isinstance(a, str) and 32 <= len(a) <= 44 and set(a) <= _B58


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sol(lamports: int) -> str:
    """Lamports as SOL with nine decimals, exact (no float)."""
    sign = "-" if lamports < 0 else ""
    q, r = divmod(abs(int(lamports)), LAMPORTS_PER_SOL)
    return f"{sign}{q}.{r:09d}"


# --- R223: the sample -----------------------------------------------------------------------------

def residue(first_blockhash: str) -> int:
    """The first 8 hex of sha256(blockhash) as an integer, mod 864."""
    if not is_address(first_blockhash):
        raise AdapterError("S131: the day's first blockhash is not base58")
    return int(sha256_hex(first_blockhash.encode("ascii"))[:8], 16) % MODULUS


def sampled_slots(first_slot: int, last_slot: int, r: int) -> list[int]:
    if not (0 <= r < MODULUS) or first_slot > last_slot:
        raise AdapterError("S131: bad slot range or residue")
    start = first_slot + ((r - first_slot) % MODULUS)
    return list(range(start, last_slot + 1, MODULUS))


# --- transactions as the node serves them (encoding json) ------------------------------------------

def tx_keys(tx: Mapping) -> list[str]:
    """Static account keys, then loaded writable, then loaded readonly: the index space of the
    instructions and of pre/postBalances."""
    try:
        keys = list(tx["transaction"]["message"]["accountKeys"])
        loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
        return keys + list(loaded.get("writable") or []) + list(loaded.get("readonly") or [])
    except (KeyError, TypeError) as exc:
        raise AdapterError(f"S131: a transaction without its account keys ({exc})") from exc


def tx_signers(tx: Mapping) -> list[str]:
    m = tx["transaction"]["message"]
    n = int(m["header"]["numRequiredSignatures"])
    return list(m["accountKeys"][:n])


def tx_ok(tx: Mapping) -> bool:
    meta = tx.get("meta")
    return bool(meta) and meta.get("err") is None


def tx_venues(tx: Mapping) -> list[str]:
    """Named venue programs invoked, top level or inner (R223: 'directly or as an inner instruction')."""
    keys = tx_keys(tx)
    idx = [i["programIdIndex"] for i in tx["transaction"]["message"]["instructions"]]
    for group in (tx["meta"].get("innerInstructions") or []):
        idx += [i["programIdIndex"] for i in group["instructions"]]
    out = {keys[i] for i in idx if 0 <= i < len(keys) and keys[i] in VENUES}
    return sorted(out)


def tx_signature(tx: Mapping) -> str:
    return tx["transaction"]["signatures"][0]


# --- R223-R224: the universe -----------------------------------------------------------------------

def payers_in_block(block: Mapping) -> set[str]:
    out: set[str] = set()
    for tx in block.get("transactions") or []:
        if not tx_ok(tx):
            continue
        signers = tx_signers(tx)
        payer = tx["transaction"]["message"]["accountKeys"][0]
        if payer in signers and tx_venues(tx):
            out.add(payer)
    return out


def universe_from_blocks(blocks: Iterable[Mapping], excluded: Mapping[str, str]) -> list[str]:
    """Blocks may be a generator: each is reduced to its payers and dropped (a day is ~465 blocks of
    ~2-4 MB each; holding them parsed does not fit in memory, measured A48.1)."""
    return universe_from_payers((payers_in_block(b) for b in blocks), excluded)


def universe_from_payers(payer_sets: Iterable[set[str]], excluded: Mapping[str, str]) -> list[str]:
    seen: set[str] = set()
    for s in payer_sets:
        seen |= s
    for a, why in excluded.items():
        if a not in seen:
            raise AdapterError(f"S131: excluded address {a} is not in the universe")
        if not why:
            raise AdapterError(f"S131: excluded address {a} carries no reason")
    return sorted(seen - set(excluded))


# --- R225: the draw --------------------------------------------------------------------------------

def draw_key(address: str, tag: str = DRAW_TAG) -> str:
    return sha256_hex((tag + address).encode("ascii"))


def draw(universe: list[str], b: int, tag: str = DRAW_TAG) -> list[str]:
    if len(set(universe)) != len(universe):
        raise AdapterError("S132: an address twice in the universe")
    return sorted(universe, key=lambda a: (draw_key(a, tag), a))[:b]


def check_draw(universe: list[str], graded: list[str], b: int, tag: str = DRAW_TAG) -> None:
    if list(graded) != draw(universe, b, tag):
        raise AdapterError("S132: the graded set is not R225's draw from the published universe")


# --- R226 + SETTLED_SOLANA.md: one wallet's round trips ---------------------------------------------

def _token_holdings(entries: Iterable[Mapping], owner: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in entries or []:
        if e.get("owner") == owner:
            amt = int(e["uiTokenAmount"]["amount"])
            out[e["mint"]] = out.get(e["mint"], 0) + amt
    return out


def wallet_effect(tx: Mapping, wallet: str) -> dict:
    """What one transaction did to the wallet: lamports (native + wSOL), the fee if it paid it, and
    each other mint's balance before and after."""
    keys = tx_keys(tx)
    meta = tx["meta"]
    if wallet not in keys:
        raise AdapterError(f"the wallet is not among the transaction's keys: {tx_signature(tx)}")
    i = keys.index(wallet)
    native = int(meta["postBalances"][i]) - int(meta["preBalances"][i])
    pre = _token_holdings(meta.get("preTokenBalances"), wallet)
    post = _token_holdings(meta.get("postTokenBalances"), wallet)
    wsol = post.get(WSOL_MINT, 0) - pre.get(WSOL_MINT, 0)
    mints = {}
    for m in sorted(set(pre) | set(post)):
        if m == WSOL_MINT:
            continue
        if pre.get(m, 0) != post.get(m, 0):
            mints[m] = (pre.get(m, 0), post.get(m, 0))
    fee = int(meta.get("fee") or 0) if keys[0] == wallet else 0
    return {"signature": tx_signature(tx), "slot": tx.get("slot"), "block_time": tx.get("blockTime"),
            "sol_delta": native + wsol, "fee": fee, "mints": mints, "venues": tx_venues(tx)}


def grade_wallet(wallet: str, txs: Iterable[Mapping], t0: int, t1: int) -> dict:
    """SETTLED_SOLANA.md over the wallet's transactions, in chain order (slot, then the order given).

    Counted: a round trip from zero to zero in one mint through named venues, opened and closed in
    [t0, t1]. Listed and never netted: a run that began with a token received without a swap, a run
    carried into the window, a run touched by a transfer or by a swap moving two or more other mints.
    Held at t1: counted, never valued."""
    if not is_address(wallet):
        raise AdapterError(f"not a Solana address: {wallet!r}")
    rows = []
    for pos, tx in enumerate(txs):
        if not tx_ok(tx) or wallet not in tx_signers(tx):
            continue                                     # R226: failed, or not the wallet's
        bt = tx.get("blockTime")
        if bt is None or not (t0 <= int(bt) <= t1):
            continue
        rows.append((int(tx.get("slot") or 0), pos, wallet_effect(tx, wallet)))
    rows.sort(key=lambda r: (r[0], r[1]))

    open_runs: dict[str, dict] = {}
    trips, listed = [], []
    for _, _, eff in rows:
        swap = bool(eff["venues"])
        multi = len(eff["mints"]) >= 2
        for mint, (pre, post) in eff["mints"].items():
            run = open_runs.get(mint)
            if run is None:
                if pre == 0 and swap and not multi:
                    run = {"mint": mint, "taint": None}
                elif pre == 0:
                    run = {"mint": mint, "taint": "received without a swap" if not swap else "multi-mint swap"}
                else:
                    run = {"mint": mint, "taint": "carried into the window"}
                run.update(signatures=[], sol=0, fees=0, opened=eff["block_time"])
                open_runs[mint] = run
            elif not swap:
                run["taint"] = run["taint"] or "moved without a swap"
            elif multi:
                run["taint"] = run["taint"] or "multi-mint swap"
            run["signatures"].append(eff["signature"])
            if len(eff["mints"]) == 1:                    # the SOL leg belongs to this mint alone
                run["sol"] += eff["sol_delta"]
                run["fees"] += eff["fee"]
            if post == 0:
                run["closed"] = eff["block_time"]
                (listed if run["taint"] else trips).append(run)
                del open_runs[mint]
    held = [{"mint": r["mint"], "signatures": len(r["signatures"]), "taint": r["taint"]}
            for _, r in sorted(open_runs.items())]
    net = sum(t["sol"] for t in trips)
    fees = sum(t["fees"] for t in trips)
    out_trips = [{"mint": t["mint"], "net_sol": sol(t["sol"]), "fees_sol": sol(t["fees"]),
                  "first_signature": t["signatures"][0], "last_signature": t["signatures"][-1],
                  "transactions": len(t["signatures"])} for t in trips]
    wins = [t for t in trips if t["sol"] > 0]
    return {"address": wallet, "transactions_counted": len(rows), "round_trips": len(trips),
            "net_sol": sol(net), "net_lamports": net, "fees_sol": sol(fees),
            "win_rate": (f"{len(wins)}/{len(trips)}" if trips else None),
            "biggest_win_sol": sol(max(t["sol"] for t in trips)) if trips else None,
            "biggest_loss_sol": sol(min(t["sol"] for t in trips)) if trips else None,
            "first_signature": rows[0][2]["signature"] if rows else None,
            "last_signature": rows[-1][2]["signature"] if rows else None,
            "trips": out_trips,
            "listed_not_netted": [{"mint": r["mint"], "why": r["taint"], "transactions": len(r["signatures"]),
                                   "first_signature": r["signatures"][0]} for r in listed],
            "held_at_t1": held}


# --- R230: the status word -------------------------------------------------------------------------

def status_for(complete: bool, coverage: str, net_lamports: int) -> str:
    if coverage not in ("FULL", "PARTIAL"):
        raise AdapterError(f"unknown coverage {coverage!r}")
    if not complete:
        return "OPEN"
    if coverage == "PARTIAL":
        return "UNDECIDED"
    return "KEEP" if net_lamports > 0 else "DROP"
