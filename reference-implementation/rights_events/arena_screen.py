"""THE LEADER SCREEN (PREREG A20, R102–R104): whom the record would let a copier follow.

A pure function of one pinned arena capture (the pins and the window) and the pinned arena
JSON written by the arena run (the coverage and the settled figures it must agree with).
Every row of the cohort is re-settled from its sha-checked pages (S84) by the founder's
arithmetic (SETTLED.md), nine features are computed from the same fills, and nine written
criteria (R102, thresholds below) are applied. A row is SELECTED only if every criterion
holds; otherwise every failing criterion is printed with its number. A SELECTED row buys
nothing but a PAPER copy fork through a later amendment (R104). A partial window selects
nobody; an unstarted window is refused (S92).

No network. No clock. No reasoning as input (R96). Ranks nothing. Claims nothing about
anyone's profit.

Usage:
    python -m rights_events.arena_screen --capture CAPTURE --arena ARENA_JSON --out-prefix PREFIX
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from rights_events.adapters.agent_arena import (
    STATUS_FULL, _load_items, _page_pins, check_pages, coverage, day_of_ms,
    parse_arena_capture, settle, sha256_hex,
)
from rights_events.adapters.common import AdapterError
from rights_events.agent_arena import read_pages

SCREEN_KIND = "proof_of_outcome_leader_screen"
SELECTED = "SELECTED"
REFUSED = "REFUSED"
NOT_SCREENED = "NOT_SCREENED"

# R102 thresholds (A20). They change only by a later amendment.
CADENCE_MAX = Decimal("30")           # B: fills per active hour
CLOSES_MIN = 20                       # C: fills with closedPnl != 0
PERP_SHARE_MIN = Decimal("0.9")       # D: notional on coins not prefixed '@'
DAYS_MIN = 5                          # F: days with fills
CONCENTRATION_MAX = Decimal("0.5")    # G: max daily net / sum of positive daily nets
EXPOSURE_MAX = Decimal("0.25")        # H: gross exposure open at the window's end / notional
NET_BPS_MIN = Decimal("18.64")        # I: twice the copier's per-notional cost (A16)
MS_PER_HOUR = Decimal(3_600_000)

CRITERIA = {
    "A": f"coverage FULL",
    "B": f"cadence <= {CADENCE_MAX} fills per active hour",
    "C": f"closes >= {CLOSES_MIN}",
    "D": f"perp share >= {PERP_SHARE_MIN}",
    "E": "realized_ex_funding > 0 and net_with_funding > 0",
    "F": f"days with fills >= {DAYS_MIN} and positive days >= days with fills - 1",
    "G": f"day concentration <= {CONCENTRATION_MAX}",
    "H": f"open exposure at window end <= {EXPOSURE_MAX} of notional",
    "I": f"net bps of notional >= {NET_BPS_MIN}",
}


def _in_window(fills: list[dict], t0: int, t1: int) -> list[dict]:
    seen: set = set()
    out = []
    for f in fills:
        t = f.get("time")
        if not isinstance(t, int) or t < t0 or t > t1:
            continue
        tid = f.get("tid")
        if tid is not None:
            if tid in seen:
                continue
            seen.add(tid)
        out.append(f)
    out.sort(key=lambda f: (f["time"], str(f.get("tid", "")), str(f.get("hash", ""))))
    return out


def features(fills: list[dict], settled: dict) -> dict:
    """The nine features of R102 from the window's fills and the settled figures. Decimals
    from the payload's own strings; ratios are None when their denominator is zero."""
    n = len(fills)
    notional = Decimal(0)
    perp = Decimal(0)
    closes = 0
    position: dict[str, Decimal] = {}
    last_px: dict[str, Decimal] = {}
    days: set[str] = set()
    for f in fills:
        px, sz = Decimal(f["px"]), Decimal(f["sz"])
        notional += px * sz
        if not str(f["coin"]).startswith("@"):
            perp += px * sz
        if Decimal(f["closedPnl"]) != 0:
            closes += 1
        position[f["coin"]] = Decimal(f["startPosition"]) + (sz if f["side"] == "B" else -sz)
        last_px[f["coin"]] = px
        days.add(day_of_ms(f["time"]))
    hours = Decimal(1)
    if n > 1:
        hours = max((Decimal(fills[-1]["time"]) - Decimal(fills[0]["time"])) / MS_PER_HOUR, Decimal(1))
    exposure = sum((abs(p) * last_px[c] for c, p in position.items()), Decimal(0))
    daily = {d["day"]: d["net"] for d in settled["daily"]}
    positive_sum = sum((v for v in daily.values() if v > 0), Decimal(0))
    max_day = max(daily.values(), default=Decimal(0))
    positive_days = sum(1 for d in days if daily.get(d, Decimal(0)) > 0)
    return {
        "fills": n,
        "notional": notional,
        "active_hours": hours,
        "cadence_per_hour": (Decimal(n) / hours) if n else Decimal(0),
        "closes": closes,
        "perp_notional": perp,
        "perp_share": (perp / notional) if notional else None,
        "days_with_fills": len(days),
        "positive_days": positive_days,
        "max_daily_net": max_day,
        "positive_daily_sum": positive_sum,
        "day_concentration": (max_day / positive_sum) if positive_sum > 0 else None,
        "open_exposure_end": exposure,
        "exposure_share": (exposure / notional) if notional else None,
        "net_bps_of_notional": (settled["net_with_funding"] / notional * 10000) if notional else None,
    }


def verdict(status: str, feat: dict, settled: dict) -> list[str]:
    """R102: the letters of every failing criterion (empty = SELECTED)."""
    fails = []
    if status != STATUS_FULL:
        fails.append("A")
    if feat["cadence_per_hour"] > CADENCE_MAX:
        fails.append("B")
    if feat["closes"] < CLOSES_MIN:
        fails.append("C")
    if feat["perp_share"] is None or feat["perp_share"] < PERP_SHARE_MIN:
        fails.append("D")
    if not (settled["realized_ex_funding"] > 0 and settled["net_with_funding"] > 0):
        fails.append("E")
    if feat["days_with_fills"] < DAYS_MIN or feat["positive_days"] < feat["days_with_fills"] - 1:
        fails.append("F")
    if feat["day_concentration"] is None or feat["day_concentration"] > CONCENTRATION_MAX:
        fails.append("G")
    if feat["exposure_share"] is None or feat["exposure_share"] > EXPOSURE_MAX:
        fails.append("H")
    if feat["net_bps_of_notional"] is None or feat["net_bps_of_notional"] < NET_BPS_MIN:
        fails.append("I")
    return fails


def screen(capture_path: Path, arena_path: Path) -> dict:
    """The screen of one cohort as of the arena's date. Pure; raises AdapterError."""
    doc, boards = parse_arena_capture(capture_path.read_text(encoding="utf-8"))
    arena = json.loads(arena_path.read_text(encoding="utf-8"), parse_float=Decimal)
    c = boards.claim
    if arena.get("cohort_date") != c["cohort_date"] or arena.get("as_of") != c["as_of_date"]:
        raise AdapterError("the arena JSON is not this capture's (cohort or as-of differ)")
    win = c["window"]
    if not win["started"]:
        raise AdapterError(f"S92: cohort {c['cohort_date']}'s window has not started as of "
                           f"{c['as_of_date']}; nothing to screen")
    complete = bool(win["complete"])
    by_addr = {r["address"].lower(): r for r in arena.get("rows", [])}
    base = capture_path.parent
    actor = doc["actor"]["actor_id"].lower()
    rows_out = []
    for row in doc.get("rows", []):
        address = row["address"]
        if address.lower() == actor:
            continue  # the operator's RECORD row is graded, never screened as a leader
        ctx = f"rows[{address}]"
        arow = by_addr.get(address.lower())
        if arow is None:
            raise AdapterError(f"{ctx}: not in the arena JSON")
        try:
            fill_pins = _page_pins(row, "fills_pages", ctx)
            fund_pins = _page_pins(row, "funding_pages", ctx)
            fill_pages = read_pages(base / row["fills_file"])
            fund_pages = read_pages(base / row["funding_file"])
            check_pages(fill_pins, fill_pages, ctx + ".fills")
            check_pages(fund_pins, fund_pages, ctx + ".funding")
        except (AdapterError, OSError, KeyError) as exc:
            rows_out.append({"address": address, "status": "REFUSED", "verdict": REFUSED,
                             "fails": ["A"], "reason": str(exc), "features": None})
            continue
        fills = _in_window(_load_items(fill_pages, ctx + ".fills"), win["t0_ms"], win["t1_ms"])
        funding = _load_items(fund_pages, ctx + ".funding")
        s = settle(fills, funding, win["t0_ms"], win["t1_ms"], ctx)
        status, _reason = coverage(s["fills"], fill_pins, s["first_time_ms"], win["t0_ms"])
        # S91: the screen's settled figures must equal the arena run's, byte for byte as Decimals
        for k in ("fills", "realized_ex_funding", "funding", "net_with_funding"):
            mine, theirs = s[k], arow[k]
            if Decimal(str(mine)) != Decimal(str(theirs)):
                raise AdapterError(f"S91: {ctx}.{k} re-settled {mine} but the arena JSON says "
                                   f"{theirs}; the screen fails")
        if status != arow["status"] and arow["status"] != "RECORD":
            raise AdapterError(f"S91: {ctx} coverage re-read {status} but the arena says "
                               f"{arow['status']}")
        feat = features(fills, s)
        fails = verdict(status, feat, s)
        if complete:
            v = SELECTED if not fails else REFUSED
        else:
            v = NOT_SCREENED
        if v == SELECTED and status != STATUS_FULL:
            raise AdapterError(f"S90: {ctx} selected with coverage {status}")
        rows_out.append({"address": address, "status": status, "verdict": v, "fails": fails,
                         "features": feat,
                         "settled": {k: s[k] for k in ("fills", "realized_ex_funding", "funding",
                                                       "net_with_funding")}})
    rows_out.sort(key=lambda r: (r["verdict"] != SELECTED, r["status"] != STATUS_FULL,
                                 -(r["settled"]["net_with_funding"] if r.get("settled") else Decimal(0)),
                                 r["address"].lower()))
    selected = [r["address"] for r in rows_out if r["verdict"] == SELECTED]
    counts = {SELECTED: len(selected), REFUSED: sum(1 for r in rows_out if r["verdict"] == REFUSED),
              NOT_SCREENED: sum(1 for r in rows_out if r["verdict"] == NOT_SCREENED)}
    return {
        "kind": SCREEN_KIND,
        "cohort_date": c["cohort_date"],
        "as_of": c["as_of_date"],
        "window": {k: win[k] for k in ("t0_date", "t1_date", "days", "started", "complete")},
        "window_complete": complete,
        "capture_file": capture_path.name,
        "capture_sha256": sha256_hex(capture_path.read_bytes().replace(b"\r\n", b"\n")),
        "arena_file": arena_path.name,
        "arena_sha256": sha256_hex(arena_path.read_bytes().replace(b"\r\n", b"\n")),
        "criteria": CRITERIA,
        "thresholds": {"cadence_max_per_hour": CADENCE_MAX, "closes_min": CLOSES_MIN,
                       "perp_share_min": PERP_SHARE_MIN, "days_min": DAYS_MIN,
                       "concentration_max": CONCENTRATION_MAX, "exposure_max": EXPOSURE_MAX,
                       "net_bps_min": NET_BPS_MIN},
        "counts": counts,
        "selected": selected,
        "rows": rows_out,
        "what_a_selection_buys": ("R104: a PAPER copy fork on the cohort's next window by a later "
                                  "amendment the operator signs, one unit, marked at the independent "
                                  "tape's next mid after a stated latency, with C0 and C1 controls; "
                                  "never at the leader's own prices; never live. Nothing here opens, "
                                  "sizes or signs anything."),
        "what_is_not_claimed": ("No profit, no ranking, no prediction: who passed nine written tests "
                                "over one graded window, and who failed which."),
    }


def _s(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, Decimal):
        return format(x.quantize(Decimal("0.01")) if abs(x) >= 1 else x.quantize(Decimal("0.0001")), "f")
    return str(x)


def render_markdown(m: dict) -> str:
    out = [f"# Leader screen — cohort {m['cohort_date']} as of {m['as_of']} (PREREG A20)", ""]
    out.append(f"Window {m['window']['t0_date']} … {m['window']['t1_date']} "
               f"({m['window']['days']} days, {'complete' if m['window_complete'] else 'PARTIAL: nobody is screened'}). "
               f"Selected {m['counts'][SELECTED]}, refused {m['counts'][REFUSED]}, not screened {m['counts'][NOT_SCREENED]}.")
    out.append("")
    out.append("Criteria (R102): " + "; ".join(f"**{k}** {v}" for k, v in m["criteria"].items()))
    out.append("")
    out.append("| verdict | address | coverage | fails | fills | cadence/h | closes | perp share | net bps | concentration | exposure share | net with funding |")
    out.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in m["rows"]:
        f = r.get("features")
        if not f:
            out.append(f"| {r['verdict']} | `{r['address']}` | {r['status']} | {''.join(r['fails'])} | | | | | | | | {r.get('reason', '')} |")
            continue
        out.append(f"| {r['verdict']} | `{r['address']}` | {r['status']} | {''.join(r['fails']) or '—'} | {f['fills']} | "
                   f"{_s(f['cadence_per_hour'])} | {f['closes']} | {_s(f['perp_share'])} | {_s(f['net_bps_of_notional'])} | "
                   f"{_s(f['day_concentration'])} | {_s(f['exposure_share'])} | {_s(r['settled']['net_with_funding'])} |")
    out.append("")
    out.append(m["what_a_selection_buys"])
    out.append("")
    out.append(m["what_is_not_claimed"])
    out.append("")
    out.append(f"Inputs: `{m['capture_file']}` sha256 `{m['capture_sha256']}`; `{m['arena_file']}` sha256 `{m['arena_sha256']}`.")
    return "\n".join(out) + "\n"


def _json_default(o):
    if isinstance(o, Decimal):
        return format(o, "f")
    raise TypeError(type(o).__name__)


def screen_json(m: dict) -> str:
    return json.dumps(m, indent=2, default=_json_default, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rights_events.arena_screen",
                                description="The leader screen (PREREG A20). Pure; no trade.")
    p.add_argument("--capture", required=True)
    p.add_argument("--arena", required=True)
    p.add_argument("--out-prefix", required=True, help="writes <prefix>.json and <prefix>.md")
    a = p.parse_args(argv)
    try:
        m = screen(Path(a.capture), Path(a.arena))
    except AdapterError as exc:
        print(f"SCREEN REFUSED: {exc}")
        return 1
    prefix = Path(a.out_prefix)
    for suffix, text in ((".json", screen_json(m)), (".md", render_markdown(m))):
        path = prefix.with_name(prefix.name + suffix)
        path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
        print(f"wrote {path} sha256 {sha256_hex(path.read_bytes())}")
    print(f"LEADER SCREEN cohort {m['cohort_date']} as of {m['as_of']}: selected {m['counts'][SELECTED]}, "
          f"refused {m['counts'][REFUSED]}, not screened {m['counts'][NOT_SCREENED]}")
    for r in m["rows"]:
        if r["verdict"] == SELECTED:
            print(f"  SELECTED {r['address']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
