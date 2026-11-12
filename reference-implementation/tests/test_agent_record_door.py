"""A44 / P36 gates: THE DOOR.

R191 the proof is arithmetic (keccak-256 against its published vectors and, through the same permutation, against
hashlib's SHA3-256; secp256k1 recovery against signatures made by an independent library and pasted here as bytes);
R192 the statement's fixed words and every refusal (S118); the registry's enter / already / withdraw and S119;
R193 trips per coin, carried-in positions counted and never valued, the record's cohort-1 row from the pinned pages;
R194 crossings and the census of cohort 1 (373); R195 the status words, a self-cross reads DROP, and the limit R196
states (a counterpart outside the graded set is not seen); R198 the kill line's words and S120; R197 pure, the latest
pointer byte-equal, the shipped registry and the shipped door file. Offline.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from rights_events import arena_ai_board as aib
from rights_events import arena_door as d
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_ARENA = _ROOT / "rights_events" / "fixtures" / "agent_record" / "arena"
SHA = "c6b590de2289de698053a203e22941bafd55e558f0d5947ac8a4b40274042878"      # SETTLED.md, ratified 2026-11-04
A1 = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"                              # a published test key's address; no funds
A2 = "0x70997970c51812dc3a010c7d01b50e0d17dc79c8"                              # a second published test key's address
# Signatures made on 2026-11-12 by eth_account 0.13.7 (not by this module) over statement_text(...) below.
SIG_ENROL_1 = "0xf81ba717305c251623f858a72ee727e37ba86e07730956f069bc976ba7b4500a1b4b6f41a36b34f12e86ea1f774bf662af0dfe6a5fc488fb06ceada17feb44a61b"
SIG_WITHDRAW_1 = "0x1a82c76d71eeb9e8feb863573b05dd62e80455d57842a89a09221d68448871c219d4302e06d0a29b57da85386cdd5868bf68c15a846e8bdfd9025a1b81fc88251c"
SIG_ENROL_2 = "0xba92546ee0357d51953a61df9510a2f1665f6fd56dda862b13e5e6e7c4e57e9c6837249068761c7f23e1e8a0c789c5c59ae2745eb9872379d174ca76d2e86f0f1b"
ST1 = d.statement_text(A1, "gate-agent v1", SHA).encode("utf-8")
ST1_OUT = d.statement_text(A1, "gate-agent v1", SHA, withdrawal=True).encode("utf-8")
ST2 = d.statement_text(A2, "gate-agent two", SHA).encode("utf-8")
EMPTY = {"entrants": [], "withdrawals": []}
T0, T1 = 1_000_000, 9_000_000


def _refused(code, fn, *a, **k):
    with pytest.raises(AdapterError) as e:
        fn(*a, **k)
    assert str(e.value).startswith(code), str(e.value)


# --- R191: the arithmetic ------------------------------------------------------------------------

def test_keccak256_published_vectors_and_the_permutation_against_sha3():
    assert d.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert d.keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    for n in list(range(0, 140)) + [271, 272, 273, 407, 408, 409, 1000]:
        data = bytes((i * 7 + n) % 256 for i in range(n))
        assert d.sponge256(data, 0x06) == hashlib.sha3_256(data).digest(), n


def test_the_curve_is_secp256k1():
    assert (d.G[1] ** 2 - d.G[0] ** 3 - 7) % d.P == 0
    assert d.ec_add(d.ec_mul(d.N - 1, d.G), d.G) is None
    assert d.address_of_point(d.ec_mul(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80, d.G)) == A1


def test_signatures_made_elsewhere_recover_to_their_addresses():
    assert d.recover_address(ST1, SIG_ENROL_1) == A1
    assert d.recover_address(ST1_OUT, SIG_WITHDRAW_1) == A1
    assert d.recover_address(ST2, SIG_ENROL_2) == A2
    assert d.verify_statement(ST1, SIG_ENROL_1, SHA) == {"address": A1, "model": "gate-agent v1", "settled_sha256": SHA, "withdrawal": False}
    low_v = SIG_ENROL_1[:-2] + "00"                     # v as 0/1 is the same signature
    assert d.recover_address(ST1, low_v) == A1


def test_one_changed_byte_is_refused():
    changed = d.statement_text(A1, "gate-agent v2", SHA).encode("utf-8")
    _refused("S118", d.verify_statement, changed, SIG_ENROL_1, SHA)
    flipped = SIG_ENROL_1[:10] + ("0" if SIG_ENROL_1[10] != "0" else "1") + SIG_ENROL_1[11:]
    _refused("S118", d.verify_statement, ST1, flipped, SHA)
    _refused("S118", d.verify_statement, ST1, SIG_ENROL_2, SHA)                 # another key's signature
    _refused("S118", d.verify_statement, ST2, SIG_ENROL_1, SHA)                 # a statement naming an address the key is not
    _refused("S118", d.recover_address, ST1, SIG_ENROL_1[:-2] + "1d")           # v = 29
    _refused("S118", d.recover_address, ST1, SIG_ENROL_1[:-2])                  # short
    _refused("S118", d.recover_address, ST1, "0x" + "00" * 64 + "1b")           # r = s = 0


# --- R192: the fixed words -----------------------------------------------------------------------

def test_statement_is_six_fixed_lines():
    assert ST1.decode() == ("PROOF OF OUTCOME ARENA: ENROLMENT\n" f"address: {A1}\n" "model: gate-agent v1\n" f"settled_sha256: {SHA}\n"
                            "registry: arena/entrants.json\n" "statement: grade this address by what settled on chain; I claim nothing else.\n")
    assert ST1_OUT.decode().splitlines()[0] == "PROOF OF OUTCOME ARENA: WITHDRAWAL"
    assert ST1_OUT.decode().splitlines()[5] == "statement: stop grading this address; rows already pinned stand."
    assert d.parse_statement(ST1_OUT)["withdrawal"] is True


@pytest.mark.parametrize("raw", [
    ST1.replace(b"\n", b"\r\n"),
    b"\xef\xbb\xbf" + ST1,
    ST1 + b"\n",
    ST1[:-1],
    b"\n".join(ST1.split(b"\n")[:5]) + b"\n",
    ST1.replace(A1.encode(), A1.upper().replace("0X", "0x").encode()),
    ST1.replace(b"gate-agent v1", b"x" * 65),
    ST1.replace(b"model: gate-agent v1", b"model: "),
    ST1.replace(b"gate-agent v1", "café".encode("utf-8")),
    ST1.replace(b"I claim nothing else.", b"I claim a badge."),
    ST1.replace(b"registry: arena/entrants.json", b"registry: arena/copiers.json"),
    ST1.replace(b"address: ", b"model: ", 1),
    ST1.replace(b"ENROLMENT", b"ENROLLMENT"),
    ST1.replace(SHA.encode(), SHA[:63].encode()),
    b"\xff\xfe",
])
def test_statement_refusals(raw):
    _refused("S118", d.parse_statement, raw)


def test_a_statement_for_another_objective_is_refused():
    other = "0" * 64
    _refused("S118", d.verify_statement, ST1, SIG_ENROL_1, other)
    assert d.settled_sha() == SHA


# --- R191: the registry --------------------------------------------------------------------------

def test_enter_already_withdraw_and_enter_again():
    doc, word = d.enter(EMPTY, ST1, SIG_ENROL_1, "2026-11-12", SHA)
    assert word == "ENTERED" and EMPTY == {"entrants": [], "withdrawals": []}            # pure
    e = doc["entrants"][0]
    assert (e["address"], e["model"], e["class"], e["date"]) == (A1, "gate-agent v1", "AGENT", "2026-11-12")
    assert e["statement"].encode() == ST1 and e["statement_sha256"] == hashlib.sha256(ST1).hexdigest()
    assert set(e) == {"address", "model", "class", "date", "statement", "statement_sha256", "signature"}   # nothing about the owner
    same, word = d.enter(doc, ST1, SIG_ENROL_1, "2026-11-13", SHA)
    assert word == "ALREADY ENTERED" and same is doc
    doc2, word = d.enter(doc, ST2, SIG_ENROL_2, "2026-11-13", SHA)
    assert word == "ENTERED" and [x["address"] for x in d.active_entrants(doc2)] == [A1, A2]
    out, word = d.enter(doc2, ST1_OUT, SIG_WITHDRAW_1, "2026-11-14", SHA, withdrawal=True)
    assert word == "WITHDRAWN" and [x["address"] for x in d.active_entrants(out)] == [A2] and len(out["entrants"]) == 2
    _refused("S118", d.enter, out, ST1_OUT, SIG_WITHDRAW_1, "2026-11-15", SHA, withdrawal=True)   # nothing to withdraw
    back, word = d.enter(out, ST1, SIG_ENROL_1, "2026-11-16", SHA)
    assert word == "ENTERED" and [x["address"] for x in d.active_entrants(back)] == [A1, A2] and d.active_entrants(back)[0]["date"] == "2026-11-16"
    d.verify_registry(back, SHA)
    _refused("S118", d.enter, EMPTY, ST1_OUT, SIG_WITHDRAW_1, "2026-11-12", SHA)                   # a withdrawal is not an entry
    _refused("S118", d.enter, EMPTY, ST1, SIG_ENROL_1, "12 Nov", SHA)


def test_a_registry_entry_that_no_longer_verifies_refuses_the_door():
    doc, _ = d.enter(EMPTY, ST1, SIG_ENROL_1, "2026-11-12", SHA)
    for edit in ({"model": "a better label"}, {"address": A2}, {"signature": SIG_ENROL_2}, {"class": "COPIER"},
                 {"statement": ST1.decode().replace("v1", "v9")}):
        bad = json.loads(json.dumps(doc))
        bad["entrants"][0].update(edit)
        _refused("S119", d.verify_registry, bad, SHA)


# --- R193: trips per coin ------------------------------------------------------------------------

def _fill(coin, t, side, sz, start, pnl="0", fee="0.01", tid=None):
    return {"coin": coin, "time": t, "side": side, "sz": str(sz), "startPosition": str(start), "closedPnl": str(pnl), "fee": str(fee),
            "tid": tid if tid is not None else t, "hash": f"0x{t:064x}", "px": "1"}


def test_trips_on_one_coin_equal_the_board_s_round_trips():
    fills = [_fill("BTC", 10, "B", 1, 0), _fill("BTC", 20, "A", 1, 1, "5"), _fill("BTC", 30, "A", 2, 0), _fill("BTC", 40, "B", 1, -2, "-1"),
             _fill("BTC", 50, "B", 1, -1, "-1"), _fill("BTC", 60, "B", 3, 0)]
    mine = d.trips_by_coin(fills)
    theirs = aib.round_trips(fills)
    assert [(t["closed"], t["net"], t["fills"]) for t in mine] == [(t["closed"], t["net"], t["fills"]) for t in theirs]
    st = d.trip_stats(fills)
    assert (st["trades"], st["wins"], st["trip_net"], st["biggest_win"], st["biggest_loss"], st["open_trips_at_window_end"]) == (2, 1, "2.95", "4.98", "-2.03", 1)
    assert st["fees"] == "0.06" and st["win_rate"] == 0.5


def test_trips_are_per_coin_and_a_carried_in_position_is_counted_never_valued():
    fills = [_fill("BTC", 10, "B", 1, 0), _fill("ETH", 15, "A", 5, 5, "100"),          # ETH: closes a position carried into the window
             _fill("ETH", 18, "B", 2, 0), _fill("BTC", 20, "A", 1, 1, "3"),           # BTC trip closes while ETH is open
             _fill("ETH", 25, "A", 2, 2, "-4"), _fill("SOL", 30, "A", 1, 7, "9")]      # SOL: carried in, still open
    st = d.trip_stats(fills)
    assert st["trades"] == 2 and st["trip_net"] == "-1.04"                             # (3 - 0.02) + (-4 - 0.02); the 100 and the 9 are not in it
    assert st["carried_in_positions_closed"] == 1 and st["carried_in_positions_open"] == 1
    assert st["coins"] == ["BTC", "ETH", "SOL"] and st["fills"] == 6
    assert d.trip_stats([])["trades"] == 0 and d.trip_stats([])["trip_net"] == "0" and d.trip_stats([])["win_rate"] is None


def test_the_record_s_cohort_1_row_from_the_pinned_pages():
    cdir = _ARENA / "2026-10-25"
    cap = json.loads((cdir / "capture_ARENA_2026-10-25_2026-11-03.json").read_text(encoding="utf-8"))
    arena = json.loads((cdir / "arena_2026-10-25_2026-11-03.json").read_text(encoding="utf-8"))
    crow = next(r for r in cap["rows"] if r["address"] == d.RECORD_ADDRESS)
    fills = d._window_fills(cdir, crow, int(arena["window"]["t0_ms"]), int(arena["window"]["t1_ms"]))
    st = d.trip_stats(fills)
    assert (st["trades"], st["wins"], st["biggest_win"], st["biggest_loss"], st["trip_net"]) == (2, 1, "0.144370", "-0.067163", "0.077207")
    assert st["trip_net"] == arena["record_row"]["realized_ex_funding"] and st["fees"] == "0.041793"


# --- R194 / R195 / R196 --------------------------------------------------------------------------

def _wash():
    a = [_fill("XYZ", 100, "B", 1, 0, tid=1), _fill("XYZ", 200, "A", 1, 1, "10", tid=2)]
    b = [_fill("XYZ", 100, "A", 1, 0, tid=1), _fill("XYZ", 200, "B", 1, -1, "-10", tid=2)]
    return a, b


def test_a_self_cross_reads_drop_and_the_limit_is_what_r196_says():
    a, b = _wash()
    c = d.crossings({A1: a, A2: b})
    assert c["crossings"] == 2 and c["distinct_tids"] == 2 and c["fill_rows"] == 4 and c["addresses_with_a_crossing"] == 2
    assert c["by_address"][A1]["with"] == {A2} and c["largest_pairs"] == [{"addresses": sorted([A1, A2]), "crossings": 2}]
    sa = d.trip_stats(a, frozenset(c["by_address"][A1]["tids"]))
    assert (sa["trip_net"], sa["trip_net_uncrossed"], sa["crossed_trips"], sa["crossed_fills"]) == ("9.98", "0", 1, 2)
    assert d.agent_status(True, "FULL", "9.98", sa) == "DROP"
    alone = d.crossings({A1: a})                                                        # the counterpart is not graded: the page cannot show it
    assert alone["crossings"] == 0
    assert d.agent_status(True, "FULL", "9.98", d.trip_stats(a)) == "KEEP"
    assert "does not name counterparties" in d.ROW_SENTENCE


def test_status_words():
    win = d.trip_stats([_fill("BTC", 10, "B", 1, 0), _fill("BTC", 20, "A", 1, 1, "5")])
    none = d.trip_stats([])
    assert d.agent_status(False, "FULL", "5", win) == "OPEN"
    assert d.agent_status(True, "PARTIAL", "5", win) == "UNDECIDED" and d.agent_status(True, "REFUSED", None, None) == "UNDECIDED"
    assert d.agent_status(True, "FULL", "4.98", win) == "KEEP"
    assert d.agent_status(True, "FULL", "-1", win) == "DROP"                             # funding took it
    assert d.agent_status(True, "FULL", "0", win) == "DROP"
    assert d.agent_status(True, "FULL", "1000000", none) == "DROP"                       # money with no trip opened and closed in the window
    assert d.agent_status(True, "NONE", "0", none) == "DROP" and d.agent_status(True, "FULL", "5", None) == "DROP"


def test_the_census_of_cohort_1_and_the_board_under_r195():
    m = d.door("2026-11-12", registry_path=_ROOT / "tests" / "no_such_registry.json")
    c1 = next(c for c in m["cohorts"] if c["cohort_date"] == "2026-10-25")
    assert c1["pages_on_branch"] and c1["addresses"] == 81
    assert (c1["census"]["fill_rows"], c1["census"]["distinct_tids"], c1["census"]["crossings"]) == (217285, 216912, 373)
    assert c1["census"]["largest_pairs"][0]["crossings"] == 138
    assert c1["board_under_r195"]["full_rows"] == 8 and c1["board_under_r195"]["would_read_keep"] == 0
    assert c1["board_under_r195"]["trips_opened_and_closed_in_window"] == 0
    assert m["rows"] == [] and m["not_yet_captured"] == [] and m["registry"]["active_as_of"] == 0
    assert m["kill_line"]["line"] == "OPEN 0 of 20: 0 outside entrants, 0 of 3 outside FULL rows over a complete window"
    assert d.door_json(m) == d.door_json(d.door("2026-11-12", registry_path=_ROOT / "tests" / "no_such_registry.json"))   # pure


# --- R198: the kill line -------------------------------------------------------------------------

def test_kill_line_words():
    assert d.kill_line(0, 0, 0)["word"] == "OPEN" and d.kill_line(19, 0, 0)["word"] == "OPEN"
    k = d.kill_line(20, 0, 0)
    assert k["word"] == "CLOSED" and k["line"].startswith("CLOSED: 20 asks, 0 outside entrants")
    assert d.kill_line(20, 1, 0)["word"] == "OPEN" and d.kill_line(40, 2, 2)["word"] == "OPEN"
    assert d.kill_line(3, 3, 3)["word"] == "CLEARED" and d.kill_line(25, 5, 3)["word"] == "CLEARED"
    assert d.kill_line(7, 2, 1)["line"] == "OPEN 7 of 20: 2 outside entrants, 1 of 3 outside FULL rows over a complete window"


def test_an_ask_enters_only_with_the_operator_s_word(tmp_path):
    asks = tmp_path / "door" / "asks.jsonl"
    assert d.load_asks(asks) == []
    assert d.main(["ask", "--date", "2026-11-18", "--to", "the venue", "--channel", "a message", "--operator-word", "", "--asks", str(asks)]) == 1
    assert not asks.exists()
    assert d.main(["ask", "--date", "2026-11-18", "--to", "the venue", "--channel", "a message", "--operator-word", "sent it this morning", "--asks", str(asks)]) == 0
    assert d.main(["ask", "--date", "2026-11-19", "--to", "an agent's operator", "--channel", "a message", "--operator-word", "asked them too", "--asks", str(asks)]) == 0
    rows = d.load_asks(asks)
    assert [r["date"] for r in rows] == ["2026-11-18", "2026-11-19"] and rows[0]["operator_word"] == "sent it this morning"
    asks.write_text(asks.read_text(encoding="utf-8") + '{"date": "2026-11-20", "to": "x", "channel": "y"}\n', encoding="utf-8")
    _refused("S120", d.load_asks, asks)


# --- R197: the door on a synthetic arena ---------------------------------------------------------

def _pages(path: Path, fills: list[dict]) -> list[dict]:
    raw = json.dumps(fills).encode("utf-8")
    with gzip.open(path, "wb") as f:
        f.write(raw + b"\n")
    return [{"line": 0, "sha256": hashlib.sha256(raw).hexdigest()}]


def _arena(tmp_path: Path, book: dict, complete: bool = True, write_pages: bool = True) -> Path:
    """book: address -> (fills, status, net_with_funding). One cohort 2026-12-01 as of 2026-12-09."""
    arena_dir = tmp_path / "arena"
    cdir = arena_dir / "2026-12-01"
    cdir.mkdir(parents=True)
    cap_rows, arena_rows = [], []
    for addr, (fills, status, net) in book.items():
        name = f"hl_fills_{addr}.jsonl.gz"
        pins = _pages(cdir / name, fills)
        if not write_pages:
            (cdir / name).unlink()
        cap_rows.append({"address": addr, "fills_file": name, "fills_pages": pins})
        arena_rows.append({"address": addr, "status": status, "net_with_funding": net, "realized_ex_funding": net, "funding": "0"})
    (cdir / "capture_ARENA_2026-12-01_2026-12-09.json").write_text(json.dumps({"rows": cap_rows}), encoding="utf-8")
    (cdir / "arena_2026-12-01_2026-12-09.json").write_text(json.dumps({
        "as_of": "2026-12-09", "rows": arena_rows, "record_row": {},
        "window": {"t0_ms": T0, "t1_ms": T1, "t0_date": "2026-12-02", "t1_date": "2026-12-08", "complete": complete}}), encoding="utf-8")
    return arena_dir


def _registry(tmp_path: Path, *entries) -> Path:
    doc = EMPTY
    for raw, sig, date in entries:
        doc, _ = d.enter(doc, raw, sig, date, SHA)
    p = tmp_path / "entrants.json"
    p.write_bytes(d.registry_json(doc).encode("utf-8"))
    return p


def _trip(coin, t, pnl, tid0):
    return [_fill(coin, T0 + t, "B", 1, 0, tid=tid0), _fill(coin, T0 + t + 5, "A", 1, 1, pnl, tid=tid0 + 1)]


def test_the_door_grades_an_entrant_and_lists_one_not_yet_captured(tmp_path):
    board_addr = "0x" + "ab" * 20
    arena_dir = _arena(tmp_path, {A1: (_trip("BTC", 10, "5", 1) + _trip("ETH", 20, "-1", 3), "FULL", "3.96"),
                                  board_addr: (_trip("BTC", 30, "2", 7), "FULL", "1.98")})
    reg = _registry(tmp_path, (ST1, SIG_ENROL_1, "2026-12-01"), (ST2, SIG_ENROL_2, "2026-12-03"))
    m = d.door("2026-12-09", arena_dir, reg)
    assert len(m["rows"]) == 1 and m["counts"]["KEEP"] == 1
    r = m["rows"][0]
    assert (r["address"], r["klass"], r["model"], r["model_is"], r["status"], r["coverage"], r["total_pnl"]) == (A1, "AGENT", "gate-agent v1", "self-declared", "KEEP", "FULL", "3.96")
    assert (r["trips"]["trades"], r["trips"]["wins"], r["trips"]["trip_net"], r["trips"]["crossed_fills"]) == (2, 1, "3.96", 0)
    assert r["rank"] == 1 and r["rank_of"] == 1 and r["roi"] == aib.ROI_NOT_COMPUTED and r["sentence"] == d.ROW_SENTENCE and r["outside"] is True
    assert m["not_yet_captured"] == [{"address": A2, "model": "gate-agent two", "model_is": "self-declared", "entered": "2026-12-03",
                                      "status": "LISTED, NOT YET CAPTURED", "outside": True}]
    assert m["kill_line"]["line"] == "OPEN 0 of 20: 2 outside entrants, 1 of 3 outside FULL rows over a complete window"
    assert m["cohorts"][0]["board_under_r195"] == {"what": m["cohorts"][0]["board_under_r195"]["what"], "full_rows": 2,
                                                   "trips_opened_and_closed_in_window": 3, "would_read_keep": 2, "addresses": sorted([A1, board_addr])}
    md =d.render_markdown(m)
    assert "gate-agent v1 (self-declared)" in md and "| 1 of 1 |" in md and "LISTED, NOT YET CAPTURED" in md and "settled_sha256: " + SHA in md
    assert "<script" not in md and all(c in md for c in d.COLUMNS)
    shas = d.write_door(m, tmp_path / "out")
    assert shas["json"] == shas["latest"] and d.check_latest(tmp_path / "out") == "door_2026-12-09.json"
    (tmp_path / "out" / "door_latest.json").write_bytes(b"{}\n")
    _refused("S119", d.check_latest, tmp_path / "out")
    _refused("S119", d.check_latest, tmp_path / "nowhere")


def test_two_entrants_trading_with_each_other_are_both_read_crossed(tmp_path):
    a, b = _wash()
    for f in a + b:
        f["time"] += T0
    arena_dir = _arena(tmp_path, {A1: (a, "FULL", "9.98"), A2: (b, "FULL", "-10.02")})
    reg = _registry(tmp_path, (ST1, SIG_ENROL_1, "2026-12-01"), (ST2, SIG_ENROL_2, "2026-12-01"))
    m = d.door("2026-12-09", arena_dir, reg)
    by = {r["address"]: r for r in m["rows"]}
    assert by[A1]["status"] == "DROP" and by[A2]["status"] == "DROP" and m["counts"]["KEEP"] == 0
    assert by[A1]["crossed_with"] == [A2] and by[A1]["trips"]["crossed_trips"] == 1 and by[A1]["trips"]["trip_net_uncrossed"] == "0"
    assert m["cohorts"][0]["census"]["crossings"] == 2


def test_an_open_window_and_pages_off_the_branch_are_said_not_guessed(tmp_path):
    book = {A1: (_trip("BTC", 10, "5", 1), "FULL", "4.98")}
    reg = _registry(tmp_path, (ST1, SIG_ENROL_1, "2026-12-01"))
    assert d.door("2026-12-09", _arena(tmp_path / "open", book, complete=False), reg)["rows"][0]["status"] == "OPEN"
    m = d.door("2026-12-09", _arena(tmp_path / "off", book, write_pages=False), reg)
    r = m["rows"][0]
    assert r["status"] == "TRIPS NOT COMPUTED" and r["trips"] is None and "pages not on the branch (0 of 1 fills files)" in r["trips_not_computed"]
    assert m["cohorts"][0]["census"] is None and m["counts"]["KEEP"] == 0 and r["rank"] is None
    assert "not computed" in d.render_markdown(m)


def test_a_page_that_does_not_hash_to_its_pin_refuses_the_door(tmp_path):
    arena_dir = _arena(tmp_path, {A1: (_trip("BTC", 10, "5", 1), "FULL", "4.98")})
    with gzip.open(arena_dir / "2026-12-01" / f"hl_fills_{A1}.jsonl.gz", "wb") as f:
        f.write(json.dumps(_trip("BTC", 10, "500", 1)).encode("utf-8") + b"\n")
    _refused("S119", d.door, "2026-12-09", arena_dir, _registry(tmp_path, (ST1, SIG_ENROL_1, "2026-12-01")))
    _refused("S119", d.door, "2026-12-08", _arena(tmp_path / "later", {A1: ([], "NONE", "0")}), tmp_path / "none.json")   # an arena file from the future


def test_the_cli_refuses_and_writes_nothing(tmp_path, capsys):
    st = tmp_path / "statement.txt"
    reg = tmp_path / "entrants.json"
    st.write_bytes(ST1)
    assert d.main(["enrol", "--statement", str(st), "--signature", SIG_ENROL_2, "--date", "2026-11-12", "--registry", str(reg)]) == 1
    assert "REFUSED S118" in capsys.readouterr().out and not reg.exists()
    assert d.main(["enrol", "--statement", str(st), "--signature", SIG_ENROL_1, "--date", "2026-11-12", "--registry", str(reg)]) == 0
    assert f"ENTERED: {A1} (gate-agent v1, self-declared)" in capsys.readouterr().out
    before = reg.read_bytes()
    assert d.main(["enrol", "--statement", str(st), "--signature", SIG_ENROL_1, "--date", "2026-11-13", "--registry", str(reg)]) == 0
    assert "ALREADY ENTERED" in capsys.readouterr().out and reg.read_bytes() == before
    assert d.main(["template", "--address", A1, "--model", "gate-agent v1"]) == 0
    assert capsys.readouterr().out.encode("utf-8").replace(b"\r\n", b"\n") == ST1


# --- what is shipped -----------------------------------------------------------------------------

def test_the_shipped_registry_and_the_shipped_door():
    reg = json.loads((_ARENA / "entrants.json").read_text(encoding="utf-8"))
    assert reg["settled_sha256"] == SHA and reg["opened"] == "2026-11-12"
    d.verify_registry(d.load_registry(_ARENA / "entrants.json"), SHA)
    name = d.check_latest(_ARENA / "door")
    m = json.loads((_ARENA / "door" / name).read_text(encoding="utf-8"))
    assert m["kind"] == "proof_of_outcome_door" and m["settled_sha256"] == SHA and m["columns"] == aib.COLUMNS
    assert d.parse_statement(d.statement_text(A1, "x", m["settled_sha256"]).encode())["address"] == A1
    assert m["how_to_enter"]["statement"].splitlines()[3] == "settled_sha256: " + SHA
    copiers = json.loads((_ARENA / "copiers.json").read_text(encoding="utf-8"))
    assert [c["class"] for c in copiers["copiers"]] == ["COPIER"]                        # R134's registry is another file and is not the door's
