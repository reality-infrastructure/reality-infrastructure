"""PREREG A43 (P35) — OUT-GRIND: the pulled bid, the shots read, the HALT line.

  pulled  R189  L5M_pulled_bid: L4M's call (A42 R179), kept only when the tape of record's mid for the perp is on the
                favorite's side at the call, cancelled at the first tape-of-record row whose mid is on the other side;
                a print fills it only up to the pull time plus 5 000 ms. One variable against L4M: the cancel.
  shots   R185  the cumulative read over full tape days from 2026-11-12: kill 1 (the sum at or below -10.000), kill 2
                (150 shots: the sum at or below zero or the control's), kill 3 (600 shots, not cleared), kill 4 (L4M
                only: the read of 2026-11-17), cleared (150 shots: R181's test and the mean above two standard errors).
          R189  L5M becomes the leg of record on the read that retires L4M, with every shot it already has.
          R190  both retired: the thesis is CLOSED only on the adverse-selection fact, on 150 shots of each variant.
  halt    R187  hours without a capture, per leg, in the same words every day.

  S117  pure: pinned files in, bytes out; no network, no clock, no randomness; byte-equal on re-run.

`l2_maker.py` (A42) is imported and not changed. Nothing here sends an order.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path

from rights_events import call_ledger as cl
from rights_events import l2_maker as mk

L2_DIR = mk.DIR.parent                                   # calls/l2_favorite
PULLED_DIR = mk.DIR / "pulled"
PULLED_LEGS_DIR = PULLED_DIR / "legs"
SHOTS_DIR = mk.DIR / "shots"
HALT_DIR = L2_DIR / "halt"
CAPTURES_DIR = L2_DIR / "captures"
LEDGER_DIR = L2_DIR / "ledger"

L4M, CMM, L5M = mk.LEG, mk.CONTROL, "L5M_pulled_bid"
TAKER_LEGS = ("L2F_favorite", "L3T_tape_side", "CMF_coinflip")
ENTRY_TOL_MS = 15_000
PULL_LATENCY_MS = 5_000
FIRST_DAY = "2026-11-12"                                 # the first full tape day (A42.1)
KILL_SUM = -10.0                                         # per USD staked: -110 USD of paper at one 11 USDC ticket a shot
N_BENCH, N_BUDGET = 150, 600
LAST_DAY_L4M = "2026-11-16"                              # R181's fifth full tape day; read on 2026-11-17 (kill 4)
SE_MULT = 2.0
HOUR_MS = 3_600_000
KIND_PULLED, KIND_SHOTS, KIND_HALT = "l2_pulled_table", "l2_shots_read", "l2_halt_line"
NO_CALL = "NO_CALL_TAPE_SIDE"
NOT_CLAIMED = ("Paper. L5M's cancel is assumed to take 5 000 ms and that is counted against the leg; only a live order measures it. "
               "Not modelled: the bid's own effect on the book, partial fills, the maker's fee. No return is promised; nothing here "
               "sends an order.")


# ----------------------------------------------------------------------------- R189: the pulled bid
def _mid(row: dict | None, perp: str) -> Decimal | None:
    return mk._d((row or {}).get("mids", {}).get(perp)) if row else None


def _on_side(side: str, mid: Decimal, thr: Decimal) -> bool:
    """YES needs mid > threshold; a mid exactly at the threshold is the NO side (L3T's rule)."""
    return (mid > thr) if side == "YES" else (mid <= thr)


def newest_at_or_before(rows: list[dict], ms: int) -> dict | None:
    lo, hi = 0, len(rows)
    while lo < hi:
        m = (lo + hi) // 2
        if int(rows[m]["ms"]) <= ms:
            lo = m + 1
        else:
            hi = m
    return rows[lo - 1] if lo else None


def entry_and_pull(side: str, perp: str, thr: Decimal, t_call: int, expiry_ms: int, tape_rows: list[dict]) -> dict:
    """R189: the entry check at the call and the first row after it on the other side (the pull)."""
    r0 = newest_at_or_before(tape_rows, t_call)
    m0 = _mid(r0, perp) if r0 is not None and t_call - int(r0["ms"]) <= ENTRY_TOL_MS else None
    if m0 is None:
        return {"enter": False, "reason": "no tape-of-record mid within 15 s before the call", "entry_row_ms": None, "entry_mid": None, "pull_ms": None}
    if not _on_side(side, m0, thr):
        return {"enter": False, "reason": "the perp's mid is on the other side of the threshold at the call", "entry_row_ms": int(r0["ms"]),
                "entry_mid": str(m0), "pull_ms": None}
    pull_ms, pull_mid = None, None
    for r in tape_rows:
        ms = int(r["ms"])
        if ms <= t_call:
            continue
        if ms >= expiry_ms:
            break
        m = _mid(r, perp)
        if m is not None and not _on_side(side, m, thr):
            pull_ms, pull_mid = ms, str(m)
            break
    return {"enter": True, "reason": None, "entry_row_ms": int(r0["ms"]), "entry_mid": str(m0), "pull_ms": pull_ms, "pull_mid": pull_mid}


def _prints_by_outcome(rows: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    seen: set = set()
    for r in rows:
        if r.get("kind") == "trade" and r.get("outcome") is not None:
            key = (r.get("coin"), r.get("tid"))
            if key not in seen:
                seen.add(key)
                out.setdefault(int(r["outcome"]), []).append(r)
    for o in out:
        out[o].sort(key=lambda x: (int(x.get("time") or 0), int(x.get("tid") or 0)))
    return out


def _leg_row(cs: list[dict]) -> dict:
    called = [c for c in cs if c["status"] != NO_CALL]
    filled = [c for c in called if c["status"] == "FILLED"]
    graded = [c for c in filled if c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]
    unf = [c for c in called if c["status"] == "UNFILLED" and c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]
    pays = [c["payoff_1usd"] for c in graded]
    right = sum(1 for c in graded if c["bit"] == cl.BIT_RIGHT)
    return {"l4m_calls": len(cs), "no_call_tape_side": len(cs) - len(called), "calls": len(called), "pulled": sum(1 for c in called if c.get("pull_ms") is not None),
            "filled": len(filled), "fill_rate": (round(len(filled) / len(called), 4) if called else None),
            "filled_resolved": len(graded), "right": right, "hit_rate_filled": (round(right / len(graded), 4) if graded else None),
            "mean_p_filled": (round(mk._mean([float(c["p"]) for c in graded]), 6) if graded else None),
            "payoff_sum_usd": (round(math.fsum(pays), 6) if graded else None), "payoff_mean": (round(mk._mean(pays), 6) if graded else None),
            "unfilled_resolved": len(unf),
            "hit_rate_unfilled": (round(sum(1 for c in unf if c["bit"] == cl.BIT_RIGHT) / len(unf), 4) if unf else None),
            "mean_p_unfilled": (round(mk._mean([float(c["p"]) for c in unf]), 6) if unf else None)}


def pulled_table(day: str, tape_dir: Path, maker_dir: Path = mk.DIR, leg_path: Path | None = None) -> dict:
    """L5M's day: every L4M call of the day's maker table, re-read with the entry check and the pull."""
    base = mk.table(day, tape_dir, maker_dir)                                        # A42's table, recomputed from the same pins
    leg_path = leg_path or (PULLED_LEGS_DIR / f"{L5M}.json")
    p_day, p_prev = mk.l2tape_path(maker_dir, day), mk.l2tape_path(maker_dir, cl._prev_day(day))
    prints = _prints_by_outcome(mk.read_l2tape(p_prev)[0] + mk.read_l2tape(p_day)[0])
    tape_rows = sorted(cl.read_tape(cl.tape_path(tape_dir, cl._prev_day(day)))[0] + cl.read_tape(cl.tape_path(tape_dir, day))[0]
                       + cl.read_tape(cl.tape_path(tape_dir, cl._next_day(day)))[0], key=lambda r: int(r["ms"]))
    tape_pins = dict(base["tape_pins"])
    t_prev = cl.tape_path(tape_dir, cl._prev_day(day))
    if t_prev.exists():
        tape_pins[t_prev.name] = mk.sha256_file(t_prev)

    calls = []
    for c in base["calls"]:
        if c["leg"] != L4M:
            continue
        p, thr = Decimal(c["p"]), mk._d(c["threshold"])
        ep = entry_and_pull(c["side"], c["perp"], thr, int(c["called_ms"]), int(c["expiry_ms"]), tape_rows)
        row = {"leg": L5M, "outcome": c["outcome"], "perp": c["perp"], "threshold": c["threshold"], "expiry_ms": c["expiry_ms"],
               "called_ms": c["called_ms"], "side": c["side"], "p": c["p"], "contracts": c["contracts"], "bit": c["bit"], "gap": c["gap"],
               "entry_row_ms": ep["entry_row_ms"], "entry_mid": ep["entry_mid"], "pull_ms": ep["pull_ms"], "pull_mid": ep.get("pull_mid"),
               "l4m_status": c["status"]}
        if not ep["enter"]:
            row.update({"status": NO_CALL, "reason": ep["reason"], "fill_print": None, "payoff_1usd": None})
        else:
            end = int(c["expiry_ms"]) if ep["pull_ms"] is None else min(int(c["expiry_ms"]), ep["pull_ms"] + PULL_LATENCY_MS + 1)
            fill = mk.first_fill(c["side"], p, prints.get(int(c["outcome"]), []), int(c["called_ms"]), end)
            bit = c["bit"] if c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG) else None
            row.update({"status": "FILLED" if fill else "UNFILLED", "reason": None, "fill_print": fill,
                        "payoff_1usd": mk.payoff(bit, p) if fill else None})
        calls.append(row)

    pins = dict(base["pins"])
    pins[leg_path.name] = mk.sha256_file(leg_path)
    return {"kind": KIND_PULLED, "prereg": "A43 R189", "day": day, "partial_day": base["partial_day"],
            "counted": not base["partial_day"], "markets_expiring_in_day": base["markets_expiring_in_day"],
            "legs": {L5M: _leg_row(calls), L4M: base["legs"][L4M], CMM: base["legs"][CMM]},
            "calls": calls, "pins": pins, "tape_pins": tape_pins, "entry_tol_ms": ENTRY_TOL_MS, "pull_latency_ms": PULL_LATENCY_MS,
            "not_claimed": NOT_CLAIMED}


def render_pulled(doc: dict) -> str:
    f = mk._f
    r, a, c = doc["legs"][L5M], doc["legs"][L4M], doc["legs"][CMM]
    L = [f"# The pulled bid — L5M, {doc['day']} (PREREG A43 R189)", "",
         "L4M's call, kept only when the tape of record's mid is on the favorite's side at the call and cancelled when it crosses; "
         "a print fills it only up to the pull plus 5 000 ms. "
         + ("**Partial day: printed, not counted (R184).**" if doc["partial_day"] else "A full tape day."), "",
         f"L4M's calls: {r['l4m_calls']}; refused at entry ({NO_CALL}): {r['no_call_tape_side']}; L5M's calls: {r['calls']}; pulled before expiry: {r['pulled']}.", "",
         "| leg | calls | filled | fill rate | filled and resolved | right | hit rate (filled) | mean p (filled) | payoff sum (USD) | mean a filled call | hit rate (unfilled) |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, x in ((L5M, r), (L4M, a), (CMM, c)):
        L.append(f"| {name} | {x['calls']} | {x['filled']} | {f(x['fill_rate'])} | {x['filled_resolved']} | {x['right']} | {f(x['hit_rate_filled'])} | "
                 f"{f(x['mean_p_filled'])} | {f(x['payoff_sum_usd'], 3, True)} | {f(x['payoff_mean'], 3, True)} | {f(x['hit_rate_unfilled'])} |")
    L += ["", "L5M decides nothing while L4M is the leg of record (R189).", "", doc["not_claimed"], ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- R185: the shots read
def _stats(pays: list[float]) -> dict:
    n = len(pays)
    s = math.fsum(pays)
    mean = s / n if n else None
    sd = math.sqrt(math.fsum((x - mean) ** 2 for x in pays) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    return {"n": n, "sum": s, "mean": mean, "sd": sd, "se": se}


def verdict_at(st: dict, control_sum: float, day: str, has_date: bool) -> tuple[str, str]:
    """R185 at one read. Kill 1, then (at 150 shots) kill 2 or cleared, then kill 3, then (L4M only) kill 4."""
    n, s = st["n"], st["sum"]
    if n and s <= KILL_SUM:
        return "RETIRED", f"kill 1: the payoff sum {s:+.3f} is at or below {KILL_SUM:+.3f}"
    if n >= N_BENCH:
        if s <= 0 or s <= control_sum:
            return "RETIRED", f"kill 2: at {n} shots the sum {s:+.3f} is at or below zero or the control's {control_sum:+.3f}"
        if st["se"] is not None and st["mean"] > SE_MULT * st["se"]:
            return "CLEARED", f"at {n} shots the sum {s:+.3f} is above zero and the control's {control_sum:+.3f}, and the mean {st['mean']:+.4f} is above two standard errors ({SE_MULT * st['se']:.4f})"
    if n >= N_BUDGET:
        return "RETIRED", f"kill 3: {n} shots and not cleared"
    if has_date and day >= LAST_DAY_L4M:
        return "RETIRED", f"kill 4: the read after {LAST_DAY_L4M} and not cleared (R181's five days)"
    return "CONTINUES", f"{n} shots, sum {s:+.3f}" if n else "no shots yet"


def _shot_calls(doc: dict, leg: str) -> list[dict]:
    return [c for c in doc["calls"] if c["leg"] == leg and c["status"] == "FILLED" and c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]


def _selection(docs: list[dict], leg: str) -> dict:
    """R190's fact: the filled hit rate against the filled mean p, and the unfilled against theirs."""
    fil = [c for d in docs for c in _shot_calls(d, leg)]
    unf = [c for d in docs for c in d["calls"] if c["leg"] == leg and c["status"] == "UNFILLED" and c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]

    def hr(cs):
        return (sum(1 for c in cs if c["bit"] == cl.BIT_RIGHT) / len(cs)) if cs else None

    def mp(cs):
        return mk._mean([float(c["p"]) for c in cs]) if cs else None
    out = {"filled": len(fil), "hit_rate_filled": hr(fil), "mean_p_filled": mp(fil), "unfilled": len(unf), "hit_rate_unfilled": hr(unf), "mean_p_unfilled": mp(unf)}
    out["adverse"] = bool(fil and unf and out["hit_rate_filled"] < out["mean_p_filled"] and out["hit_rate_unfilled"] > out["mean_p_unfilled"])
    return out


def shots(day: str, maker_dir: Path = mk.DIR) -> dict:
    """The cumulative read through `day` (the read is made on the next day), every earlier read replayed in order."""
    pulled_dir = maker_dir / "pulled"
    days, d = [], FIRST_DAY
    while d <= day:
        days.append(d)
        d = cl._next_day(d)
    state = {L4M: {"status": "CONTINUES", "why": "no read yet", "read_day": None}, L5M: {"status": "SHADOW", "why": "L4M is the leg of record", "read_day": None}}
    pays = {L4M: [], L5M: [], CMM: []}
    used: dict[str, list[dict]] = {L4M: [], L5M: []}
    reads, pins, missing, partial = [], {}, [], []
    for dd in days:
        pm, pp = maker_dir / f"maker_{dd}.json", pulled_dir / f"pulled_{dd}.json"
        dm = json.loads(pm.read_text(encoding="utf-8")) if pm.exists() else None
        dp = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
        if dm is None:
            missing.append(pm.name)
        if dp is None:
            missing.append(pp.name)
        if dm is not None:
            pins[pm.name] = mk.sha256_file(pm)
            if dm["partial_day"]:
                partial.append(dd)
            else:
                pays[L4M] += [c["payoff_1usd"] for c in _shot_calls(dm, L4M)]
                pays[CMM] += [c["payoff_1usd"] for c in _shot_calls(dm, CMM)]
                used[L4M].append(dm)
        if dp is not None:
            pins[pp.name] = mk.sha256_file(pp)
            if not dp["partial_day"]:
                pays[L5M] += [c["payoff_1usd"] for c in _shot_calls(dp, L5M)]
                used[L5M].append(dp)
        st4, st5, ctl = _stats(pays[L4M]), _stats(pays[L5M]), math.fsum(pays[CMM])
        if state[L4M]["status"] == "CONTINUES":
            v, why = verdict_at(st4, ctl, dd, has_date=True)
            state[L4M] = {"status": v, "why": why, "read_day": dd}
            if v == "CLEARED":
                state[L5M] = {"status": "SHADOW", "why": "L4M cleared; L5M stays a shadow (R189)", "read_day": dd}
            elif v == "RETIRED":
                state[L5M] = {"status": "CONTINUES", "why": "the leg of record from this read (R189)", "read_day": dd}
        if state[L4M]["status"] == "RETIRED" and state[L5M]["status"] == "CONTINUES":
            v, why = verdict_at(st5, ctl, dd, has_date=False)
            state[L5M] = {"status": v, "why": why, "read_day": dd}
        reads.append({"day": dd, L4M: {"n": st4["n"], "sum": round(st4["sum"], 6), "status": state[L4M]["status"]},
                      L5M: {"n": st5["n"], "sum": round(st5["sum"], 6), "status": state[L5M]["status"]},
                      CMM: {"n": len(pays[CMM]), "sum": round(ctl, 6)}})

    def rnd(st):
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in st.items()}
    legs = {L4M: {**rnd(_stats(pays[L4M])), **state[L4M]}, L5M: {**rnd(_stats(pays[L5M])), **state[L5M]},
            CMM: {"n": len(pays[CMM]), "sum": round(math.fsum(pays[CMM]), 6)}}
    record = L4M if state[L4M]["status"] != "RETIRED" else L5M
    thesis = {"status": "OPEN", "why": "a leg is alive or cleared"}
    if state[L4M]["status"] == "RETIRED" and state[L5M]["status"] == "RETIRED":
        s4, s5 = _selection(used[L4M], L4M), _selection(used[L5M], L5M)
        enough = legs[L4M]["n"] >= N_BENCH and legs[L5M]["n"] >= N_BENCH
        closed = enough and s4["adverse"] and s5["adverse"]
        thesis = {"status": "CLOSED" if closed else "NOT CLOSED", "selection": {L4M: s4, L5M: s5},
                  "why": ("R190: on at least 150 shots of each variant the filled calls hit below their mean p and the unfilled above theirs" if closed else
                          "both legs are retired but R190's fact does not hold on 150 shots of each; the amendment names what the tables show to be most broken")}
    return {"kind": KIND_SHOTS, "prereg": "A43 R185, R189, R190", "through_day": day, "read_on": cl._next_day(day), "first_day": FIRST_DAY,
            "leg_of_record": record, "legs": legs, "reads": reads, "thesis": thesis, "partial_days_not_counted": partial, "missing_tables": missing,
            "pins": pins, "rule": {"kill_sum": KILL_SUM, "n_bench": N_BENCH, "n_budget": N_BUDGET, "last_day_l4m": LAST_DAY_L4M, "se_mult": SE_MULT},
            "not_claimed": NOT_CLAIMED}


def render_shots(doc: dict) -> str:
    def g(x, nd=3):
        return "—" if x is None else f"{x:+.{nd}f}"
    L = [f"# The shots read through {doc['through_day']} (PREREG A43 R185; read on {doc['read_on']})", "",
         "A shot is one call FILLED and resolved on a full tape day from 2026-11-12. Kill 1: the sum at or below −10.000 (−110 USD of paper at one "
         "11 USDC ticket a shot). At 150 shots: kill 2 (the sum at or below zero or the control's) or cleared (also the mean above two standard "
         "errors). Kill 3: 600 shots. Kill 4 (L4M only): the read of 2026-11-17.", "",
         f"**Leg of record: {doc['leg_of_record']}.** Thesis: {doc['thesis']['status']} ({doc['thesis']['why']}).", "",
         "| leg | shots | payoff sum (USD) | mean a shot | two standard errors | status | why |", "|---|---:|---:|---:|---:|---|---|"]
    for leg in (L4M, L5M):
        r = doc["legs"][leg]
        L.append(f"| {leg} | {r['n']} | {g(r['sum'])} | {g(r['mean'], 4)} | {'—' if r['se'] is None else format(SE_MULT * r['se'], '.4f')} | {r['status']} | {r['why']} |")
    c = doc["legs"][CMM]
    L += [f"| {CMM} (the control) | {c['n']} | {g(c['sum'])} | | | | |", ""]
    if doc["partial_days_not_counted"]:
        L += ["Partial days, not counted: " + ", ".join(doc["partial_days_not_counted"]) + ".", ""]
    if doc["missing_tables"]:
        L += ["Tables not on the record (their days are not counted): " + ", ".join(doc["missing_tables"]) + ".", ""]
    L += [doc["not_claimed"], ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- R187: the HALT line
def _hhmm(ms: int, d0: int) -> str:
    m = (ms - d0) // 60_000
    return f"{m // 60:02d}:{m % 60:02d}"


def _halt(times: list[int], d0: int) -> dict:
    """Hours of the day holding no capture, and the longest silence, measured to the day's edges."""
    ts = sorted(t for t in times if d0 <= t < d0 + mk.DAY_MS)
    hours = {(t - d0) // HOUR_MS for t in ts}
    edges = [d0] + ts + [d0 + mk.DAY_MS]
    gap, a, b = max(((y - x, x, y) for x, y in zip(edges, edges[1:])), key=lambda z: (z[0], -z[1]))
    return {"hours_without": 24 - len(hours), "captures": len(ts), "longest_ms": gap, "from": _hhmm(a, d0), "to": _hhmm(b, d0) if b < d0 + mk.DAY_MS else "24:00"}


def halt_line(leg: str, day: str, h: dict, resolved) -> str:
    mins = h["longest_ms"] // 60_000
    return (f"HALT {leg} ({day}): {h['hours_without']} of 24 hours without a capture; longest {mins // 60} h {mins % 60} min "
            f"from {h['from']}Z to {h['to']}Z; resolved calls {'—' if resolved is None else resolved}.")


def halt(day: str, maker_dir: Path = mk.DIR, captures_dir: Path = CAPTURES_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    d0 = cl.day_ms(day)
    pins = {}
    p_tape = mk.l2tape_path(maker_dir, day)
    tape_times = [int(r["t_ms"]) for r in mk.read_l2tape(p_tape)[0]]
    if p_tape.exists():
        pins[p_tape.name] = mk.sha256_file(p_tape)
    cap_times = []
    for p in sorted(captures_dir.glob(f"*outcomes_{day}T????Z.json")):
        m = re.search(r"outcomes_\d{4}-\d{2}-\d{2}T(\d{2})(\d{2})Z\.json$", p.name)
        if m:
            cap_times.append(d0 + int(m.group(1)) * HOUR_MS + int(m.group(2)) * 60_000)
            pins[p.name] = mk.sha256_file(p)
    resolved: dict[str, int | None] = {}
    pm, pp, pr = maker_dir / f"maker_{day}.json", maker_dir / "pulled" / f"pulled_{day}.json", ledger_dir / f"resolved_{day}.json"
    dm = json.loads(pm.read_text(encoding="utf-8")) if pm.exists() else None
    dp = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
    dr = json.loads(pr.read_text(encoding="utf-8")) if pr.exists() else None
    for p in (pm, pp, pr):
        if p.exists():
            pins[p.name] = mk.sha256_file(p)
    resolved[L4M] = dm["legs"][L4M]["filled_resolved"] if dm else None
    resolved[CMM] = dm["legs"][CMM]["filled_resolved"] if dm else None
    resolved[L5M] = dp["legs"][L5M]["filled_resolved"] if dp else None
    for leg in TAKER_LEGS:
        resolved[leg] = (sum(1 for c in dr["calls"] if c.get("leg") == leg and c.get("bit") in (cl.BIT_RIGHT, cl.BIT_WRONG)) if dr else None)
    ht, hc = _halt(tape_times, d0), _halt(cap_times, d0)
    legs = {}
    for leg in (L4M, CMM, L5M):
        legs[leg] = {**ht, "source": "the book tape", "resolved": resolved[leg], "line": halt_line(leg, day, ht, resolved[leg])}
    for leg in TAKER_LEGS:
        legs[leg] = {**hc, "source": "the hourly capture", "resolved": resolved[leg], "line": halt_line(leg, day, hc, resolved[leg])}
    return {"kind": KIND_HALT, "prereg": "A43 R187", "day": day, "legs": legs, "halted": sorted(k for k, v in legs.items() if v["hours_without"] >= 1), "pins": pins}


def render_halt(doc: dict) -> str:
    return "\n".join([f"# HALT — hours without a capture, {doc['day']} (PREREG A43 R187)", ""] + [doc["legs"][k]["line"] for k in (L4M, CMM, L5M) + TAKER_LEGS] + [""])


# ----------------------------------------------------------------------------- files
def _write(doc: dict, text: str, out_dir: Path, stem: str, key: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = mk.dumps(doc).encode("utf-8")
    (out_dir / f"{stem}_{key}.json").write_bytes(body)
    (out_dir / f"{stem}_{key}.md").write_bytes(text.encode("utf-8"))
    dated = sorted(p.name for p in out_dir.glob(f"{stem}_????-??-??.json"))
    if dated and dated[-1] == f"{stem}_{key}.json":
        (out_dir / f"{stem}_latest.json").write_bytes(body)


def check_latest(out_dir: Path, stem: str) -> str:
    tag = stem.upper()
    dated = sorted(out_dir.glob(f"{stem}_????-??-??.json"))
    if not dated:
        return f"{tag} LATEST: no dated file"
    latest = out_dir / f"{stem}_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        return f"{tag} LATEST REFUSED: {stem}_latest.json is not byte-equal to {dated[-1].name}"
    return f"{tag} LATEST OK: {stem}_latest.json == {dated[-1].name}"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="l2_shots")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pulled")
    a.add_argument("--day", required=True)
    a.add_argument("--tape-dir", type=Path, required=True)
    a.add_argument("--no-write", action="store_true")
    b = sub.add_parser("shots")
    b.add_argument("--day", required=True, help="the last day read (D-1)")
    b.add_argument("--no-write", action="store_true")
    c = sub.add_parser("halt")
    c.add_argument("--day", required=True)
    c.add_argument("--no-write", action="store_true")
    sub.add_parser("check-latest")
    args = ap.parse_args(argv)
    if args.cmd == "pulled":
        doc = pulled_table(args.day, args.tape_dir)
        if not args.no_write:
            _write(doc, render_pulled(doc), PULLED_DIR, "pulled", args.day)
        print(render_pulled(doc))
    elif args.cmd == "shots":
        doc = shots(args.day)
        if not args.no_write:
            _write(doc, render_shots(doc), SHOTS_DIR, "shots", args.day)
        print(render_shots(doc))
    elif args.cmd == "halt":
        doc = halt(args.day)
        if not args.no_write:
            _write(doc, render_halt(doc), HALT_DIR, "halt", args.day)
        print(render_halt(doc))
    else:
        for d, s in ((PULLED_DIR, "pulled"), (SHOTS_DIR, "shots"), (HALT_DIR, "halt")):
            print(check_latest(d, s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
