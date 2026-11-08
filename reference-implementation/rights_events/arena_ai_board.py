"""THE AI BOARD ENTRY (PREREG A29, R123–R127, S101–S102).

The record's account and the paper population graded in the venue's own "AI Traders" columns
(RANK, MODEL, TOTAL P&L, ROI %, WIN RATE, BIGGEST WIN, BIGGEST LOSS, TRADES, FEES), as a pure
function of pinned inputs:

  * the record's rows, one per arena cohort window, from the record address's pinned chain pages
    named in the newest capture_ARENA_<cohort>_<as_of>.json (fills + funding; a page that does not
    hash to its pin refuses the row, S102; pages not on the branch -> listed, not graded).
    A TRADE is a round trip: from a fill whose startPosition is 0 to the fill that returns the
    position to 0; its P&L = sum closedPnl - sum fee (fee includes builderFee). FEES = sum fee of
    every fill in the window. TOTAL P&L = realized ex funding + funding (SETTLED.md). Open round
    trips at the window's end are counted, never valued.
  * the population's rows (F4 forks and C1 controls) from the newest pinned marks reading of every
    full forward day admitted as of --as-of (agent_ledger.newest_readings), void days excluded
    always (R116): TRADES = episodes, WIN RATE on net_bps > 0, BIGGEST WIN / LOSS = max / min
    net_bps, FEES = sum cost_bps, TOTAL P&L = sum net_bps, in bps of one unit, never USD.
  * ROI % = not computed (SETTLED.md 4). RANK within a unit class only (USD, bps), by TOTAL P&L
    descending among rows with >= 1 trade; controls ranked with the forks.

No network, no clock, nothing recomputed from a venue figure. The board's as_of is the day it is
produced; ai_board_<as_of>.json/.md are pins, ai_board_latest.json is byte-equal (S101).

Usage:
    python -m rights_events.arena_ai_board --as-of YYYY-MM-DD [--arena-dir DIR] [--vps-dir DIR]
        [--out-dir DIR] [--settled FILE] [--marker FILE] [--live-dir DIR]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rights_events import agent_ledger as led
from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
ARENA_DIR = _FIXTURES / "arena"
BOARD_DIR = ARENA_DIR / "ai_board"
LIVE_DIR = _FIXTURES
SETTLED = Path(__file__).resolve().parents[1] / "contracts" / "agent_record" / "SETTLED.md"
BOARD_KIND = "proof_of_outcome_ai_board_entry"
COLUMNS = ["RANK", "MODEL", "TOTAL P&L", "ROI %", "WIN RATE", "BIGGEST WIN", "BIGGEST LOSS", "TRADES", "FEES"]
ROI_NOT_COMPUTED = "not computed (SETTLED.md 4: a return is not an outcome)"
ENDPOINT = ("https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/"
            "contract/agent-record/reference-implementation/rights_events/fixtures/agent_record/arena/ai_board/ai_board_latest.json")
FORWARD_FAMILY, CONTROL_FAMILY = "F4", "C1"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CAPTURE = re.compile(r"^capture_ARENA_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
_ARENA = re.compile(r"^arena_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def _dec(s) -> Decimal:
    try:
        return Decimal(str(s))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AdapterError(f"S102: not a decimal string: {s!r}") from exc


def _fmt(d: Decimal) -> str:
    s = format(d, "f")
    return s if "." in s else s + ".0" if False else s


# --- the record: round trips from chain fills ----------------------------------------------------

def round_trips(fills: list[dict]) -> list[dict]:
    """R124. Fills in time order; a trip starts at startPosition 0 and closes when the position returns to 0."""
    trips: list[dict] = []
    cur: dict | None = None
    for f in sorted(fills, key=lambda x: (int(x["time"]), str(x.get("tid", "")))):
        start = _dec(f["startPosition"])
        sz = _dec(f["sz"])
        pos_after = start + sz if f["side"] == "B" else start - sz
        if cur is None:
            if start != 0:
                # a trip already open before the window: counted as open, never valued (no start fill in the window)
                cur = {"pnl": Decimal(0), "fees": Decimal(0), "fills": 0, "first_time_ms": int(f["time"]), "last_time_ms": int(f["time"]),
                       "opened_before_window": True, "txs": []}
            else:
                cur = {"pnl": Decimal(0), "fees": Decimal(0), "fills": 0, "first_time_ms": int(f["time"]), "last_time_ms": int(f["time"]),
                       "opened_before_window": False, "txs": []}
        cur["pnl"] += _dec(f["closedPnl"])
        cur["fees"] += _dec(f["fee"])
        cur["fills"] += 1
        cur["last_time_ms"] = int(f["time"])
        cur["txs"].append(f.get("hash"))
        if pos_after == 0:
            cur["closed"] = True
            cur["net"] = cur["pnl"] - cur["fees"]
            trips.append(cur)
            cur = None
    if cur is not None:
        cur["closed"] = False
        cur["net"] = None
        trips.append(cur)
    return trips


def _read_pages(path: Path, pins: list[dict]) -> list:
    """Pages of a gz page file, each line checked against its pin (S102)."""
    with gzip.open(path, "rb") as f:
        lines = f.read().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    by_line = {int(p["line"]): p for p in pins}
    items: list = []
    for i, raw in enumerate(lines):
        pin = by_line.get(i)
        if pin is None:
            continue
        if sha256_bytes(raw) != pin["sha256"]:
            raise AdapterError(f"S102: {path.name} line {i} does not hash to its pin {pin['sha256'][:12]}…")
        page = json.loads(raw.decode("utf-8"))
        items.extend(page if isinstance(page, list) else page.get("items", []))
    if len(by_line) != sum(1 for i in range(len(lines)) if i in by_line):
        raise AdapterError(f"S102: {path.name} has {len(lines)} lines, pins name {sorted(by_line)}")
    return items


def newest_cohorts(arena_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in sorted(p for p in arena_dir.iterdir() if p.is_dir() and _DAY.match(p.name)):
        caps, arenas = [], []
        for f in d.iterdir():
            m = _CAPTURE.match(f.name)
            if m and m.group(1) == d.name:
                caps.append((m.group(2), f))
            m = _ARENA.match(f.name)
            if m and m.group(1) == d.name:
                arenas.append((m.group(2), f))
        if caps and arenas:
            out[d.name] = {"capture": max(caps)[1], "arena": max(arenas)[1]}
    return out


def record_rows(arena_dir: Path, as_of: str) -> tuple[list[dict], list[dict]]:
    """One row per cohort for the record address (R124). Returns (rows, not_graded)."""
    rows, not_graded = [], []
    for cohort, files in newest_cohorts(arena_dir).items():
        arena = json.loads(files["arena"].read_text(encoding="utf-8"))
        cap = json.loads(files["capture"].read_text(encoding="utf-8"))
        cap_as_of = cap.get("as_of")
        if isinstance(cap_as_of, dict):
            cap_as_of = cap_as_of.get("as_of_date", "")
        cap_as_of = cap.get("as_of_date", cap_as_of) or ""
        if arena.get("as_of", "") > as_of or str(cap_as_of) > as_of:
            raise AdapterError(f"S102: cohort {cohort}: arena/capture as of later than the board's {as_of}")
        rr = arena.get("record_row") or {}
        addr = rr.get("address")
        if not addr:
            not_graded.append({"cohort_date": cohort, "reason": "no record row in the arena"})
            continue
        crow = next((r for r in cap.get("rows", []) if r.get("address") == addr), None)
        if crow is None:
            not_graded.append({"cohort_date": cohort, "address": addr, "reason": "the record address is not in the capture"})
            continue
        fills_path = files["capture"].parent / crow["fills_file"]
        funding_path = files["capture"].parent / crow["funding_file"]
        if not fills_path.exists() or not funding_path.exists():
            not_graded.append({"cohort_date": cohort, "address": addr, "reason": "pages not on the branch (A27 (2): archived at the window's close)",
                               "fills_file": crow["fills_file"], "pins": len(crow.get("fills_pages") or [])})
            continue
        window = arena["window"]
        t0, t1 = int(window["t0_ms"]), int(window["t1_ms"])
        fills = [f for f in _read_pages(fills_path, crow.get("fills_pages") or []) if t0 <= int(f["time"]) <= t1]
        funding = [r for r in _read_pages(funding_path, crow.get("funding_pages") or []) if t0 <= int(r["time"]) <= t1]
        trips = round_trips(fills)
        closed = [t for t in trips if t["closed"]]
        nets = [t["net"] for t in closed]
        fees = sum((_dec(f["fee"]) for f in fills), Decimal(0))
        realized = sum((_dec(f["closedPnl"]) for f in fills), Decimal(0)) - fees
        fund = sum((_dec(r["delta"]["usdc"]) for r in funding), Decimal(0))
        total = realized + fund
        if rr.get("net_with_funding") is not None and _dec(rr["net_with_funding"]) != total:
            raise AdapterError(f"S102: cohort {cohort}: the record's total {total} is not the arena's {rr['net_with_funding']}")
        wins = sum(1 for n in nets if n > 0)
        rows.append({
            "klass": "USD", "model": "RI record · the operator's account · live · one unit", "address": addr, "control": False,
            "cohort_date": cohort, "window": {"t0_date": window.get("t0_date"), "t1_date": window.get("t1_date"), "complete": window.get("complete")},
            "total_pnl": format(total, "f"), "realized_ex_funding": format(realized, "f"), "funding": format(fund, "f"),
            "roi": ROI_NOT_COMPUTED,
            "win_rate": (wins / len(closed)) if closed else None, "wins": wins, "trades": len(closed),
            "open_round_trips_at_window_end": sum(1 for t in trips if not t["closed"]),
            "biggest_win": format(max(nets), "f") if nets else None, "biggest_loss": format(min(nets), "f") if nets else None,
            "fees": format(fees, "f"), "fills": len(fills), "funding_rows": len(funding),
            "trips": [{"net": format(t["net"], "f"), "fills": t["fills"], "first_time_ms": t["first_time_ms"], "last_time_ms": t["last_time_ms"], "txs": t["txs"]} for t in closed],
            "pins": {"capture": files["capture"].name, "capture_sha256": sha256_file(files["capture"]), "fills_file": crow["fills_file"],
                     "fills_pages": [p["sha256"] for p in crow.get("fills_pages") or []], "funding_file": crow["funding_file"],
                     "funding_pages": [p["sha256"] for p in crow.get("funding_pages") or []], "arena_file": files["arena"].name},
            "source": "HyperLiquid L1 fills and funding as the public info API served them, pages pinned in the arena capture (SETTLED.md 1–3)",
        })
    return rows, not_graded


def record_outside_windows(live_dir: Path, graded_t0_ms: int | None) -> list[dict]:
    """The live pairs on the record that lie before every graded window: listed, never added (R124)."""
    out = []
    for p in sorted(live_dir.glob("capture_LIVE_*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        lf = c.get("live_fill") or {}
        if not lf or (graded_t0_ms is not None and int(lf.get("fill_time_ms", 0)) >= graded_t0_ms):
            continue
        out.append({"capture": p.name, "fill_time_ms": lf.get("fill_time_ms"), "dir": lf.get("dir"), "tx_hashes": lf.get("tx_hashes"),
                    "note": "on the record; before every graded window; the capture's fee line is not the chain's (A8); not on the board"})
    return out


# --- the population: forks and controls from pinned marks ----------------------------------------

def population_rows(vps_dir: Path, as_of: str, marker_path: Path, first_day: str = led.FIRST_FULL_DAY) -> tuple[list[dict], dict]:
    reader = led.load_reader()
    readings = led.newest_readings(vps_dir, first_day, as_of)
    days, void_days, by_fork = [], {}, {}
    for d, p in readings.items():
        try:
            rows, voids, _al = reader.read_day_lines(p, "marks")
        except reader.Refused as exc:
            raise AdapterError(str(exc)) from exc
        if voids:
            void_days[d] = {"void_marks": len(voids), "file": p.name}
            continue
        days.append(d)
        for r in rows:
            if r.get("in_sample") or r.get("family") not in (FORWARD_FAMILY, CONTROL_FAMILY):
                continue
            by_fork.setdefault(r["fork"], []).append(r)
    marker_sha = sha256_file(marker_path)
    out = []
    for fork in sorted(by_fork):
        v = by_fork[fork]
        nets = [float(r["net_bps"]) for r in v]
        wins = sum(1 for n in nets if n > 0)
        fam = fork.split(":", 1)[0]
        control = fam == CONTROL_FAMILY
        out.append({
            "klass": "bps", "model": ("%s · %s · marker %s" % (fork, "seeded random-minute entry, the control" if control else "paper copy fork of the leaders' fills", marker_sha[:8])),
            "fork": fork, "control": control, "days": days,
            "total_pnl": sum(nets), "roi": ROI_NOT_COMPUTED,
            "win_rate": wins / len(v), "wins": wins, "trades": len(v),
            "biggest_win": max(nets), "biggest_loss": min(nets), "fees": sum(float(r["cost_bps"]) for r in v),
            "unit": "bps of one unit of notional per episode; never a USD figure",
            "pins": {"readings": {d: readings[d].name for d in days}, "marker.py": marker_sha},
            "source": "pinned marks of the frozen forward marker on the environment tape, net of the fee line and spread (P12.0, R116)",
        })
    return out, {"days": days, "void_days_excluded": void_days, "readings": {d: p.name for d, p in readings.items()}}


def _rank(rows: list[dict]) -> None:
    for klass in ("USD", "bps"):
        ranked = sorted((r for r in rows if r["klass"] == klass and r["trades"] >= 1), key=lambda r: -Decimal(str(r["total_pnl"])))
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
            r["rank_of"] = len(ranked)
        for r in rows:
            if r["klass"] == klass and r.get("rank") is None:
                r["rank"] = None
                r["rank_of"] = len(ranked)


def board(as_of: str, arena_dir: Path = ARENA_DIR, vps_dir: Path = led.VPS_DIR, settled_path: Path = SETTLED,
          marker_path: Path = led.MARKER, live_dir: Path = LIVE_DIR) -> dict:
    if not _DAY.match(as_of):
        raise AdapterError(f"as_of {as_of!r} is not a YYYY-MM-DD date")
    if not settled_path.exists():
        raise AdapterError("S102: SETTLED.md is missing")
    rec, not_graded = record_rows(arena_dir, as_of)
    pop, pop_meta = population_rows(vps_dir, as_of, marker_path)
    rows = rec + pop
    for r in rows:
        r.setdefault("rank", None)
    _rank(rows)
    first_t0 = None
    for cohort, files in newest_cohorts(arena_dir).items():
        a = json.loads(files["arena"].read_text(encoding="utf-8"))
        t0 = int(a["window"]["t0_ms"])
        first_t0 = t0 if first_t0 is None else min(first_t0, t0)
    outside = record_outside_windows(live_dir, first_t0)
    return {
        "kind": BOARD_KIND, "as_of": as_of, "columns": COLUMNS, "endpoint": ENDPOINT,
        "settled_sha256": sha256_bytes(settled_path.read_bytes().replace(b"\r\n", b"\n")),
        "marker_sha256": sha256_file(marker_path),
        "classes": {"USD": "the record's account: USD from chain fills and funding", "bps": "the paper population: basis points of one unit per episode"},
        "rows": sorted(rows, key=lambda r: (0 if r["klass"] == "USD" else 1, r["rank"] if r["rank"] is not None else 10**6, str(r.get("fork") or r.get("cohort_date")))),
        "record_not_graded": not_graded, "record_outside_windows": outside,
        "population": pop_meta,
        "rules": {"R123": "pure function of pinned captures, pages and marks; as_of = production day; latest byte-equal (S101)",
                  "R124": "record rows per arena window; a trade = a round trip from startPosition 0 back to 0; P&L = sum closedPnl - sum fee; open trips counted, never valued",
                  "R125": "forks and controls from pinned marks over admitted non-void days, in bps of one unit, never USD",
                  "R126": "ROI not computed (SETTLED.md 4); rank within a unit class only, among rows with >= 1 trade; controls ranked with the forks",
                  "R127": "the dated pin, the latest pointer, the page section #ai-board, the routine's step 3f"},
        "what_is_not_claimed": "No rank on the venue, no skill, no badge, no return: the record's entry in the venue's columns, graded by the chain and the pinned tape, for the venue to accept or not.",
    }


def _f(x, nd=2):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:+.{nd}f}" if nd else f"{x:.0f}"
    return str(x)


def _row_cells(r: dict) -> list[str]:
    rk = f"{r['rank']} of {r['rank_of']}" if r.get("rank") else f"— of {r.get('rank_of', 0)}"
    unit = " USD" if r["klass"] == "USD" else " bps"
    wr = f"{r['win_rate']:.4f} ({r['wins']}/{r['trades']})" if r["trades"] else "—"
    return [rk, r["model"] + (" · " + r["address"] if r.get("address") else "") + (f" · window {r['window']['t0_date']} … {r['window']['t1_date']}" if r.get("window") else ""),
            _f(r["total_pnl"]) + unit, r["roi"], wr, _f(r["biggest_win"]) + (unit if r["biggest_win"] is not None else ""),
            _f(r["biggest_loss"]) + (unit if r["biggest_loss"] is not None else ""), str(r["trades"]), _f(r["fees"]) + unit]


def render_markdown(m: dict) -> str:
    out = [f"# The AI board entry as of {m['as_of']} (PREREG A29)", "",
           f"Columns are the venue's (\"AI Traders\" board); numbers are the chain's and the pinned tape's. SETTLED.md `{m['settled_sha256'][:16]}…`, marker `{m['marker_sha256'][:8]}…`, endpoint `{m['endpoint']}`.", "",
           "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in m["rows"]:
        out.append("| " + " | ".join(_row_cells(r)) + " |")
    out.append("")
    pm = m["population"]
    out.append(f"Population days read: {', '.join(pm['days'])}; void days excluded (R116): {', '.join(pm['void_days_excluded']) or 'none'}. "
               f"Controls are ranked with the forks; the bps class is one unit of notional per episode, never USD.")
    if m["record_not_graded"]:
        out.append("")
        out.append("Record rows not graded here: " + "; ".join(f"cohort {x['cohort_date']}: {x['reason']}" for x in m["record_not_graded"]) + ".")
    if m["record_outside_windows"]:
        out.append("")
        out.append("On the record, before every graded window, not on the board: " + "; ".join(
            f"{x['capture']} ({x['dir']}, tx {str((x['tx_hashes'] or [''])[0])[:14]}…)" for x in m["record_outside_windows"]) + ".")
    out.append("")
    out.append("Rules: " + "; ".join(f"**{k}** {v}" for k, v in m["rules"].items()))
    out.append("")
    out.append(m["what_is_not_claimed"])
    return "\n".join(out) + "\n"


def render_html_section(m: dict) -> str:
    import html as _h
    parts = [f'<section id="ai-board"><h2>The AI board entry as of {_h.escape(m["as_of"])} (A29)</h2>',
             '<p class="lead">The venue\'s "AI Traders" board is empty. These are its columns filled by the chain and the pinned tape: the record\'s '
             'account in USD per arena window, the paper forks and their random-entry controls in basis points of one unit per episode. ROI is never '
             f'computed (SETTLED.md 4). Rank is within a unit class only. Machine-readable: <code>{_h.escape(m["endpoint"])}</code>.</p>',
             '<div class="wrap"><table><thead><tr>' + "".join(f"<th>{_h.escape(c)}</th>" for c in COLUMNS) + "</tr></thead><tbody>"]
    for r in m["rows"]:
        cells = _row_cells(r)
        parts.append("<tr>" + "".join(f'<td class="{"mono" if i == 1 else "num"}">{_h.escape(c)}</td>' for i, c in enumerate(cells)) + "</tr>")
    parts.append("</tbody></table></div>")
    pm = m["population"]
    parts.append(f'<p class="lead">Population days read: {_h.escape(", ".join(pm["days"]))}; void days excluded: {_h.escape(", ".join(pm["void_days_excluded"]) or "none")}.'
                 + (" Record rows not graded here: " + _h.escape("; ".join(f"cohort {x['cohort_date']}: {x['reason']}" for x in m["record_not_graded"])) + "." if m["record_not_graded"] else "")
                 + "</p>")
    parts.append(f'<p class="lead">{_h.escape(m["what_is_not_claimed"])}</p></section>')
    return "\n".join(parts)


def board_json(m: dict) -> str:
    return json.dumps(m, indent=2) + "\n"


def write_board(m: dict, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = board_json(m).encode("utf-8")
    md = render_markdown(m).encode("utf-8")
    paths = {"json": out_dir / f"ai_board_{m['as_of']}.json", "md": out_dir / f"ai_board_{m['as_of']}.md", "latest": out_dir / "ai_board_latest.json"}
    paths["json"].write_bytes(js)
    paths["md"].write_bytes(md)
    paths["latest"].write_bytes(js)
    return {k: sha256_file(p) for k, p in paths.items()}


def check_latest(board_dir: Path) -> str:
    dated = sorted(p for p in board_dir.glob("ai_board_*.json") if re.match(r"^ai_board_\d{4}-\d{2}-\d{2}\.json$", p.name))
    if not dated:
        raise AdapterError("S101: no dated board file")
    latest = board_dir / "ai_board_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        raise AdapterError(f"S101: ai_board_latest.json is not byte-equal to {dated[-1].name}")
    return dated[-1].name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.arena_ai_board", description="The AI board entry (PREREG A29). Pure; no network.")
    p.add_argument("--as-of", required=True)
    p.add_argument("--arena-dir", default=str(ARENA_DIR))
    p.add_argument("--vps-dir", default=str(led.VPS_DIR))
    p.add_argument("--out-dir", default=str(BOARD_DIR))
    p.add_argument("--settled", default=str(SETTLED))
    p.add_argument("--marker", default=str(led.MARKER))
    p.add_argument("--live-dir", default=str(LIVE_DIR))
    a = p.parse_args(argv)
    try:
        m = board(a.as_of, Path(a.arena_dir), Path(a.vps_dir), Path(a.settled), Path(a.marker), Path(a.live_dir))
        shas = write_board(m, Path(a.out_dir))
        check_latest(Path(a.out_dir))
    except AdapterError as exc:
        print(f"AI BOARD REFUSED: {exc}")
        return 1
    print(f"AI BOARD ENTRY as of {m['as_of']}: rows {len(m['rows'])} (USD {sum(1 for r in m['rows'] if r['klass'] == 'USD')}, bps {sum(1 for r in m['rows'] if r['klass'] == 'bps')}); "
          f"population days {len(m['population']['days'])}, void excluded {list(m['population']['void_days_excluded'])}; not graded {len(m['record_not_graded'])}")
    for r in m["rows"]:
        print("  " + " | ".join(_row_cells(r)))
    for k, v in shas.items():
        print(f"  {k} sha256 {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
