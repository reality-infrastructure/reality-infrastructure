"""THE BOOK OF THE VERDICT (PREREG A37: R145-R150, S105-S106; A38: R151-R158, S107-S108 via arena_gap).

The arena's KEEP set becomes the leader list of one paper fork, F6, identical to F4 in every
other byte (the declared coins, the 30 bps stop, the 5 h gate, the fee and spread charge, one
open episode per fork, the controls C0 and C1, the pass line, the retirement rule). One variable
changes: the list.

  keep    R146  the KEEP list of a completed cohort from the pinned copier's grade (A28), the
                RECORD row excluded, sorted, the feed's sha beside it
  replay  R147  F6 over the channel's pinned fills pages (one HTTP body a line, byte-for-byte,
                deduplicated by tid) against the tape of record's day files; every row
                in_sample: true; decides nothing; disclosed beside F4 and C1 on the same days
  relist  R149  the arena graded by itself: each verdict of the completed cohort counted as
                relisted / FULL / net > 0 in the next cohort, from the pinned feed alone
  ledger  R148  agent_ledger.ledger with family F6: six slots of its own, k_for(6) = 5, never
                merged with the F4 population
  run           all of the above, book_<as_of>.json|.md, book_latest.json and the manifest
  verify  S105  every file the manifest pins hashes to its pin

Pure: no network, no clock, no randomness (S105). Never imports or names a venue write tool
(S106). The book submits nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

from rights_events import agent_ledger as al
from rights_events import arena_gap as ag
from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
BOOK_DIR = _FIXTURES / "book"
FEED_DIR = _FIXTURES / "arena" / "feed"
MARKER_DIR = _FIXTURES / "marker"
VPS_DIR = _FIXTURES / "vps"

FAMILY, BASE_FAMILY, CONTROL = "F6", "F4", "C1"
STATUS_KEEP = "KEEP"
VERDICTS = ("KEEP", "DROP", "UNDECIDED")
REPLAY_SPREAD_BPS_PER_LEG = 1.0
REPLAY_SPREAD_SOURCE = "replay_proxy"
DAY_MS = 86_400_000
KIND_KEEP = "agent_record_book_keep_list"
KIND_BOOK = "agent_record_book"
KIND_MANIFEST = "agent_record_book_manifest"
KIND_RELIST = "agent_record_book_relist"
WHAT_IS_NOT_CLAIMED = ("No forecast, no profit, no status from the replay: F6's and F7's replay rows are in-sample for the "
                       "rule's existence (R147) and decide nothing; only the forward marker's rows enter the "
                       "book's ledger (R148). Funding is excluded from the replay and said so.")


# ----------------------------------------------------------------------------- small helpers
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def day_ms(day: str) -> int:
    import datetime as _dt
    y, m, d = (int(x) for x in day.split("-"))
    return int(_dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp() * 1000)


def day_of(ms: int) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ms / 1000.0, tz=_dt.timezone.utc).strftime("%Y-%m-%d")


def days_between(first: str, last: str) -> list[str]:
    out, ms = [], day_ms(first)
    while ms <= day_ms(last):
        out.append(day_of(ms))
        ms += DAY_MS
    return out


def load_families(path: Path = MARKER_DIR / "families.json") -> dict:
    return json.loads(path.read_bytes())


def _f(x, nd=2) -> str:
    if x is None:
        return "—"
    return f"{x:.{nd}f}"


# ----------------------------------------------------------------------------- R146 the KEEP list
def feed_cohort(feed: dict, cohort_date: str) -> dict:
    for c in feed.get("cohorts") or []:
        if str(c.get("cohort_date")) == cohort_date:
            return c
    raise AdapterError(f"R146: cohort {cohort_date} is not in the feed")


def cohort_rows(feed: dict, cohort_date: str) -> list[dict]:
    """The feed's rows are one flat list tagged by cohort_date (A28)."""
    return [r for r in (feed.get("rows") or []) if isinstance(r, dict) and str(r.get("cohort_date")) == cohort_date]


def _addr(r: dict) -> str:
    return str(r.get("address", "")).split(" ")[0].lower()


def keep_list(feed_path: Path, cohort_date: str, require_complete: bool = True) -> dict:
    """The addresses whose status is KEEP in the copier's grade of `cohort_date`, the RECORD row
    excluded, sorted; a pure function of the pinned feed (R146)."""
    data = feed_path.read_bytes()
    feed = json.loads(data)
    cohort = feed_cohort(feed, cohort_date)
    window = cohort.get("window") or {}
    if require_complete and not window.get("complete", False):
        raise AdapterError(f"R146: cohort {cohort_date}'s window is not complete in {feed_path.name}")
    rows = cohort_rows(feed, cohort_date)
    if not rows:
        raise AdapterError(f"R146: cohort {cohort_date} has no rows in {feed_path.name}")
    excluded = sorted(_addr(r) for r in rows if r.get("status") == STATUS_KEEP and r.get("record"))
    addrs = sorted(_addr(r) for r in rows if r.get("status") == STATUS_KEEP and not r.get("record"))
    return {
        "kind": KIND_KEEP,
        "what": ("R146: the leader list of F6 = the arena's KEEP set of the newest completed cohort, the RECORD row "
                 "excluded (the record does not follow itself), sorted; refreshed once per completed cohort"),
        "cohort_date": cohort_date,
        "window": window,
        "feed_file": feed_path.name,
        "feed_sha256": sha256_bytes(data),
        "feed_as_of": feed.get("as_of"),
        "n_keep_rows": len(addrs) + len(excluded),
        "excluded_record": excluded,
        "addresses": addrs,
    }


# ----------------------------------------------------------------------------- R147 the replay
def _body(line: bytes):
    try:
        v = json.loads(line)
    except ValueError:
        return None
    return v if isinstance(v, list) else None


def read_page_parts(parts: list[Path], index: set[str] | None = None) -> tuple[list[dict], list[dict], dict]:
    """The channel splits one page file into byte chunks under GitHub's limit (A25/A27): the parts
    are joined in name order, then split into lines. One HTTP response body a line (a JSON array
    of fills), byte-for-byte. A line that does not parse but has a suffix from a `[` that parses
    is a torn fragment glued to a whole page (R115's rule): the page is the suffix, the fragment
    is counted and its page is lost. Any other unparsable line is counted and skipped. Fills are
    deduplicated by tid and sorted by (time, tid). Returns (fills, pins, alignment)."""
    fills: dict = {}
    pins = []
    chunks = []
    for p in sorted(parts, key=lambda q: q.name):
        data = p.read_bytes()
        pins.append({"file": p.name, "sha256": sha256_bytes(data), "bytes": len(data)})
        chunks.append(data)
    align = {"lines": 0, "pages": 0, "indexed": 0, "torn_fragments": 0, "lost_pages": 0, "unparsed": 0}
    for line in b"".join(chunks).split(b"\n"):
        if not line.strip():
            continue
        align["lines"] += 1
        body = _body(line)
        if body is None:
            cut = None
            for j in range(1, len(line)):
                if line[j:j + 1] == b"[":
                    cand = _body(line[j:])
                    if cand is not None:
                        cut, body = j, cand
                        break
            if cut is None:
                align["unparsed"] += 1
                continue
            align["torn_fragments"] += 1
            align["lost_pages"] += 1
            line = line[cut:]
        align["pages"] += 1
        if index is not None and sha256_bytes(line) in index:
            align["indexed"] += 1
        for f in body:
            if not isinstance(f, dict):
                continue
            tid = f.get("tid")
            if tid is None:
                tid = ("nameless", f.get("hash"), f.get("time"), f.get("px"), f.get("sz"))
            if tid not in fills:
                fills[tid] = f
    out = sorted(fills.values(), key=lambda f: (int(f.get("time", 0)), str(f.get("tid", ""))))
    return out, pins, align


def read_pages_index(path: Path) -> tuple[dict[str, set[str]], dict | None]:
    """pages_index.jsonl: one row per page the sensor wrote, with the page file's name and the
    page's sha256 -> {file: {sha, ...}}; absent -> ({}, None)."""
    if not path.exists():
        return {}, None
    data = path.read_bytes()
    by: dict[str, set[str]] = {}
    for line in data.split(b"\n"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and "file" in r and "sha256" in r:
            by.setdefault(str(r["file"]), set()).add(str(r["sha256"]))
    return by, {"file": path.name, "sha256": sha256_bytes(data), "rows": sum(len(v) for v in by.values())}


def read_tape(tape_dir: Path, days: list[str], coins: list[str]) -> tuple[dict[str, list[tuple[int, float]]], list[dict]]:
    """The tape of record's day files -> one (ms, mid) path per coin. A line that does not parse
    is counted and skipped (the sensor's torn append), never repaired."""
    paths: dict[str, list[tuple[int, float]]] = {c: [] for c in coins}
    pins = []
    for day in days:
        p = tape_dir / f"tape_MIDS_{day}.jsonl"
        if not p.exists():
            pins.append({"file": p.name, "missing": True})
            continue
        data = p.read_bytes()
        rows = unparsed = 0
        for line in data.split(b"\n"):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                unparsed += 1
                continue
            if not isinstance(r, dict) or "ms" not in r or not isinstance(r.get("mids"), dict):
                unparsed += 1
                continue
            rows += 1
            ms = int(r["ms"])
            for c in coins:
                v = r["mids"].get(c)
                if v is None:
                    continue
                try:
                    paths[c].append((ms, float(v)))
                except (TypeError, ValueError):
                    continue
        pins.append({"file": p.name, "sha256": sha256_bytes(data), "rows": rows, "unparsed_lines": unparsed})
    for c in coins:
        paths[c].sort(key=lambda x: x[0])
    return paths, pins


def f6_signals(fills: list[dict], leader: str, coins: list[str], min_notional: float, t0_ms: int, t1_ms: int, mk) -> list[dict]:
    """F4's signal (marker.f4_leader_opens) over a KEEP address, relabelled F6, entries inside the window (R145)."""
    out = []
    for coin in coins:
        for s in mk.f4_leader_opens(fills, min_notional, coin, leader):
            if t0_ms <= int(s["ms"]) <= t1_ms:
                s = dict(s)
                s["family"] = FAMILY
                out.append(s)
    return out


def replay(keep: dict, channel_arena_dir: Path, tape_dir: Path, t0_day: str, t1_day: str,
           fam: dict | None = None, mk=None) -> dict:
    """F6 over the pinned pages for the KEEP addresses the sensor followed, marked on the tape
    with the marker's own functions; every row in_sample (R147). Returns the replay document
    (signals, episodes, coverage, pins)."""
    fam = fam or load_families()
    mk = mk or al.load_marker()
    coins = list(fam["declared_coins"])
    stop, gate = float(fam["exit"]["stop_bps"]), int(fam["exit"]["gate_ms"])
    fee = float(fam["costs"]["fee_bps_per_leg"])
    min_notional = float(fam["families"][BASE_FAMILY]["parameter"]["min_open_notional_usd"])
    t0_ms, t1_ms = day_ms(t0_day), day_ms(t1_day) + DAY_MS - 1
    tape_days = days_between(t0_day, day_of(day_ms(t1_day) + DAY_MS))   # one more day for exits
    paths, tape_pins = read_tape(tape_dir, tape_days, coins)
    coverage, page_pins, signals, closes = {}, [], [], []
    index, index_pin = read_pages_index(channel_arena_dir / "pages_index.jsonl")
    for addr in keep["addresses"]:
        parts = sorted(channel_arena_dir.glob(f"pages_fills_{addr}.jsonl.part*"))
        if not parts:
            coverage[addr] = {"parts": 0, "pages": 0, "fills": 0, "signals": 0,
                              "note": "no pages on the channel: the sensor did not follow this address (disclosed, R147)"}
            continue
        fills, pins, align = read_page_parts(parts, index.get(f"pages_fills_{addr}.jsonl"))
        page_pins.extend(pins)
        sigs = f6_signals(fills, addr, coins, min_notional, t0_ms, t1_ms, mk)
        cl = ag.close_events(fills, coins, addr)
        closes.extend(cl)
        coverage[addr] = {"parts": len(parts), "pages": align["pages"], "fills": len(fills), "signals": len(sigs), "closes": len(cl), "alignment": align}
        signals.extend(sigs)
    signals.sort(key=lambda s: (int(s["ms"]), str(s["leader"]), str(s["coin"]), str(s.get("leader_notional", ""))))
    episodes = []
    for coin in coins:
        sigs = [s for s in signals if s["coin"] == coin]
        if not sigs or not paths[coin]:
            continue
        eps = mk.mark_fork(paths[coin], sigs, fork=f"{FAMILY}:{coin}", family=FAMILY, coin=coin,
                           stop_bps=stop, gate_ms=gate, fee_bps_per_leg=fee,
                           spread_bps_per_leg=REPLAY_SPREAD_BPS_PER_LEG, spread_source=REPLAY_SPREAD_SOURCE,
                           funding=(), in_sample=True)
        episodes.extend(eps)
    episodes.sort(key=lambda e: (e.entry_ms, e.fork))
    # A38 R151: F7 over the same signals, the exit = the leader's own close
    closes.sort(key=lambda c: (c["ms"], c["leader"], c["coin"]))
    episodes_f7 = []
    holes = 0
    for coin in coins:
        sigs = [s for s in signals if s["coin"] == coin]
        if sigs and paths[coin]:
            holes += ag.signals_in_tape_holes(paths[coin], sigs, closes, coin)
            episodes_f7.extend(ag.mark_f7(paths[coin], sigs, closes, coin=coin, fee_bps_per_leg=fee,
                                          spread_bps_per_leg=REPLAY_SPREAD_BPS_PER_LEG, spread_source=REPLAY_SPREAD_SOURCE,
                                          in_sample=True))
    episodes_f7.sort(key=lambda e: (e["entry_ms"], e["fork"]))
    # how many signals had no later close by the same leader on the same coin (F7 can never take them)
    no_close = 0
    for s_ in signals:
        ld = str(s_.get("leader", "")).lower()
        if not any(c["leader"] == ld and c["coin"] == s_["coin"] and c["ms"] > int(s_["ms"]) for c in closes):
            no_close += 1
    return {
        "family": FAMILY, "one_variable": "the list (R145): F6 = F4 with the KEEP set as its leaders; nothing else differs",
        "f7": {"family": ag.F7, "one_variable": "the exit (R151): F7 = F6 with the leader's own close as the exit; no stop, no gate; nothing else differs",
               "closes_seen": len(closes), "signals_without_later_close": no_close, "signals_in_tape_holes": holes},
        "episodes_f7": episodes_f7,
        "keep": {"cohort_date": keep["cohort_date"], "feed_file": keep["feed_file"], "feed_sha256": keep["feed_sha256"],
                 "addresses": keep["addresses"], "excluded_record": keep["excluded_record"]},
        "window": {"t0_ms": t0_ms, "t1_ms": t1_ms, "t0_day": t0_day, "t1_day": t1_day, "tape_days": tape_days},
        "parameters": {"coins": coins, "stop_bps": stop, "gate_ms": gate, "fee_bps_per_leg": fee,
                       "spread_bps_per_leg": REPLAY_SPREAD_BPS_PER_LEG, "spread_source": REPLAY_SPREAD_SOURCE,
                       "min_open_notional_usd": min_notional, "funding": "excluded (disclosed)"},
        "coverage": coverage,
        "signals": signals,
        "episodes": [e.row() for e in episodes],
        "pins": {"pages": page_pins, "tape": tape_pins, **({"pages_index": index_pin} if index_pin else {})},
        "in_sample": True,
        "disclosure": ("every row in_sample: the rule (F6 = the KEEP list) was decided after cohort 1's KEEP set and cohort 2's "
                       "partial grade had been seen (R147); episodes whose exit the tape had not yet printed are dropped "
                       "(the marker's rule); funding excluded"),
    }


# ----------------------------------------------------------------------------- the comparison on the same days
def admitted_days(vps_dir: Path, first_day: str, as_of: str) -> tuple[dict[str, list[dict]], dict[str, dict], dict[str, str]]:
    """The newest pinned marks reading per day (as the ledger reads them), void days excluded (R116).
    Returns (rows_by_day, void_days, readings_by_day)."""
    reader = al.load_reader()
    readings = al.newest_readings(vps_dir, first_day, as_of)
    rows_by_day, voids = {}, {}
    for d, p in readings.items():
        try:
            all_rows, void_marks, _al = reader.read_day_lines(p, "marks")
        except reader.Refused as exc:
            raise AdapterError(str(exc)) from exc
        if void_marks:
            voids[d] = {"void_marks": len(void_marks), "file": p.name}
            continue
        rows_by_day[d] = [r for r in all_rows if not r.get("in_sample", False)]
    return rows_by_day, voids, {d: p.name for d, p in readings.items()}


def daily_table(rep: dict, rows_by_day: dict[str, list[dict]], days: list[str]) -> list[dict]:
    """Per admitted day inside the replay window: F6 and F7 (replay), F4 and C1 (pinned marks) episodes and
    summed net bps over the declared coins. The same arithmetic for the four (R147, R151)."""
    out = []
    f6_by_day: dict[str, list[float]] = {}
    f7_by_day: dict[str, list[float]] = {}
    for e in rep["episodes"]:
        f6_by_day.setdefault(day_of(int(e["entry_ms"])), []).append(float(e["net_bps"]))
    for e in rep.get("episodes_f7", []):
        f7_by_day.setdefault(day_of(int(e["entry_ms"])), []).append(float(e["net_bps"]))
    for d in days:
        if d < rep["window"]["t0_day"] or d > rep["window"]["t1_day"]:
            continue
        rows = rows_by_day.get(d, [])
        f4 = [float(r["net_bps"]) for r in rows if r.get("family") == BASE_FAMILY]
        c1 = [float(r["net_bps"]) for r in rows if r.get("family") == CONTROL]
        f6 = f6_by_day.get(d, [])
        f7 = f7_by_day.get(d, [])
        out.append({"day": d, "admitted": d in rows_by_day,
                    "F6": {"episodes": len(f6), "sum_net_bps": math.fsum(f6)},
                    "F7": {"episodes": len(f7), "sum_net_bps": math.fsum(f7)},
                    "F4": {"episodes": len(f4), "sum_net_bps": math.fsum(f4)},
                    "C1": {"episodes": len(c1), "sum_net_bps": math.fsum(c1)},
                    "F6_beats_both_controls": (math.fsum(f6) > 0.0 and math.fsum(f6) > math.fsum(c1)) if f6 else False,
                    "F7_beats_both_controls": (math.fsum(f7) > 0.0 and math.fsum(f7) > math.fsum(c1)) if f7 else False})
    return out


def per_coin(rep: dict, mk, void_days: set[str] = frozenset(), family: str = FAMILY) -> list[dict]:
    """Per fork of `family` over the replay's episodes on admitted days only: an episode entered on a day
    the marker voided counts for nothing (R116), as in the ledger."""
    out = []
    by: dict[str, list[dict]] = {}
    episodes = rep["episodes"] if family == FAMILY else rep.get("episodes_f7", [])
    for e in episodes:
        if day_of(int(e["entry_ms"])) in void_days:
            continue
        by.setdefault(e["coin"], []).append(e)
    for coin in rep["parameters"]["coins"]:
        eps = by.get(coin, [])
        nets = [float(e["net_bps"]) for e in eps]
        gross = [float(e["gross_bps"]) for e in eps]
        ok, mu, bar = mk.mean_clears_2sigma(nets)
        holds = [int(e["exit_ms"]) - int(e["entry_ms"]) for e in eps]
        out.append({"fork": f"{family}:{coin}", "episodes": len(eps),
                    "sum_gross_bps": math.fsum(gross), "sum_net_bps": math.fsum(nets),
                    "mean_net_bps": mu if nets else None,
                    "two_sigma_over_sqrt_n": None if (not nets or bar == float("inf")) else bar,
                    "stops": sum(1 for e in eps if e["exit_reason"] == "stop"),
                    "gates": sum(1 for e in eps if e["exit_reason"] == "gate"),
                    "leader_closes": sum(1 for e in eps if e["exit_reason"] == ag.EXIT_LEADER_CLOSE),
                    "mean_hold_hours": (math.fsum(holds) / len(holds) / 3_600_000.0) if holds else None,
                    "sd_net_bps": statistics.stdev(nets) if len(nets) > 1 else None})
    return out


# ----------------------------------------------------------------------------- R149 the relisting table
def relist(feed_path: Path, cohort_a: str, cohort_b: str) -> dict:
    """The arena graded by itself: for each verdict of cohort_a, how many addresses were relisted in
    cohort_b, how many of those are FULL in cohort_b's arena as of the feed's day, how many of those
    have verified net > 0. Counts only; never a status, never a rank (R149)."""
    data = feed_path.read_bytes()
    feed = json.loads(data)
    a = feed_cohort(feed, cohort_a)
    b = feed_cohort(feed, cohort_b)
    rows_a, rows_b_list = cohort_rows(feed, cohort_a), cohort_rows(feed, cohort_b)
    rows_b = {_addr(r): r for r in rows_b_list}
    set_a = {_addr(r) for r in rows_a}
    table = []
    for verdict in VERDICTS:
        addrs = [_addr(r) for r in rows_a if r.get("status") == verdict]
        relisted = [x for x in addrs if x in rows_b]
        full = [x for x in relisted if rows_b[x].get("coverage") == "FULL"]
        pos = [x for x in full if _dec(rows_b[x].get("verified_net")) > 0]
        table.append({"verdict": verdict, "n": len(addrs), "relisted": len(relisted), "full_so_far": len(full), "net_positive": len(pos)})
    return {
        "kind": KIND_RELIST,
        "what": ("R149: each verdict of the completed cohort counted as relisted / FULL / net > 0 in the next cohort's arena "
                 "as of the feed's day; a statement about the verdict's forward value, not about any address"),
        "cohort": cohort_a, "next_cohort": cohort_b,
        "next_cohort_arena_as_of": b.get("arena_as_of"), "next_window": b.get("window"),
        "feed_file": feed_path.name, "feed_sha256": sha256_bytes(data),
        "table": table,
        "n_rows": {"cohort": len(rows_a), "next_cohort": len(rows_b_list)},
        "new_in_next_cohort": sum(1 for x in rows_b if x not in set_a),
    }


def _dec(x) -> float:
    try:
        return float(str(x))
    except (TypeError, ValueError):
        return 0.0


# ----------------------------------------------------------------------------- R148 the book's ledger
def book_ledger(as_of: str, vps_dir: Path = VPS_DIR, family: str = FAMILY) -> dict:
    m = al.ledger(as_of, vps_dir=vps_dir, family=family)
    m["kind"] = "agent_record_book_ledger"
    m["what"] = (f"R148 (and R151 for F7): the {family} population's own ledger, six slots of its own, the same k_for, controls "
                 "and retirement rule as the F4 population's; never merged, ranked or averaged with it or with any arena row; "
                 "no forward row exists before the marker runs with keep.json")
    return m


def render_book_ledger(m: dict) -> str:
    body = al.render_markdown(m)
    body = body.replace("# Population ledger as of", f"# The book's ledger ({m.get('family', FAMILY)}) as of", 1)
    return body.replace("(PREREG A21)", "(PREREG A37 R148 / A38 R151; the arithmetic of A21)", 1)


# ----------------------------------------------------------------------------- the page
def render_book(b: dict) -> str:
    k = b["keep"]
    pr = b["replay"]["parameters"]
    out = [f"# The book of the verdict as of {b['as_of']} (PREREG A37, A38)", ""]
    out.append(f"F6 = F4 with one variable changed, the list: the arena's KEEP set of cohort {k['cohort_date']} "
               f"({len(k['addresses'])} addresses, the RECORD row excluded; feed `{k['feed_file']}` {k['feed_sha256'][:16]}…). "
               f"F7 = F6 with one variable changed, the exit: the leader's own close (R151). "
               f"Stop {pr['stop_bps']} bps, gate {pr['gate_ms']} ms (F6 only), fee {pr['fee_bps_per_leg']} bps a leg, "
               f"spread {pr['spread_bps_per_leg']} bps a leg ({pr['spread_source']}), funding excluded. Endpoint `{b['endpoint']}`.")
    out.append("")
    out.append("## The KEEP list and what the sensor followed")
    out.append("")
    out.append("| address | pages | fills | F6 signals in the window | leader closes | torn / lost / unparsed lines | note |")
    out.append("|---|---:|---:|---:|---:|---|---|")
    for addr in k["addresses"]:
        c = b["replay"]["coverage"].get(addr, {})
        al_ = c.get("alignment") or {}
        torn = f"{al_.get('torn_fragments', 0)} / {al_.get('lost_pages', 0)} / {al_.get('unparsed', 0)}" if al_ else "—"
        out.append(f"| `{addr}` | {c.get('pages', 0)} | {c.get('fills', 0)} | {c.get('signals', 0)} | {c.get('closes', 0)} | {torn} | {c.get('note', '—')} |")
    out.append("")
    w = b["replay"]["window"]
    out.append(f"## The replay, entries {w['t0_day']} … {w['t1_day']} (R147: in-sample, decides nothing)")
    out.append("")
    out.append("| day | admitted | F6 ep | F6 net bps | F7 ep | F7 net bps | F4 ep | F4 net bps | C1 ep | C1 net bps | F6 > both | F7 > both |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for r in b["daily"]:
        out.append(f"| {r['day']} | {'yes' if r['admitted'] else 'void (R116)'} | {r['F6']['episodes']} | {_f(r['F6']['sum_net_bps'])} | "
                   f"{r['F7']['episodes']} | {_f(r['F7']['sum_net_bps'])} | {r['F4']['episodes']} | {_f(r['F4']['sum_net_bps'])} | "
                   f"{r['C1']['episodes']} | {_f(r['C1']['sum_net_bps'])} | {'yes' if r['F6_beats_both_controls'] else 'no'} | "
                   f"{'yes' if r['F7_beats_both_controls'] else 'no'} |")
    out.append("")
    out.append("| fork | episodes | sum gross bps | sum net bps | mean net bps | 2σ/√n | stops | gates | leader closes | mean hold h |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in b["per_coin"] + b["per_coin_f7"]:
        out.append(f"| {r['fork']} | {r['episodes']} | {_f(r['sum_gross_bps'])} | {_f(r['sum_net_bps'])} | {_f(r['mean_net_bps'])} | "
                   f"{_f(r['two_sigma_over_sqrt_n'])} | {r['stops']} | {r['gates']} | {r['leader_closes']} | {_f(r['mean_hold_hours'])} |")
    t = b["replay_totals"]
    out.append("")
    out.append(f"Replay totals on admitted days: F6 {t['episodes']} episodes, gross {_f(t['sum_gross_bps'])} bps, cost {_f(t['sum_cost_bps'])} bps, "
               f"net {_f(t['sum_net_bps'])} bps ({t['episodes_on_void_days_not_counted']} on void days counted for nothing, R116); "
               f"F7 {t['F7_episodes']} episodes, gross {_f(t['F7_sum_gross_bps'])} bps, cost {_f(t['F7_sum_cost_bps'])} bps, net {_f(t['F7_sum_net_bps'])} bps "
               f"({t['F7_episodes_on_void_days_not_counted']} on void days not counted; {t['F7_signals_without_later_close']} signals had no later close by their leader, {t['F7_signals_in_tape_holes']} closed inside a tape hole and were skipped); "
               f"F4 on the same admitted days {t['F4_episodes']} episodes / {_f(t['F4_sum_net_bps'])} bps; "
               f"C1 {t['C1_episodes']} / {_f(t['C1_sum_net_bps'])} bps; days F6 beat both controls {t['days_F6_beats_both_controls']} of {len(t['admitted_days'])}, "
               f"F7 {t['days_F7_beats_both_controls']} of {len(t['admitted_days'])}. {b['replay']['disclosure']}.")
    out.append("")
    rl = b["relist"]
    out.append(f"## The arena graded by itself (R149): cohort {rl['cohort']} relisted in cohort {rl['next_cohort']} as of {rl['next_cohort_arena_as_of']}")
    out.append("")
    out.append("| verdict | n | relisted | FULL so far | net > 0 |")
    out.append("|---|---:|---:|---:|---:|")
    for r in rl["table"]:
        out.append(f"| {r['verdict']} | {r['n']} | {r['relisted']} | {r['full_so_far']} | {r['net_positive']} |")
    out.append("")
    out.append(f"{rl['new_in_next_cohort']} addresses of cohort {rl['next_cohort']} were not in cohort {rl['cohort']}. Counts only; never a status, never a rank.")
    out.append("")
    cp = b["copier"]
    out.append(f"## The copier row (A38 R153–R155): `{cp['address']}`, leg {cp['leg']}, from {cp['r155_start']}")
    out.append("")
    out.append(f"Settled pairs {cp['n_settled']} (open trips {len(cp['open_trips'])}); sum net {_f(cp['sum_net_usd'], 6)} USD / {_f(cp['sum_net_bps'])} bps; "
               f"mean {_f(cp['mean_net_bps'])} bps; 2σ/√n {_f(cp['two_sigma_over_sqrt_n'])}; run {cp['run_days']} of k {cp['k']}; "
               f"status **{cp['status']}**; kill test {'due' if cp['kill_due'] else 'not due'} (at {cp['kill_pairs']} pairs or {cp['kill_date']}); "
               f"first pair 50th-percentile date {cp['first_pair_date_50pct']}, first settled {cp['first_pair_settled'] or 'none'}; coverage {cp['coverage'] or '—'}.")
    if cp["settled_pairs"]:
        out.append("")
        out.append("| coin | dir | entry | exit | hold h | net USD | net bps |")
        out.append("|---|---|---|---|---:|---:|---:|")
        for p_ in cp["settled_pairs"]:
            out.append(f"| {p_['coin']} | {'L' if p_['direction'] > 0 else 'S'} | {p_['entry_ms']} | {p_['exit_ms']} | {_f(p_['hold_ms'] / 3_600_000.0)} | {_f(p_['net_usd'], 6)} | {_f(p_['net_bps'])} |")
    out.append("")
    out.append(f"**{cp['starlink_line']}** (R158: ready only at ≥ {cp['starlink_pairs_needed']} settled pairs, not KILLED, coverage FULL; nothing is shared before).")
    out.append("")
    lg = b["ledger"]
    out.append(f"## The book's ledgers (R148, R151) as of {lg['as_of']}: F6 {lg['counts']}, F7 {b['ledger_f7']['counts']}, k {lg['k']}, forward days read {len(lg['days'])}")
    out.append("")
    out.append(f"Forward F6 rows: {lg['forward_rows']}; forward F7 rows: {b['ledger_f7']['forward_rows']}. {lg['note']}")
    out.append("")
    out.append("Rules: **R145** F6 = F4's signal over the KEEP list, every other byte F4's; **R146** the list from the pinned feed, "
               "the record excluded, refreshed per completed cohort; **R147** the replay is in-sample and decides nothing; "
               "**R148** only the forward marker's rows enter the book's ledger; **R149** the relisting table counts verdicts, not addresses; "
               "**R151** F7 exits at the leader's own close; **R153** the copier row's kill line; **R154** the record's account is the first COPIER row; "
               "**R155** the entry is the first F6 signal inside the window; **R158** the Starlink is a readiness gate; "
               "**S105/S107** pure, byte-equal on re-run; **S106/S108** no venue write path, no order from the machine.")
    out.append("")
    out.append(b["what_is_not_claimed"])
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- run / verify
def record_coverage_word(feed_path: Path, cohort_date: str) -> str | None:
    feed = json.loads(feed_path.read_bytes())
    for r in cohort_rows(feed, cohort_date):
        if r.get("record"):
            return r.get("coverage")
    return None


def run(as_of: str, cohort: str, next_cohort: str, feed_path: Path, channel_arena_dir: Path, tape_dir: Path,
        t0_day: str, t1_day: str, out_dir: Path = BOOK_DIR, vps_dir: Path = VPS_DIR, endpoint: str = "",
        marker_dir: Path = MARKER_DIR, copiers_path: Path | None = None) -> dict:
    mk = al.load_marker(marker_dir / "marker.py")
    fam = load_families(marker_dir / "families.json")
    copiers_path = copiers_path if copiers_path is not None else (_FIXTURES / "arena" / "copiers.json")
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = keep_list(feed_path, cohort)
    rep = replay(keep, channel_arena_dir, tape_dir, t0_day, t1_day, fam=fam, mk=mk)
    rows_by_day, voids, readings = admitted_days(vps_dir, al.FIRST_FULL_DAY, as_of)
    days = days_between(t0_day, t1_day)
    daily = daily_table(rep, rows_by_day, days)
    for r in daily:
        if r["day"] in voids:
            r["admitted"] = False
    void_set = {d for d in voids if t0_day <= d <= t1_day}
    coins = per_coin(rep, mk, void_set)
    coins_f7 = per_coin(rep, mk, void_set, family=ag.F7)
    counted = [e for e in rep["episodes"] if day_of(int(e["entry_ms"])) not in void_set]
    counted_f7 = [e for e in rep["episodes_f7"] if day_of(int(e["entry_ms"])) not in void_set]
    totals = {
        "episodes": len(counted),
        "episodes_on_void_days_not_counted": len(rep["episodes"]) - len(counted),
        "sum_gross_bps": math.fsum(float(e["gross_bps"]) for e in counted),
        "sum_cost_bps": math.fsum(float(e["cost_bps"]) for e in counted),
        "sum_net_bps": math.fsum(float(e["net_bps"]) for e in counted),
        "F7_episodes": len(counted_f7),
        "F7_episodes_on_void_days_not_counted": len(rep["episodes_f7"]) - len(counted_f7),
        "F7_signals_without_later_close": rep["f7"]["signals_without_later_close"],
        "F7_signals_in_tape_holes": rep["f7"]["signals_in_tape_holes"],
        "F7_sum_gross_bps": math.fsum(float(e["gross_bps"]) for e in counted_f7),
        "F7_sum_cost_bps": math.fsum(float(e["cost_bps"]) for e in counted_f7),
        "F7_sum_net_bps": math.fsum(float(e["net_bps"]) for e in counted_f7),
        "F4_episodes": sum(r["F4"]["episodes"] for r in daily if r["admitted"]),
        "F4_sum_net_bps": math.fsum(r["F4"]["sum_net_bps"] for r in daily if r["admitted"]),
        "C1_episodes": sum(r["C1"]["episodes"] for r in daily if r["admitted"]),
        "C1_sum_net_bps": math.fsum(r["C1"]["sum_net_bps"] for r in daily if r["admitted"]),
        "days_F6_beats_both_controls": sum(1 for r in daily if r["admitted"] and r["F6_beats_both_controls"]),
        "days_F7_beats_both_controls": sum(1 for r in daily if r["admitted"] and r["F7_beats_both_controls"]),
        "admitted_days": [r["day"] for r in daily if r["admitted"]],
        "void_days": sorted(void_set),
    }
    rl = relist(feed_path, cohort, next_cohort)
    lg = book_ledger(as_of, vps_dir)
    lg7 = book_ledger(as_of, vps_dir, family=ag.F7)
    forward_rows = sum(r["episodes"] for r in lg["forks"])
    forward_rows_7 = sum(r["episodes"] for r in lg7["forks"])
    lg_summary = {"as_of": as_of, "counts": lg["counts"], "k": lg["k"], "days": lg["days"], "forward_rows": forward_rows,
                  "note": ("no forward F6 row exists before the marker runs with keep.json beside it (R148)") if forward_rows == 0
                  else "forward rows read from the pinned marks"}
    lg7_summary = {"as_of": as_of, "counts": lg7["counts"], "k": lg7["k"], "forward_rows": forward_rows_7}
    # the copier row (A38 R153-R155, R158): the record's own pages on the channel, C1's daily nets from the pinned marks
    rec_parts = sorted(channel_arena_dir.glob(f"pages_fills_{ag.RECORD_ADDRESS}.jsonl.part*"))
    rec_fills, rec_pins, rec_align = (read_page_parts(rec_parts) if rec_parts else ([], [], None))
    c1_daily = {d: math.fsum(float(r["net_bps"]) for r in rows if r.get("family") == CONTROL) for d, rows in rows_by_day.items()}
    copiers_doc = ag.load_copiers(copiers_path)
    cp = ag.copier_section(as_of, copiers_doc, rec_fills, c1_daily, record_coverage_word(feed_path, next_cohort))
    cp["pages"] = {"parts": len(rec_parts), "fills": len(rec_fills), "alignment": rec_align}
    cp["registry"] = {"file": copiers_path.name, "sha256": sha256_file(copiers_path) if copiers_path.exists() else None}
    written = {}

    def put(name: str, text: str):
        p = out_dir / name
        p.write_text(text, encoding="utf-8", newline="\n")
        written[name] = sha256_file(p)

    put(f"keep_{cohort}.json", dumps(keep))
    put(f"signals_F6_{cohort}_as_of_{as_of}.jsonl", "".join(json.dumps(s_, separators=(",", ":"), sort_keys=True) + "\n" for s_ in rep["signals"]))
    put(f"marks_F6_{cohort}_as_of_{as_of}.jsonl", "".join(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n" for e in rep["episodes"]))
    put(f"marks_F7_{cohort}_as_of_{as_of}.jsonl", "".join(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n" for e in rep["episodes_f7"]))
    put(f"relist_{as_of}.json", dumps(rl))
    put(f"ledger_F6_{as_of}.json", al.ledger_json(lg))
    put(f"ledger_F6_{as_of}.md", render_book_ledger(lg))
    put(f"ledger_F7_{as_of}.json", al.ledger_json(lg7))
    put(f"ledger_F7_{as_of}.md", render_book_ledger(lg7))
    put(f"copier_{as_of}.json", dumps(cp))
    book = {
        "kind": KIND_BOOK, "as_of": as_of, "endpoint": endpoint,
        "keep": {k: v for k, v in keep.items() if k != "kind"},
        "replay": {k: v for k, v in rep.items() if k not in ("signals", "episodes", "episodes_f7")},
        "replay_files": {"signals": f"signals_F6_{cohort}_as_of_{as_of}.jsonl", "marks": f"marks_F6_{cohort}_as_of_{as_of}.jsonl",
                         "marks_f7": f"marks_F7_{cohort}_as_of_{as_of}.jsonl"},
        "daily": daily, "per_coin": coins, "per_coin_f7": coins_f7, "replay_totals": totals,
        "relist": {k: v for k, v in rl.items() if k != "kind"},
        "ledger": lg_summary, "ledger_f7": lg7_summary,
        "copier": {k: v for k, v in cp.items() if k != "settled_pairs"} | {"settled_pairs": cp["settled_pairs"]},
        "readings": readings,
        "what_is_not_claimed": WHAT_IS_NOT_CLAIMED,
    }
    put(f"book_{as_of}.json", dumps(book))
    put(f"book_{as_of}.md", render_book(book))
    put("book_latest.json", dumps(book))
    manifest = {
        "kind": KIND_MANIFEST, "as_of": as_of, "amendment": "A37, A38",
        "inputs": {"feed": {"file": feed_path.name, "sha256": keep["feed_sha256"]},
                   "pages": rep["pins"]["pages"], "record_pages": rec_pins, "tape": rep["pins"]["tape"],
                   "marks_readings": {d: sha256_file(vps_dir / n_) for d, n_ in readings.items()},
                   "copiers.json": cp["registry"]["sha256"],
                   "marker.py": sha256_file(marker_dir / "marker.py"), "families.json": sha256_file(marker_dir / "families.json")},
        "outputs": written,
        "s105": "a re-run over the same bytes writes these bytes (sums by math.fsum, exactly rounded on every interpreter); verify re-hashes every output",
    }
    (out_dir / f"MANIFEST_BOOK_{as_of}.json").write_text(dumps(manifest), encoding="utf-8", newline="\n")
    return book


def verify(manifest_path: Path) -> list[str]:
    m = json.loads(manifest_path.read_bytes())
    bad = []
    for name, sha in m["outputs"].items():
        p = manifest_path.parent / name
        if not p.exists():
            bad.append(f"{name}: missing")
        elif sha256_file(p) != sha:
            bad.append(f"{name}: {sha256_file(p)[:16]} != pin {sha[:16]} (S105)")
    return bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.arena_book", description="The book of the verdict (PREREG A37). Pure; no network; no clock.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--as-of", required=True)
    r.add_argument("--cohort", required=True, help="the completed cohort whose KEEP set is the list")
    r.add_argument("--next-cohort", required=True, help="the cohort being graded now (the relisting table's second column)")
    r.add_argument("--feed", type=Path, required=True)
    r.add_argument("--channel-arena-dir", type=Path, required=True, help="the channel extract's arena/<next cohort>/")
    r.add_argument("--tape-dir", type=Path, required=True, help="the channel extract's tape/")
    r.add_argument("--t0", required=True, help="first entry day (the next cohort's window start)")
    r.add_argument("--t1", required=True, help="last entry day (as_of, or the window's end)")
    r.add_argument("--out-dir", type=Path, default=BOOK_DIR)
    r.add_argument("--vps-dir", type=Path, default=VPS_DIR)
    r.add_argument("--endpoint", default="")
    r.add_argument("--copiers", type=Path, default=None, help="arena/copiers.json (default: the fixtures' registry)")
    v = sub.add_parser("verify")
    v.add_argument("--manifest", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.cmd == "run":
            b = run(a.as_of, a.cohort, a.next_cohort, a.feed, a.channel_arena_dir, a.tape_dir, a.t0, a.t1,
                    out_dir=a.out_dir, vps_dir=a.vps_dir, endpoint=a.endpoint, copiers_path=a.copiers)
            sys.stdout.write(render_book(b))
            return 0
        bad = verify(a.manifest)
        if bad:
            sys.stdout.write("BOOK REFUSED (S105):\n" + "\n".join("  " + x for x in bad) + "\n")
            return 2
        sys.stdout.write("book verify OK\n")
        return 0
    except AdapterError as exc:
        sys.stdout.write(f"BOOK REFUSED: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
