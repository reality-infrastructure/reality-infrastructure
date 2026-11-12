"""THE DOOR (PREREG A44, R191–R200, S118–S120).

Any HyperLiquid address enrols itself to be graded under SETTLED.md as class AGENT:

  * R191/R192: an enrolment statement of six fixed lines, signed by the address's own key
    (EIP-191 personal_sign over the statement's exact bytes; secp256k1; keccak-256). The check
    is arithmetic done here with the standard library only: the signature must recover to the
    statement's address (S118). Nothing about the owner is recorded; the label is self-declared.
  * R193: an entrant is graded, per cohort whose newest capture pins its pages, by SETTLED.md's
    two figures as the arena's row carries them and, beside them, round trips PER COIN (from a
    fill whose startPosition is 0 to the fill that returns that coin's position to 0). A
    position carried into the window or open at its end is counted and never valued; its closes
    are in SETTLED.md's figure and not in trip net.
  * R194: a trade id (`tid`) on the pinned pages of two addresses of one capture is a crossing;
    the cohort's count is printed and each entrant's crossed fills, crossed trips and trip net
    uncrossed.
  * R195: OPEN / UNDECIDED / KEEP / DROP for class AGENT.  R196: the sentence every row carries.
  * R197: door_<as_of>.json/.md are pins, door_latest.json is byte-equal (S119).
  * R198: the kill line in shots: asks.jsonl rows enter only by the operator's quoted word
    (S120); CLOSED at 20 asks with 0 outside entrants; CLEARED at 3 outside FULL rows over a
    complete window.

No network, no clock, no venue figure. Usage:
    python -m rights_events.arena_door door --as-of YYYY-MM-DD
    python -m rights_events.arena_door enrol --statement FILE --signature 0x… --date YYYY-MM-DD
    python -m rights_events.arena_door withdraw --statement FILE --signature 0x… --date YYYY-MM-DD
    python -m rights_events.arena_door template --address 0x… --model "label"
    python -m rights_events.arena_door ask --date YYYY-MM-DD --to "who" --channel "how" --operator-word "the quote"
    python -m rights_events.arena_door check-latest
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from rights_events import arena_ai_board as aib
from rights_events.adapters.common import AdapterError
from rights_events.arena_gap import RECORD_ADDRESS

ARENA_DIR = aib.ARENA_DIR
DOOR_DIR = ARENA_DIR / "door"
REGISTRY = ARENA_DIR / "entrants.json"
ASKS = DOOR_DIR / "asks.jsonl"
SETTLED = aib.SETTLED
DOOR_KIND = "proof_of_outcome_door"
ENDPOINT = ("https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/"
            "contract/agent-record/reference-implementation/rights_events/fixtures/agent_record/arena/door/door_latest.json")
COLUMNS = aib.COLUMNS
ROI_NOT_COMPUTED = aib.ROI_NOT_COMPUTED
ROW_SENTENCE = "A settled net, not a finding about skill; the page does not name counterparties; the label is self-declared."
HEAD_ENROL = "PROOF OF OUTCOME ARENA: ENROLMENT"
HEAD_WITHDRAW = "PROOF OF OUTCOME ARENA: WITHDRAWAL"
LAST_ENROL = "statement: grade this address by what settled on chain; I claim nothing else."
LAST_WITHDRAW = "statement: stop grading this address; rows already pinned stand."
REGISTRY_LINE = "registry: arena/entrants.json"
KILL_ASKS = 20
CLEAR_ROWS = 3
NOT_CAPTURED = "LISTED, NOT YET CAPTURED"
TRIPS_NOT_COMPUTED = "TRIPS NOT COMPUTED"      # a complete FULL row whose pages are not on the branch: R195 cannot be read, and is not guessed
_ADDR = re.compile(r"^0x[0-9a-f]{40}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_MODEL = re.compile(r"^[\x20-\x7e]{1,64}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DOOR_FILE = re.compile(r"^door_\d{4}-\d{2}-\d{2}\.json$")


# --- keccak-256 (the original Keccak padding, not SHA-3's) ---------------------------------------

_MASK = (1 << 64) - 1
_RC = (0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
       0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
       0x000000000000800A, 0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008)
_ROT = ((0, 36, 3, 41, 18), (1, 44, 10, 45, 2), (62, 6, 43, 15, 61), (28, 55, 25, 21, 56), (27, 20, 39, 8, 14))   # [x][y]


def _rol(v: int, n: int) -> int:
    return ((v << n) | (v >> (64 - n))) & _MASK if n else v


def _keccak_f(a: list[list[int]]) -> list[list[int]]:
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & _MASK & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def sponge256(data: bytes, pad: int) -> bytes:
    """A 256-bit sponge at rate 136 bytes. pad 0x01 is Keccak-256 (Ethereum's); pad 0x06 is SHA3-256 (the gate's cross-check)."""
    rate = 136
    p = bytearray(data)
    p.append(pad)
    while len(p) % rate:
        p.append(0)
    p[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(p), rate):
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(p[off + 8 * i: off + 8 * i + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def keccak256(data: bytes) -> bytes:
    return sponge256(data, 0x01)


# --- secp256k1: public-key recovery --------------------------------------------------------------

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def ec_add(p1, p2):
    """Affine addition on y^2 = x^3 + 7 over F_P; None is the point at infinity."""
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        lam = (3 * x1 * x1) * pow(2 * y1, -1, P) % P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return x3, (lam * (x1 - x3) - y1) % P


def ec_mul(k: int, pt):
    k %= N
    acc = None
    while k:
        if k & 1:
            acc = ec_add(acc, pt)
        pt = ec_add(pt, pt)
        k >>= 1
    return acc


def address_of_point(pt) -> str:
    return "0x" + keccak256(pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big"))[12:].hex()


def personal_hash(message: bytes) -> bytes:
    """EIP-191 personal_sign: keccak256("\\x19Ethereum Signed Message:\\n" + len + message)."""
    return keccak256(b"\x19Ethereum Signed Message:\n" + str(len(message)).encode("ascii") + message)


def recover_address(message: bytes, signature_hex: str) -> str:
    """The address whose key made this personal_sign signature over these exact bytes. S118 on anything malformed."""
    s = signature_hex.strip()
    if not re.match(r"^0x[0-9a-fA-F]{130}$", s):
        raise AdapterError("S118: the signature is not 0x + 130 hex characters (r, s, v)")
    raw = bytes.fromhex(s[2:])
    r, sv, v = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:64], "big"), raw[64]
    if v in (27, 28):
        v -= 27
    if v not in (0, 1):
        raise AdapterError(f"S118: the signature's v is {raw[64]}, not 27, 28, 0 or 1")
    if not (1 <= r < N and 1 <= sv < N):
        raise AdapterError("S118: the signature's r or s is out of range")
    y2 = (pow(r, 3, P) + 7) % P
    y = pow(y2, (P + 1) // 4, P)
    if y * y % P != y2:
        raise AdapterError("S118: the signature's r is not a point on the curve")
    if y & 1 != v:
        y = P - y
    z = int.from_bytes(personal_hash(message), "big")
    rinv = pow(r, -1, N)
    q = ec_add(ec_mul(sv * rinv % N, (r, y)), ec_mul((-z * rinv) % N, G))
    if q is None:
        raise AdapterError("S118: the signature recovers to no key")
    return address_of_point(q)


# --- R192: the statement --------------------------------------------------------------------------

def statement_text(address: str, model: str, settled_sha256: str, withdrawal: bool = False) -> str:
    return "\n".join([HEAD_WITHDRAW if withdrawal else HEAD_ENROL, f"address: {address}", f"model: {model}",
                      f"settled_sha256: {settled_sha256}", REGISTRY_LINE, LAST_WITHDRAW if withdrawal else LAST_ENROL]) + "\n"


def parse_statement(raw: bytes) -> dict:
    """R192's bytes exactly, or S118. Returns {address, model, settled_sha256, withdrawal}."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AdapterError("S118: the statement starts with a byte order mark")
    if b"\r" in raw:
        raise AdapterError("S118: the statement holds a carriage return (lines are LF-terminated)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdapterError("S118: the statement is not UTF-8") from exc
    lines = text.split("\n")
    if len(lines) != 7 or lines[6] != "":
        raise AdapterError("S118: the statement is not exactly six LF-terminated lines")
    if lines[0] not in (HEAD_ENROL, HEAD_WITHDRAW):
        raise AdapterError("S118: the statement's first line is not the enrolment or the withdrawal heading")
    withdrawal = lines[0] == HEAD_WITHDRAW
    fields = {}
    for line, key in zip(lines[1:4], ("address", "model", "settled_sha256")):
        if not line.startswith(key + ": "):
            raise AdapterError(f"S118: the statement's line {key!r} is missing or out of order")
        fields[key] = line[len(key) + 2:]
    if not _ADDR.match(fields["address"]):
        raise AdapterError("S118: the address is not 0x + 40 lower-case hex characters")
    if not _MODEL.match(fields["model"]):
        raise AdapterError("S118: the label is not 1 to 64 printable ASCII characters")
    if not _SHA.match(fields["settled_sha256"]):
        raise AdapterError("S118: settled_sha256 is not 64 lower-case hex characters")
    if text != statement_text(fields["address"], fields["model"], fields["settled_sha256"], withdrawal):
        raise AdapterError("S118: the statement is not R192's fixed words")
    fields["withdrawal"] = withdrawal
    return fields


def settled_sha(settled_path: Path = SETTLED) -> str:
    if not settled_path.exists():
        raise AdapterError("S119: SETTLED.md is missing")
    return aib.sha256_bytes(settled_path.read_bytes().replace(b"\r\n", b"\n"))


def verify_statement(raw: bytes, signature_hex: str, settled_sha256: str) -> dict:
    """S118 unless the statement is R192's, names the branch's SETTLED.md and is signed by its own address."""
    f = parse_statement(raw)
    if f["settled_sha256"] != settled_sha256:
        raise AdapterError(f"S118: the statement names SETTLED.md {f['settled_sha256'][:12]}…, the branch's is {settled_sha256[:12]}…")
    got = recover_address(raw, signature_hex)
    if got != f["address"]:
        raise AdapterError(f"S118: the signature recovers to {got}, not to the statement's address {f['address']}")
    return f


# --- R191: the registry ---------------------------------------------------------------------------

def load_registry(path: Path = REGISTRY) -> dict:
    if not path.exists():
        return {"entrants": [], "withdrawals": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.setdefault("entrants", [])
    doc.setdefault("withdrawals", [])
    return doc


def active_entrants(doc: dict) -> list[dict]:
    """The newest entry of every address entered more times than withdrawn, in the order of each address's first entry."""
    out = {}
    for e in doc["entrants"]:
        n_in = sum(1 for x in doc["entrants"] if x["address"] == e["address"])
        n_out = sum(1 for x in doc["withdrawals"] if x["address"] == e["address"])
        if n_in > n_out:
            out[e["address"]] = e
    return list(out.values())


def verify_registry(doc: dict, settled_sha256: str) -> None:
    """S119: every entry and withdrawal still verifies by its own bytes."""
    for kind, want in (("entrants", False), ("withdrawals", True)):
        for e in doc[kind]:
            try:
                raw = e["statement"].encode("utf-8")
                f = verify_statement(raw, e["signature"], settled_sha256)
            except (AdapterError, KeyError) as exc:
                raise AdapterError(f"S119: a registry entry no longer verifies ({e.get('address')}): {exc}") from exc
            if f["withdrawal"] != want or f["address"] != e["address"] or aib.sha256_bytes(raw) != e.get("statement_sha256") \
                    or (not want and (f["model"] != e.get("model") or e.get("class") != "AGENT")):
                raise AdapterError(f"S119: a registry entry does not match its own statement ({e.get('address')})")


def enter(doc: dict, raw: bytes, signature_hex: str, date: str, settled_sha256: str, withdrawal: bool = False) -> tuple[dict, str]:
    """Pure. Returns (the new registry, 'ENTERED' | 'ALREADY ENTERED' | 'WITHDRAWN'); S118 refuses."""
    if not _DAY.match(date):
        raise AdapterError(f"S118: the date {date!r} is not YYYY-MM-DD")
    f = verify_statement(raw, signature_hex, settled_sha256)
    if f["withdrawal"] != withdrawal:
        raise AdapterError("S118: the statement's heading is not the one this command enters")
    is_active = any(e["address"] == f["address"] for e in active_entrants(doc))
    new = json.loads(json.dumps(doc))
    row = {"address": f["address"], "date": date, "statement": raw.decode("utf-8"), "statement_sha256": aib.sha256_bytes(raw),
           "signature": signature_hex.strip().lower()}
    if withdrawal:
        if not is_active:
            raise AdapterError(f"S118: {f['address']} is not entered; there is nothing to withdraw")
        new["withdrawals"].append(row)
        return new, "WITHDRAWN"
    if is_active:
        return doc, "ALREADY ENTERED"
    new["entrants"].append({"address": f["address"], "model": f["model"], "class": "AGENT", **{k: row[k] for k in ("date", "statement", "statement_sha256", "signature")}})
    return new, "ENTERED"


def registry_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


# --- R198: the asks -------------------------------------------------------------------------------

def load_asks(path: Path = ASKS) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n")):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"S120: asks line {i} is not a JSON row") from exc
        check_ask(r)
        rows.append(r)
    return rows


def check_ask(r: dict) -> None:
    for k in ("date", "to", "channel", "operator_word"):
        if not isinstance(r.get(k), str) or not r[k].strip():
            raise AdapterError(f"S120: an asks row needs a non-empty {k!r}; the count is never inferred")
    if not _DAY.match(r["date"]):
        raise AdapterError(f"S120: an asks row's date {r['date']!r} is not YYYY-MM-DD")


def kill_line(n_asks: int, n_outside: int, n_outside_full_complete: int) -> dict:
    if n_outside_full_complete >= CLEAR_ROWS:
        word = "CLEARED"
    elif n_asks >= KILL_ASKS and n_outside == 0:
        word = "CLOSED"
    else:
        word = "OPEN"
    line = {"CLEARED": f"CLEARED: {n_outside_full_complete} outside AGENT rows with coverage FULL over a complete window (the next rung is an amendment and the operator's word)",
            "CLOSED": f"CLOSED: {n_asks} asks, 0 outside entrants (nobody outside wants this grade; a new prereg reopens it)",
            "OPEN": f"OPEN {n_asks} of {KILL_ASKS}: {n_outside} outside entrants, {n_outside_full_complete} of {CLEAR_ROWS} outside FULL rows over a complete window"}[word]
    return {"word": word, "asks": n_asks, "kill_at_asks": KILL_ASKS, "outside_entrants": n_outside,
            "outside_full_complete_rows": n_outside_full_complete, "clear_at_rows": CLEAR_ROWS, "line": line}


# --- R193 / R194: trips per coin, crossings ------------------------------------------------------

def _tid_key(f: dict):
    t = f.get("tid")
    return (0, t) if isinstance(t, int) else (1, str(t))


def trips_by_coin(fills: list[dict], crossed_tids=frozenset()) -> list[dict]:
    """R193. Per coin, in time order: a trip opens at a fill whose startPosition is 0 and closes at the fill that returns
    the coin's position to 0. Fills met while no trip is open and the position is not 0 belong to a position carried in."""
    by: dict[str, list[dict]] = {}
    for f in fills:
        by.setdefault(str(f["coin"]), []).append(f)
    trips: list[dict] = []
    for coin in sorted(by):
        cur = None
        for f in sorted(by[coin], key=lambda x: (int(x["time"]), _tid_key(x))):
            start = aib._dec(f["startPosition"])
            sz = aib._dec(f["sz"])
            after = start + sz if f["side"] == "B" else start - sz
            if cur is None:
                cur = {"coin": coin, "pnl": Decimal(0), "fees": Decimal(0), "fills": 0, "crossed_fills": 0, "carried_in": start != 0,
                       "first_time_ms": int(f["time"]), "txs": []}
            cur["pnl"] += aib._dec(f["closedPnl"])
            cur["fees"] += aib._dec(f["fee"])
            cur["fills"] += 1
            cur["crossed_fills"] += 1 if f.get("tid") in crossed_tids else 0
            cur["last_time_ms"] = int(f["time"])
            cur["txs"].append(f.get("hash"))
            if after == 0:
                cur["closed"] = True
                cur["net"] = cur["pnl"] - cur["fees"]
                trips.append(cur)
                cur = None
        if cur is not None:
            cur["closed"] = False
            cur["net"] = None
            trips.append(cur)
    return trips


def trip_stats(fills: list[dict], crossed_tids=frozenset()) -> dict:
    """The venue's columns from R193's trips. Only trips opened AND closed inside the pages count; the rest are counted, never valued."""
    trips = trips_by_coin(fills, crossed_tids)
    counted = [t for t in trips if t["closed"] and not t["carried_in"]]
    nets = [t["net"] for t in counted]
    wins = sum(1 for n in nets if n > 0)
    crossed = [t for t in counted if t["crossed_fills"]]
    return {
        "trades": len(counted), "wins": wins, "win_rate": (wins / len(counted)) if counted else None,
        "biggest_win": format(max(nets), "f") if nets else None, "biggest_loss": format(min(nets), "f") if nets else None,
        "trip_net": format(sum(nets, Decimal(0)), "f"),
        "trip_net_uncrossed": format(sum((t["net"] for t in counted if not t["crossed_fills"]), Decimal(0)), "f"),
        "crossed_trips": len(crossed), "crossed_fills": sum(1 for f in fills if f.get("tid") in crossed_tids),
        "fees": format(sum((aib._dec(f["fee"]) for f in fills), Decimal(0)), "f"), "fills": len(fills),
        "coins": sorted({str(f["coin"]) for f in fills}),
        "carried_in_positions_closed": sum(1 for t in trips if t["closed"] and t["carried_in"]),
        "carried_in_positions_open": sum(1 for t in trips if not t["closed"] and t["carried_in"]),
        "open_trips_at_window_end": sum(1 for t in trips if not t["closed"] and not t["carried_in"]),
    }


def crossings(fills_by_address: dict[str, list[dict]]) -> dict:
    """R194. A tid on the pages of two addresses is a crossing. Returns the census and, per address, its crossed tids and counterparts."""
    owners: dict = {}
    n_fills = 0
    for addr in sorted(fills_by_address):
        for f in fills_by_address[addr]:
            n_fills += 1
            if f.get("tid") is not None:
                owners.setdefault(f["tid"], set()).add(addr)
    shared = {t: a for t, a in owners.items() if len(a) > 1}
    by_addr: dict[str, dict] = {}
    pairs: dict[tuple, int] = {}
    for t, addrs in shared.items():
        for a in addrs:
            d = by_addr.setdefault(a, {"tids": set(), "with": set()})
            d["tids"].add(t)
            d["with"].update(x for x in addrs if x != a)
        key = tuple(sorted(addrs))
        pairs[key] = pairs.get(key, 0) + 1
    return {"fill_rows": n_fills, "distinct_tids": len(owners), "crossings": len(shared), "addresses_with_a_crossing": len(by_addr),
            "largest_pairs": [{"addresses": list(k), "crossings": v} for k, v in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
            "by_address": by_addr}


def agent_status(window_complete: bool, coverage: str, net_with_funding: str | None, stats: dict | None) -> str:
    """R195."""
    if not window_complete:
        return "OPEN"
    if coverage in ("PARTIAL", "REFUSED"):
        return "UNDECIDED"
    if coverage == "FULL" and stats is not None and stats["trades"] >= 1 and net_with_funding is not None \
            and Decimal(net_with_funding) > 0 and Decimal(stats["trip_net"]) > 0 and Decimal(stats["trip_net_uncrossed"]) > 0:
        return "KEEP"
    return "DROP"


# --- the door -------------------------------------------------------------------------------------

def _window_fills(cap_dir: Path, crow: dict, t0: int, t1: int) -> list[dict]:
    try:
        items = aib._read_pages(cap_dir / crow["fills_file"], crow.get("fills_pages") or [])
    except AdapterError as exc:
        raise AdapterError(str(exc).replace("S102", "S119")) from exc
    return [f for f in items if t0 <= int(f["time"]) <= t1]


def _cohort(cohort: str, files: dict, as_of: str) -> dict:
    arena = json.loads(files["arena"].read_text(encoding="utf-8"))
    cap = json.loads(files["capture"].read_text(encoding="utf-8"))
    if arena.get("as_of", "") > as_of:
        raise AdapterError(f"S119: cohort {cohort}: the arena file is as of {arena.get('as_of')}, later than the door's {as_of}")
    window = arena["window"]
    t0, t1 = int(window["t0_ms"]), int(window["t1_ms"])
    cap_dir = files["capture"].parent
    crows = {r["address"]: r for r in cap.get("rows", [])}
    arows = {r["address"]: r for r in arena.get("rows", [])}
    rec = arena.get("record_row") or {}
    if rec.get("address"):
        arows.setdefault(rec["address"], rec)
    present = sum(1 for r in crows.values() if (cap_dir / r["fills_file"]).exists())
    on_branch = bool(crows) and present == len(crows)
    out = {"cohort_date": cohort, "arena_file": files["arena"].name, "capture_file": files["capture"].name,
           "capture_sha256": aib.sha256_file(files["capture"]), "arena_as_of": arena.get("as_of"),
           "window": {"t0_date": window.get("t0_date"), "t1_date": window.get("t1_date"), "complete": bool(window.get("complete"))},
           "addresses": len(crows), "fills_files_on_branch": present, "pages_on_branch": on_branch,
           "_arows": arows, "_crows": crows, "_fills": None, "_cross": None}
    if on_branch:
        fills = {a: _window_fills(cap_dir, r, t0, t1) for a, r in sorted(crows.items())}
        cross = crossings(fills)
        out["_fills"], out["_cross"] = fills, cross
        out["census"] = {k: cross[k] for k in ("fill_rows", "distinct_tids", "crossings", "addresses_with_a_crossing", "largest_pairs")}
        full = [a for a, r in sorted(arows.items()) if r.get("status") == "FULL" and a in fills]
        keep, closed_trips = [], 0
        for a in full:
            st = trip_stats(fills[a], frozenset(cross["by_address"].get(a, {}).get("tids", ())))
            closed_trips += st["trades"]
            if agent_status(out["window"]["complete"], "FULL", arows[a].get("net_with_funding"), st) == "KEEP":
                keep.append(a)
        out["board_under_r195"] = {"what": "the cohort's FULL board rows read by R195's words; not rows of the door: none of these addresses enrolled",
                                   "full_rows": len(full), "trips_opened_and_closed_in_window": closed_trips, "would_read_keep": len(keep), "addresses": keep}
    else:
        out["census"] = None
        out["board_under_r195"] = None
        out["not_computed"] = f"pages not on the branch ({present} of {len(crows)} fills files); the census and the trips are not computed"
    return out


def _coverage(arow: dict) -> str:
    return arow.get("coverage") or arow.get("status") or "REFUSED"


def door(as_of: str, arena_dir: Path = ARENA_DIR, registry_path: Path = REGISTRY, asks_path: Path | None = None,
         settled_path: Path = SETTLED) -> dict:
    if not _DAY.match(as_of):
        raise AdapterError(f"as_of {as_of!r} is not a YYYY-MM-DD date")
    asks_path = asks_path if asks_path is not None else (arena_dir / "door" / "asks.jsonl")
    sha = settled_sha(settled_path)
    reg = load_registry(registry_path)
    verify_registry(reg, sha)
    asks = [a for a in load_asks(asks_path) if a["date"] <= as_of]
    entrants = [e for e in active_entrants(reg) if e["date"] <= as_of]
    cohorts = [_cohort(c, files, as_of) for c, files in sorted(aib.newest_cohorts(arena_dir).items())]
    rows, not_captured = [], []
    for e in entrants:
        addr, seen = e["address"], False
        for c in cohorts:
            arow = c["_arows"].get(addr)
            if arow is None or addr not in c["_crows"]:
                continue
            seen = True
            cov = _coverage(arow)
            stats = None
            cross_with: list[str] = []
            if c["pages_on_branch"]:
                ca = c["_cross"]["by_address"].get(addr, {"tids": set(), "with": set()})
                stats = trip_stats(c["_fills"][addr], frozenset(ca["tids"]))
                cross_with = sorted(ca["with"])
            rows.append({
                "klass": "AGENT", "model": e["model"], "model_is": "self-declared", "address": addr, "entered": e["date"],
                "outside": addr != RECORD_ADDRESS, "cohort_date": c["cohort_date"], "window": c["window"], "coverage": cov,
                "status": TRIPS_NOT_COMPUTED if (stats is None and cov == "FULL" and c["window"]["complete"])
                else agent_status(c["window"]["complete"], cov, arow.get("net_with_funding"), stats),
                "total_pnl": arow.get("net_with_funding"), "realized_ex_funding": arow.get("realized_ex_funding"), "funding": arow.get("funding"),
                "roi": ROI_NOT_COMPUTED, "trips": stats, "trips_not_computed": None if stats is not None else c.get("not_computed"),
                "crossed_with": cross_with, "sentence": ROW_SENTENCE,
                "pins": {"capture": c["capture_file"], "capture_sha256": c["capture_sha256"], "arena_file": c["arena_file"],
                         "statement_sha256": e["statement_sha256"]},
            })
        if not seen:
            not_captured.append({"address": addr, "model": e["model"], "model_is": "self-declared", "entered": e["date"], "status": NOT_CAPTURED,
                                 "outside": addr != RECORD_ADDRESS})
    ranked = sorted((r for r in rows if r["trips"] and r["trips"]["trades"] >= 1), key=lambda r: (r["cohort_date"], -Decimal(r["total_pnl"]), r["address"]))
    per_cohort: dict[str, int] = {}
    for r in rows:
        r["rank"] = None
    for r in ranked:
        per_cohort[r["cohort_date"]] = per_cohort.get(r["cohort_date"], 0) + 1
        r["rank"] = per_cohort[r["cohort_date"]]
    for r in rows:
        r["rank_of"] = per_cohort.get(r["cohort_date"], 0)
    outside = [e for e in entrants if e["address"] != RECORD_ADDRESS]
    cleared = len({r["address"] for r in rows if r["outside"] and r["coverage"] == "FULL" and r["window"]["complete"]})
    counts = {w: sum(1 for r in rows if r["status"] == w) for w in ("KEEP", "DROP", "UNDECIDED", "OPEN", TRIPS_NOT_COMPUTED)}
    return {
        "kind": DOOR_KIND, "as_of": as_of, "endpoint": ENDPOINT, "columns": COLUMNS, "settled_sha256": sha,
        "registry": {"file": registry_path.name, "sha256": aib.sha256_file(registry_path) if registry_path.exists() else None,
                     "entered": len(reg["entrants"]), "withdrawn": len(reg["withdrawals"]), "active_as_of": len(entrants), "outside": len(outside)},
        "how_to_enter": {
            "statement": statement_text("<your address: 0x + 40 lower-case hex>", "<your label, 1 to 64 printable ASCII characters>", sha),
            "sign": "EIP-191 personal_sign over the statement's exact bytes (six LF-terminated lines, UTF-8, no byte order mark) with the address's own key",
            "send": "the statement and the 0x signature, by any channel, to the operator; the check is `python -m rights_events.arena_door enrol`, offline, and anyone can run it",
            "then": "the address is graded from the first capture after its entry; until then it reads " + NOT_CAPTURED,
            "leave": "the same six lines with the withdrawal heading and last line, signed by the same key; rows already pinned stand"},
        "rows": sorted(rows, key=lambda r: (r["cohort_date"], r["rank"] if r["rank"] is not None else 10**6, r["address"])),
        "not_yet_captured": not_captured, "counts": counts,
        "cohorts": [{k: v for k, v in c.items() if not k.startswith("_")} for c in cohorts],
        "kill_line": kill_line(len(asks), len(outside), cleared),
        "asks": [{"date": a["date"], "to": a["to"], "channel": a["channel"]} for a in asks],
        "rules": {"R191": "an address enters by its own signed statement; the proof is the arithmetic, not anyone's word",
                  "R193": "SETTLED.md's figures as the arena's row carries them, beside round trips per coin opened and closed inside the window; carried-in and open positions counted, never valued",
                  "R194": "a trade id on the pinned pages of two addresses of one capture is a crossing: disclosed, never by itself a finding",
                  "R195": "KEEP = complete window, FULL, >= 1 closed trip, net with funding > 0, trip net > 0, trip net uncrossed > 0; DROP = every other complete FULL row and NONE; UNDECIDED = PARTIAL or REFUSED; OPEN = window not complete",
                  "R196": ROW_SENTENCE,
                  "R198": f"a shot is one ask delivered, entered only by the operator's quoted word; CLOSED at {KILL_ASKS} asks with 0 outside entrants; CLEARED at {CLEAR_ROWS} outside FULL rows over a complete window"},
        "what_is_not_claimed": "No badge, no rank on the venue, no return, no price, no finding about anyone's skill or about who trades from an address. A door, a grader and the files they read.",
    }


def _cells(r: dict) -> list[str]:
    t = r["trips"]
    rk = f"{r['rank']} of {r['rank_of']}" if r.get("rank") else f"— of {r.get('rank_of', 0)}"
    who = f"{r['model']} (self-declared) · {r['address']} · window {r['window']['t0_date']} … {r['window']['t1_date']} · {r['coverage']} · {r['status']}"
    if t is None:
        return [rk, who, f"{r['total_pnl']} USD", r["roi"], "not computed", "not computed", "not computed", "not computed", "not computed"]
    wr = f"{t['win_rate']:.4f} ({t['wins']}/{t['trades']})" if t["trades"] else "—"
    return [rk, who, f"{r['total_pnl']} USD", r["roi"], wr, (t["biggest_win"] + " USD") if t["biggest_win"] is not None else "—",
            (t["biggest_loss"] + " USD") if t["biggest_loss"] is not None else "—", str(t["trades"]), t["fees"] + " USD"]


def render_markdown(m: dict) -> str:
    out = [f"# The door as of {m['as_of']} (PREREG A44)", "",
           f"Any HyperLiquid address may enrol itself to be graded under SETTLED.md `{m['settled_sha256'][:16]}…`. "
           f"Entered {m['registry']['entered']}, withdrawn {m['registry']['withdrawn']}, active {m['registry']['active_as_of']}, outside {m['registry']['outside']}. "
           f"Endpoint `{m['endpoint']}`.", "",
           f"**Kill line (R198).** {m['kill_line']['line']}.", "",
           "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in m["rows"]:
        out.append("| " + " | ".join(_cells(r)) + " |")
    if not m["rows"]:
        out.append("| — | no entrant is graded | — | — | — | — | — | — | — |")
    out.append("")
    for r in m["rows"]:
        t = r["trips"]
        if t is not None:
            out.append(f"- {r['address']} cohort {r['cohort_date']}: trip net {t['trip_net']} USD, trip net uncrossed {t['trip_net_uncrossed']} USD, crossed fills {t['crossed_fills']}, "
                       f"crossed trips {t['crossed_trips']}, crossed with {', '.join(r['crossed_with']) or 'no graded address'}; carried-in positions closed {t['carried_in_positions_closed']}, "
                       f"still open {t['carried_in_positions_open']}, trips open at the window's end {t['open_trips_at_window_end']}. {r['sentence']}")
        else:
            out.append(f"- {r['address']} cohort {r['cohort_date']}: trips {r['trips_not_computed']}. {r['sentence']}")
    for x in m["not_yet_captured"]:
        out.append(f"- {x['address']} ({x['model']}, self-declared), entered {x['entered']}: {x['status']}.")
    out += ["", "## The census of crossings (R194)", ""]
    for c in m["cohorts"]:
        if c["census"] is None:
            out.append(f"- cohort {c['cohort_date']} (window {c['window']['t0_date']} … {c['window']['t1_date']}): {c['not_computed']}.")
            continue
        s, b = c["census"], c["board_under_r195"]
        out.append(f"- cohort {c['cohort_date']} (window {c['window']['t0_date']} … {c['window']['t1_date']}, {c['addresses']} addresses): {s['fill_rows']} fill rows in the window, "
                   f"{s['distinct_tids']} distinct trade ids, **{s['crossings']} crossings** on {s['addresses_with_a_crossing']} addresses. "
                   f"The board's {b['full_rows']} FULL rows hold {b['trips_opened_and_closed_in_window']} trips opened and closed inside the window; "
                   f"R195 would read KEEP on {b['would_read_keep']} of them (not rows of the door: none enrolled).")
    out += ["", "## How to enter (R191, R192)", "", "Sign these six lines, with your address and your label in place, using the address's own key:", "", "```",
            m["how_to_enter"]["statement"].rstrip("\n"), "```", "",
            f"- Sign: {m['how_to_enter']['sign']}.", f"- Send: {m['how_to_enter']['send']}.", f"- Then: {m['how_to_enter']['then']}.",
            f"- Leave: {m['how_to_enter']['leave']}.", "",
            "Rules: " + "; ".join(f"**{k}** {v}" for k, v in m["rules"].items()), "", m["what_is_not_claimed"]]
    return "\n".join(out) + "\n"


def door_json(m: dict) -> str:
    return json.dumps(m, indent=2, ensure_ascii=False) + "\n"


def write_door(m: dict, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = door_json(m).encode("utf-8")
    paths = {"json": out_dir / f"door_{m['as_of']}.json", "md": out_dir / f"door_{m['as_of']}.md", "latest": out_dir / "door_latest.json"}
    paths["json"].write_bytes(js)
    paths["md"].write_bytes(render_markdown(m).encode("utf-8"))
    paths["latest"].write_bytes(js)
    return {k: aib.sha256_file(p) for k, p in paths.items()}


def check_latest(door_dir: Path = DOOR_DIR) -> str:
    dated = sorted(p for p in door_dir.glob("door_*.json") if _DOOR_FILE.match(p.name))
    if not dated:
        raise AdapterError("S119: no dated door file")
    latest = door_dir / "door_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        raise AdapterError(f"S119: door_latest.json is not byte-equal to {dated[-1].name}")
    return dated[-1].name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.arena_door", description="The door (PREREG A44). Pure; no network.")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("door")
    d.add_argument("--as-of", required=True)
    d.add_argument("--arena-dir", default=str(ARENA_DIR))
    d.add_argument("--registry", default=None)
    d.add_argument("--out-dir", default=None)
    d.add_argument("--settled", default=str(SETTLED))
    for name in ("enrol", "withdraw"):
        e = sub.add_parser(name)
        e.add_argument("--statement", required=True, help="the file holding the statement's exact bytes")
        e.add_argument("--signature", required=True)
        e.add_argument("--date", required=True, help="the date of the commit that enters it")
        e.add_argument("--registry", default=str(REGISTRY))
        e.add_argument("--settled", default=str(SETTLED))
    t = sub.add_parser("template")
    t.add_argument("--address", required=True)
    t.add_argument("--model", required=True)
    t.add_argument("--withdrawal", action="store_true")
    t.add_argument("--settled", default=str(SETTLED))
    k = sub.add_parser("ask")
    k.add_argument("--date", required=True)
    k.add_argument("--to", required=True)
    k.add_argument("--channel", required=True)
    k.add_argument("--operator-word", required=True, help="the operator's own written words that this ask was delivered (S120)")
    k.add_argument("--asks", default=str(ASKS))
    c = sub.add_parser("check-latest")
    c.add_argument("--door-dir", default=str(DOOR_DIR))
    a = p.parse_args(argv)
    try:
        if a.cmd == "door":
            arena_dir = Path(a.arena_dir)
            m = door(a.as_of, arena_dir, Path(a.registry) if a.registry else arena_dir / "entrants.json", None, Path(a.settled))
            out_dir = Path(a.out_dir) if a.out_dir else arena_dir / "door"
            shas = write_door(m, out_dir)
            check_latest(out_dir)
            print(f"THE DOOR as of {m['as_of']}: active {m['registry']['active_as_of']} (outside {m['registry']['outside']}), rows {len(m['rows'])}, "
                  f"not yet captured {len(m['not_yet_captured'])}; {m['kill_line']['line']}")
            for co in m["cohorts"]:
                print(f"  cohort {co['cohort_date']}: " + (f"crossings {co['census']['crossings']} of {co['census']['distinct_tids']} trade ids; board FULL {co['board_under_r195']['full_rows']}, "
                      f"trips in window {co['board_under_r195']['trips_opened_and_closed_in_window']}, would read KEEP {co['board_under_r195']['would_read_keep']}" if co["census"] else co["not_computed"]))
            for r in m["rows"]:
                print("  " + " | ".join(_cells(r)))
            for kk, v in shas.items():
                print(f"  {kk} sha256 {v}")
        elif a.cmd in ("enrol", "withdraw"):
            reg_path = Path(a.registry)
            doc = load_registry(reg_path)
            new, word = enter(doc, Path(a.statement).read_bytes(), a.signature, a.date, settled_sha(Path(a.settled)), withdrawal=a.cmd == "withdraw")
            if word != "ALREADY ENTERED":
                reg_path.write_bytes(registry_json(new).encode("utf-8"))
            f = parse_statement(Path(a.statement).read_bytes())
            print(f"{word}: {f['address']} ({f['model']}, self-declared); registry {reg_path.name}")
        elif a.cmd == "template":
            sys.stdout.write(statement_text(a.address, a.model, settled_sha(Path(a.settled)), a.withdrawal))
        elif a.cmd == "ask":
            row = {"date": a.date, "to": a.to, "channel": a.channel, "operator_word": a.operator_word}
            check_ask(row)
            path = Path(a.asks)
            prior = load_asks(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in prior + [row])).encode("utf-8"))
            print(f"ASK {len(prior) + 1} of {KILL_ASKS} entered: {a.date}, to {a.to}, by {a.channel}")
        else:
            print(f"latest = {check_latest(Path(a.door_dir))}")
    except AdapterError as exc:
        print(f"REFUSED {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
