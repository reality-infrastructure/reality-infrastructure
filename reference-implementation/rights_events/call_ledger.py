"""THE CALL LEDGER (PREREG A35, R137–R144, S103–S104; the loss as SETTLED_CALLS.md defines it).

  register  one pre-registered call per subject each frozen leg names, BEFORE the window opens:
            BAR calls (one coin, one UTC hour) and MARKET calls (one HIP-4 binary price market from a
            pinned capture). The caller passes the registration time and the commit sha (no clock here).
            A call whose window is too close is LATE and never resolved. Append-only per day; a call is
            its (leg, type, subject, window_start, side); a repeat is DUPLICATE.
  resolve   every REGISTERED call of a day against the pinned tape of record (the day's file and the
            next day's), bit for bit as SETTLED_CALLS.md 3: RIGHT / WRONG / UNRESOLVED; SLOW when the
            print lands after the day; per leg RESOLVED, WRONG, LOSS_RATE and the side counts; GAP for a
            live leg against its paper twin. The tape files' sha256 are pinned; a later resolution of the
            same day on different tape bytes is refused (S104: a print never moves).
  board     the two numbers per leg per day (+ GAP), dated pins and board_latest.json byte-equal (S103).

No network, no clock, no randomness beyond the seeded coin-flip controls (seed = commit sha + subject).
Usage:
    python -m rights_events.call_ledger register --day D --registered-ms T --commit-sha H --tape-dir DIR
    python -m rights_events.call_ledger resolve  --day D --tape-dir DIR
    python -m rights_events.call_ledger board    --day D
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
CALLS_DIR = _FIXTURES / "calls"
LEGS_DIR = CALLS_DIR / "legs"
LEDGER_DIR = CALLS_DIR / "ledger"
BOARD_DIR = CALLS_DIR / "board"
CAPTURES_DIR = CALLS_DIR / "captures"
SETTLED_CALLS = Path(__file__).resolve().parents[1] / "contracts" / "agent_record" / "SETTLED_CALLS.md"
LEDGER_KIND = "proof_of_outcome_call_ledger"
BAR_MS = 3_600_000
DAY_MS = 86_400_000
BAR_OPEN_TOL_MS = 600_000     # SETTLED_CALLS.md 3a: the first row at/after the boundary within 600 s
MARKET_TOL_MS = 60_000        # SETTLED_CALLS.md 3b: within 60 s of the market's time
BAR_LEAD_MS = 1_800_000       # R137: a bar must open >= 1 800 s after registration
MARKET_LEAD_MS = 300_000      # R137: a market must expire >= 300 s after registration
BINARY_TEMPLATE = "template:binaryPrice"
STATUS_REG, STATUS_LATE, STATUS_DUP = "REGISTERED", "LATE", "DUPLICATE"
BIT_RIGHT, BIT_WRONG, BIT_UNRESOLVED, BIT_SLOW = "RIGHT", "WRONG", "UNRESOLVED", "SLOW"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def day_ms(day: str) -> int:
    y, m, d = (int(x) for x in day.split("-"))
    return int(_dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp() * 1000)


def iso(ms: int) -> str:
    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _dec(s) -> Decimal:
    try:
        return Decimal(str(s))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AdapterError(f"not a decimal: {s!r}") from exc


# --- inputs -----------------------------------------------------------------------------------

def load_legs(legs_dir: Path = LEGS_DIR) -> dict[str, dict]:
    legs = {}
    for p in sorted(legs_dir.glob("*.json")):
        leg = json.loads(p.read_text(encoding="utf-8"))
        if leg.get("leg") != p.stem:
            raise AdapterError(f"leg file {p.name} names leg {leg.get('leg')!r}")
        legs[p.stem] = leg
    return legs


def read_tape(path: Path) -> tuple[list[dict], int]:
    """Rows with mids, sorted by ms; torn lines are skipped and counted (R115's spirit, the tape's own)."""
    rows, torn = [], 0
    if not path.exists():
        return rows, torn
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            torn += 1
            continue
        if isinstance(r, dict) and isinstance(r.get("mids"), dict) and r.get("ms") is not None:
            rows.append(r)
    rows.sort(key=lambda r: int(r["ms"]))
    return rows, torn


def first_at(rows: list[dict], ms: int, tol_ms: int) -> dict | None:
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if int(rows[mid]["ms"]) < ms:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(rows) and int(rows[lo]["ms"]) < ms + tol_ms:
        return rows[lo]
    return None


def tape_path(tape_dir: Path, day: str) -> Path:
    return tape_dir / f"tape_MIDS_{day}.jsonl"


def newest_capture(captures_dir: Path, day: str) -> Path | None:
    caps = sorted(p for p in captures_dir.glob("outcomes_*.json") if re.match(r"^outcomes_\d{4}-\d{2}-\d{2}\.json$", p.name) and p.name[9:19] <= day)
    return caps[-1] if caps else None


def capture_markets(path: Path) -> list[dict]:
    cap = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for page in cap.get("pages", []):
        out.extend(page.get("markets", []))
    return out


def _side_prices(m: dict) -> tuple[Decimal | None, Decimal | None]:
    yes = no = None
    for s in m.get("sides", []):
        if str(s.get("label", "")).lower() == "yes":
            yes = _dec(s.get("price"))
        elif str(s.get("label", "")).lower() == "no":
            no = _dec(s.get("price"))
    return yes, no


def coin_flip(commit_sha: str, subject: str) -> bool:
    """True (UP / YES) iff the first byte of sha256(commit_sha + ':' + subject) is even."""
    return hashlib.sha256(f"{commit_sha}:{subject}".encode("utf-8")).digest()[0] % 2 == 0


def call_id(leg: str, typ: str, subject: str, window_start_ms: int, side: str) -> str:
    return sha256_bytes(f"{leg}|{typ}|{subject}|{window_start_ms}|{side}".encode("utf-8"))


def _prev_day(day: str) -> str:
    return (_dt.date.fromisoformat(day) - _dt.timedelta(days=1)).isoformat()


def _next_day(day: str) -> str:
    return (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()


# --- register (R137) ----------------------------------------------------------------------------

def _bar_sides(leg: dict, day: str, commit_sha: str, tape_dir: Path) -> tuple[dict[str, dict[int, str]], dict]:
    """Per coin, per bar start ms -> side; plus the inputs used (for the pins)."""
    coins = list(leg["coins"])
    d0 = day_ms(day)
    out: dict[str, dict[int, str]] = {c: {} for c in coins}
    meta: dict = {"rule": leg["rule"], "skipped": {}}
    if leg["leg"].startswith("L1"):
        prev = _prev_day(day)
        prev_rows, _ = read_tape(tape_path(tape_dir, prev))
        day_rows, _ = read_tape(tape_path(tape_dir, day))
        o = first_at(prev_rows, d0 - DAY_MS, BAR_OPEN_TOL_MS)
        c = first_at(day_rows, d0, BAR_OPEN_TOL_MS)
        meta["previous_day"] = {"day": prev, "open_row_ms": o["ms"] if o else None, "close_row_ms": c["ms"] if c else None,
                                "tape_files": {prev: sha256_file(tape_path(tape_dir, prev)) if tape_path(tape_dir, prev).exists() else None,
                                               day: sha256_file(tape_path(tape_dir, day)) if tape_path(tape_dir, day).exists() else None}}
        dirs = {}
        for coin in coins:
            if o is None or c is None or coin not in o["mids"] or coin not in c["mids"]:
                meta["skipped"][coin] = "previous day's open or close row missing"
                continue
            po, pc = _dec(o["mids"][coin]), _dec(c["mids"][coin])
            if pc > po:
                dirs[coin] = "UP"
            elif pc < po:
                dirs[coin] = "DOWN"
            else:
                meta["skipped"][coin] = "previous day's close equals its open"
        meta["directions"] = dirs
        for coin, side in dirs.items():
            for h in range(24):
                out[coin][d0 + h * BAR_MS] = side
    else:   # the seeded coin-flip control
        for coin in coins:
            for h in range(24):
                start = d0 + h * BAR_MS
                out[coin][start] = "UP" if coin_flip(commit_sha, f"{coin}:{iso(start)}") else "DOWN"
    return out, meta


def register(day: str, registered_ms: int, commit_sha: str, legs_dir: Path = LEGS_DIR, tape_dir: Path | None = None,
             captures_dir: Path = CAPTURES_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    if not _DAY.match(day):
        raise AdapterError(f"day {day!r} is not YYYY-MM-DD")
    if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha):
        raise AdapterError("commit sha must be hex")
    legs = load_legs(legs_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"calls_{day}.jsonl"
    existing: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                existing[r["call_id"]] = r
    d0, d_end = day_ms(day), day_ms(day) + DAY_MS - 1
    cap_path = newest_capture(captures_dir, day)
    markets = capture_markets(cap_path) if cap_path else []
    new_rows: list[dict] = []
    summary: dict[str, dict] = {}
    seen_keys = {(r["leg"], r["type"], r["subject"], r["window_start_ms"], r["side"]) for r in existing.values()}
    for name, leg in legs.items():
        counts = {STATUS_REG: 0, STATUS_LATE: 0, STATUS_DUP: 0, "already": 0}
        meta = None
        if leg["type"] == "BAR":
            if tape_dir is None:
                raise AdapterError("BAR legs need --tape-dir")
            sides, meta = _bar_sides(leg, day, commit_sha, tape_dir)
            for coin, by_start in sides.items():
                for start, side in sorted(by_start.items()):
                    key = (name, "BAR", coin, start, side)
                    cid = call_id(*key)
                    if cid in existing:
                        counts["already"] += 1
                        continue
                    status = STATUS_DUP if key in seen_keys else (STATUS_LATE if start < registered_ms + BAR_LEAD_MS else STATUS_REG)
                    seen_keys.add(key)
                    new_rows.append({"call_id": cid, "leg": name, "type": "BAR", "subject": coin, "window_start_ms": start,
                                     "window_start": iso(start), "resolve_at_ms": start + BAR_MS, "side": side, "status": status,
                                     "registered_ms": registered_ms, "registered_at": iso(registered_ms), "registered_sha": commit_sha, "day": day})
                    counts[status] += 1
        elif leg["type"] == "MARKET":
            coins = set(leg["coins"])
            meta = {"capture": cap_path.name if cap_path else None, "capture_sha256": sha256_file(cap_path) if cap_path else None, "rule": leg["rule"]}
            for m in sorted(markets, key=lambda x: (int(x.get("expiryMs", 0)), int(x.get("outcomeId", 0)))):
                if m.get("rawName") != BINARY_TEMPLATE or (m.get("params") or {}).get("perp") not in coins:
                    continue
                exp = int(m["expiryMs"])
                if not (d0 <= exp <= d_end):
                    continue
                yes, no = _side_prices(m)
                if name.startswith("L2"):
                    if yes is None or no is None:
                        continue
                    side = "YES" if yes >= no else "NO"
                else:
                    side = "YES" if coin_flip(commit_sha, str(m["outcomeId"])) else "NO"
                subject = str(m["outcomeId"])
                key = (name, "MARKET", subject, exp, side)
                cid = call_id(*key)
                if cid in existing:
                    counts["already"] += 1
                    continue
                status = STATUS_DUP if key in seen_keys else (STATUS_LATE if exp < registered_ms + MARKET_LEAD_MS else STATUS_REG)
                seen_keys.add(key)
                new_rows.append({"call_id": cid, "leg": name, "type": "MARKET", "subject": subject, "window_start_ms": registered_ms,
                                 "window_start": iso(registered_ms), "resolve_at_ms": exp, "side": side, "status": status,
                                 "coin": m["params"]["perp"], "threshold": str(m["params"].get("threshold")), "market_time": m["params"].get("time"),
                                 "title": m.get("title"), "captured_prices": {"YES": str(yes), "NO": str(no)},
                                 "capture": cap_path.name, "registered_ms": registered_ms, "registered_at": iso(registered_ms),
                                 "registered_sha": commit_sha, "day": day})
                counts[status] += 1
        else:
            continue   # LIVE legs register nothing: their calls are the chain's round trips (R143)
        summary[name] = {"counts": counts, "inputs": meta}
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for r in new_rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return {"kind": LEDGER_KIND, "action": "register", "day": day, "registered_ms": registered_ms, "registered_at": iso(registered_ms),
            "registered_sha": commit_sha, "file": path.name, "file_sha256": sha256_file(path), "new_calls": len(new_rows),
            "total_calls_in_file": len(existing) + len(new_rows), "legs": summary}


# --- resolve (R138, R139) -------------------------------------------------------------------------

def resolve(day: str, tape_dir: Path, ledger_dir: Path = LEDGER_DIR, legs_dir: Path = LEGS_DIR) -> dict:
    if not _DAY.match(day):
        raise AdapterError(f"day {day!r} is not YYYY-MM-DD")
    path = ledger_dir / f"calls_{day}.jsonl"
    if not path.exists():
        raise AdapterError(f"no register for {day}")
    legs = load_legs(legs_dir)
    calls = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    t_day, t_next = tape_path(tape_dir, day), tape_path(tape_dir, _next_day(day))
    pins = {p.name: sha256_file(p) for p in (t_day, t_next) if p.exists()}
    out_path = ledger_dir / f"resolved_{day}.json"
    if out_path.exists():
        earlier = json.loads(out_path.read_text(encoding="utf-8")).get("tape_pins", {})
        for name, sha in earlier.items():
            if name in pins and pins[name] != sha:
                raise AdapterError(f"S104: {name} is {pins[name][:12]}… now, pinned {sha[:12]}… in the earlier resolution of {day}")
    rows_day, torn_day = read_tape(t_day)
    rows_next, torn_next = read_tape(t_next)
    rows_all = sorted(rows_day + rows_next, key=lambda r: int(r["ms"]))
    d_end = day_ms(day) + DAY_MS - 1
    results = []
    seen = set()
    for c in calls:
        r = dict(c)
        if c["status"] != STATUS_REG:
            r["bit"] = c["status"]
            results.append(r)
            continue
        key = (c["leg"], c["type"], c["subject"], c["window_start_ms"], c["side"])
        if key in seen:
            r["bit"] = STATUS_DUP
            results.append(r)
            continue
        seen.add(key)
        if int(c["resolve_at_ms"]) > d_end:
            r["bit"] = BIT_SLOW
            results.append(r)
            continue
        if c["type"] == "BAR":
            o = first_at(rows_all, int(c["window_start_ms"]), BAR_OPEN_TOL_MS)
            cl = first_at(rows_all, int(c["resolve_at_ms"]), BAR_OPEN_TOL_MS)
            if o is None or cl is None or c["subject"] not in o["mids"] or c["subject"] not in cl["mids"]:
                r["bit"] = BIT_UNRESOLVED
                r["print"] = {"open_row_ms": o["ms"] if o else None, "close_row_ms": cl["ms"] if cl else None}
            else:
                po, pc = _dec(o["mids"][c["subject"]]), _dec(cl["mids"][c["subject"]])
                right = (pc > po) if c["side"] == "UP" else (pc < po)
                r["bit"] = BIT_RIGHT if right else BIT_WRONG
                r["print"] = {"open_row_ms": o["ms"], "open": str(po), "close_row_ms": cl["ms"], "close": str(pc), "source": "tape of record"}
        elif c["type"] == "MARKET":
            row = first_at(rows_all, int(c["resolve_at_ms"]), MARKET_TOL_MS)
            coin = c.get("coin")
            if row is None or coin not in row["mids"]:
                r["bit"] = BIT_UNRESOLVED
                r["print"] = {"row_ms": row["ms"] if row else None}
            else:
                mid, thr = _dec(row["mids"][coin]), _dec(c["threshold"])
                above = mid > thr
                right = above if c["side"] == "YES" else (not above)
                r["bit"] = BIT_RIGHT if right else BIT_WRONG
                r["print"] = {"row_ms": row["ms"], "mid": str(mid), "threshold": str(thr), "source": "tape of record (the deployer's settlement not pinned)"}
        else:
            r["bit"] = BIT_UNRESOLVED
            r["print"] = {"note": "no print for this type on the board"}
        results.append(r)
    per_leg: dict[str, dict] = {}
    for name in legs:
        xs = [x for x in results if x["leg"] == name]
        right = sum(1 for x in xs if x["bit"] == BIT_RIGHT)
        wrong = sum(1 for x in xs if x["bit"] == BIT_WRONG)
        resolved = right + wrong
        per_leg[name] = {"mode": legs[name].get("mode"), "type": legs[name].get("type"), "control": legs[name].get("control"),
                         "RESOLVED": resolved, "WRONG": wrong, "RIGHT": right,
                         "LOSS_RATE": round(wrong / resolved, 4) if resolved else None,
                         "UNRESOLVED": sum(1 for x in xs if x["bit"] == BIT_UNRESOLVED), "LATE": sum(1 for x in xs if x["bit"] == STATUS_LATE),
                         "DUPLICATE": sum(1 for x in xs if x["bit"] == STATUS_DUP), "SLOW": sum(1 for x in xs if x["bit"] == BIT_SLOW),
                         "registered": len(xs)}
    for name, leg in legs.items():
        twin = leg.get("paper_twin")
        if leg.get("mode") == "LIVE" and twin in per_leg and per_leg[name]["LOSS_RATE"] is not None and per_leg[twin]["LOSS_RATE"] is not None:
            per_leg[name]["GAP"] = round(per_leg[name]["LOSS_RATE"] - per_leg[twin]["LOSS_RATE"], 4)
    m = {"kind": LEDGER_KIND, "action": "resolve", "day": day, "register_file": path.name, "register_sha256": sha256_file(path),
         "tape_pins": pins, "tape_torn_lines": {t_day.name: torn_day, t_next.name: torn_next}, "settled_calls_sha256": sha256_bytes(SETTLED_CALLS.read_bytes().replace(b"\r\n", b"\n")) if SETTLED_CALLS.exists() else None,
         "legs": per_leg, "calls": results,
         "rules": {"R138": "SETTLED_CALLS.md 3 bit for bit against the pinned tape; UNRESOLVED where a row is missing",
                   "R139": "duplicates once; SLOW after the day's end", "S104": "a later resolution on different tape bytes is refused"}}
    out_path.write_bytes((json.dumps(m, indent=1) + "\n").encode("utf-8"))
    return m


# --- board (R140, S103) ---------------------------------------------------------------------------

def board(day: str, ledger_dir: Path = LEDGER_DIR, board_dir: Path = BOARD_DIR) -> dict:
    p = ledger_dir / f"resolved_{day}.json"
    if not p.exists():
        raise AdapterError(f"no resolution for {day}")
    res = json.loads(p.read_text(encoding="utf-8"))
    rows = []
    for name, v in res["legs"].items():
        rows.append({"leg": name, "mode": v["mode"], "type": v["type"], "control": v["control"], "RESOLVED": v["RESOLVED"],
                     "LOSS_RATE": v["LOSS_RATE"], "GAP": v.get("GAP"), "RIGHT": v["RIGHT"], "WRONG": v["WRONG"],
                     "UNRESOLVED": v["UNRESOLVED"], "LATE": v["LATE"], "DUPLICATE": v["DUPLICATE"], "SLOW": v["SLOW"], "registered": v["registered"]})
    m = {"kind": "proof_of_outcome_call_board", "day": day, "resolution_sha256": sha256_file(p), "tape_pins": res["tape_pins"],
         "settled_calls_sha256": res.get("settled_calls_sha256"), "rows": rows,
         "what_is_not_claimed": "Two numbers per leg per day, RESOLVED and LOSS RATE (and GAP for a live leg), from pre-registered calls against pinned prints; nothing else is scored."}
    board_dir.mkdir(parents=True, exist_ok=True)
    js = (json.dumps(m, indent=1) + "\n").encode("utf-8")
    md = render_board(m).encode("utf-8")
    (board_dir / f"board_{day}.json").write_bytes(js)
    (board_dir / f"board_{day}.md").write_bytes(md)
    (board_dir / "board_latest.json").write_bytes(js)
    return m


def render_board(m: dict) -> str:
    out = [f"# The call board, {m['day']} (PREREG A35, SETTLED_CALLS.md `{str(m.get('settled_calls_sha256'))[:16]}…`)", "",
           "| leg | mode | RESOLVED | LOSS RATE | GAP | right | wrong | unresolved | late | duplicate | slow |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in m["rows"]:
        lr = "—" if r["LOSS_RATE"] is None else f"{r['LOSS_RATE']:.4f}"
        gap = "—" if r.get("GAP") is None else f"{r['GAP']:+.4f}"
        out.append(f"| {r['leg']} | {r['mode']} | {r['RESOLVED']} | {lr} | {gap} | {r['RIGHT']} | {r['WRONG']} | {r['UNRESOLVED']} | {r['LATE']} | {r['DUPLICATE']} | {r['SLOW']} |")
    out += ["", "Tape pins: " + ", ".join(f"`{k}` {v[:16]}…" for k, v in m["tape_pins"].items()), "", m["what_is_not_claimed"]]
    return "\n".join(out) + "\n"


def check_latest(board_dir: Path = BOARD_DIR) -> str:
    dated = sorted(p for p in board_dir.glob("board_*.json") if re.match(r"^board_\d{4}-\d{2}-\d{2}\.json$", p.name))
    if not dated:
        raise AdapterError("S103: no dated board")
    latest = board_dir / "board_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        raise AdapterError(f"S103: board_latest.json is not byte-equal to {dated[-1].name}")
    return dated[-1].name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.call_ledger", description="The call ledger (PREREG A35). Pure; no network; no clock.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--day", required=True)
    r.add_argument("--registered-ms", type=int, required=True)
    r.add_argument("--commit-sha", required=True)
    r.add_argument("--tape-dir", required=True)
    r.add_argument("--legs-dir", default=str(LEGS_DIR))
    r.add_argument("--captures-dir", default=str(CAPTURES_DIR))
    r.add_argument("--ledger-dir", default=str(LEDGER_DIR))
    s = sub.add_parser("resolve")
    s.add_argument("--day", required=True)
    s.add_argument("--tape-dir", required=True)
    s.add_argument("--legs-dir", default=str(LEGS_DIR))
    s.add_argument("--ledger-dir", default=str(LEDGER_DIR))
    b = sub.add_parser("board")
    b.add_argument("--day", required=True)
    b.add_argument("--ledger-dir", default=str(LEDGER_DIR))
    b.add_argument("--board-dir", default=str(BOARD_DIR))
    a = p.parse_args(argv)
    try:
        if a.cmd == "register":
            m = register(a.day, a.registered_ms, a.commit_sha, Path(a.legs_dir), Path(a.tape_dir), Path(a.captures_dir), Path(a.ledger_dir))
            print(f"CALLS REGISTERED {m['day']} at {m['registered_at']} sha {m['registered_sha'][:12]}: new {m['new_calls']}, in file {m['total_calls_in_file']} ({m['file']} {m['file_sha256'][:16]}…)")
            for leg, v in m["legs"].items():
                print(f"  {leg:22} " + " ".join(f"{k} {n}" for k, n in v["counts"].items()) + (f"  directions {v['inputs'].get('directions')}" if v["inputs"] and v["inputs"].get("directions") else ""))
        elif a.cmd == "resolve":
            m = resolve(a.day, Path(a.tape_dir), Path(a.ledger_dir), Path(a.legs_dir))
            print(f"CALLS RESOLVED {m['day']}: tape pins {', '.join(k + ' ' + v[:12] for k, v in m['tape_pins'].items())}")
            for leg, v in m["legs"].items():
                print(f"  {leg:22} RESOLVED {v['RESOLVED']:4d} LOSS_RATE {v['LOSS_RATE']} right {v['RIGHT']} wrong {v['WRONG']} unresolved {v['UNRESOLVED']} late {v['LATE']} dup {v['DUPLICATE']} slow {v['SLOW']}" + (f" GAP {v['GAP']:+.4f}" if v.get("GAP") is not None else ""))
        else:
            m = board(a.day, Path(a.ledger_dir), Path(a.board_dir))
            check_latest(Path(a.board_dir))
            print(render_board(m))
    except AdapterError as exc:
        print(f"CALL LEDGER REFUSED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
