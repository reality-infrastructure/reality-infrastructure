"""P12.2 — the FORWARD marker (P12.0, P12.1). Runs on the VPS beside the tape writer.

Every tick (about once a minute) it: reads the tape's newest rows (`tape_MIDS_<date>.jsonl`,
one JSON row per ~5 s with every declared coin's mid); polls the 28 leaders' public
`userFillsByTime` since the last poll and turns qualifying opens into F4 signals; opens a
PAPER episode per fork at the newest tape mid (one open episode per fork at a time) with the
book's half-spread read from `l2Book` at that moment (payload pinned verbatim, its sha on the
row); walks every open episode over the new mids and closes it at the first row 30 bps
against or at entry + 5 h (the second leg's half-spread read the same way); fires C1's one
random minute per coin per day (seeded by the amendment sha passed in); writes closed
episodes to `marks_<entry-date>.jsonl` and every signal seen to `signals_<date>.jsonl`.

It submits nothing. It signs nothing. It never imports or names a venue write tool (S73).
State survives a restart through `marker_state.json`. S72: if the tape's newest row is older
than six minutes at a tick, the UTC day is marked VOID for every fork (the sensor binds).

Usage (the VPS):
  python3 forward.py --tape-dir /root/poo-tape --out-dir /root/poo-marker \
      --seed <the day's amendment commit sha> [--poll-seconds 60]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HERE = Path(__file__).resolve().parent


def _load_marker():
    spec = importlib.util.spec_from_file_location("marker", HERE / "marker.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


mk = _load_marker()
FAM = json.loads((HERE / "families.json").read_bytes())
LEADERS = [l["address"] for l in json.loads((HERE / "leaders_2026-11-01.json").read_bytes())["leaders"] if l["kept"]]
COINS = tuple(FAM["declared_coins"])
STOP = float(FAM["exit"]["stop_bps"])
GATE = int(FAM["exit"]["gate_ms"])
FEE = float(FAM["costs"]["fee_bps_per_leg"])
MIN_NOTIONAL = float(FAM["families"]["F4"]["parameter"]["min_open_notional_usd"])
FORWARD_FAMILIES = ("F4", "C1")   # F1-F3 deleted by P12.1 (R84)


def now_ms() -> int:
    return int(time.time() * 1000)


def day_of(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d")


def post(body: dict, timeout: int = 20) -> bytes:
    req = urllib.request.Request(HL_INFO_URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def l2book_half_spread_bps(coin: str, pin_dir: Path, ms: int) -> tuple[float, str]:
    """(half-spread in bps of mid, 'l2Book:<sha256>'); on failure (None, 'l2Book:unavailable')
    and the episode's leg is charged the replay proxy, disclosed on the row."""
    try:
        raw = post({"type": "l2Book", "coin": coin})
        d = json.loads(raw)
        bid = float(d["levels"][0][0]["px"]); ask = float(d["levels"][1][0]["px"])
        mid = (bid + ask) / 2.0
        sha = hashlib.sha256(raw).hexdigest()
        pin_dir.mkdir(parents=True, exist_ok=True)
        (pin_dir / f"l2Book_{coin}_{ms}.json").write_bytes(raw)
        return (ask - bid) / 2.0 / mid * 10_000.0, f"l2Book:{sha}"
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, ValueError) as e:
        return float(FAM["costs"]["replay_spread_proxy_bps_per_leg"]), f"l2Book:unavailable:{type(e).__name__}"


class State:
    def __init__(self, path: Path):
        self.path = path
        self.d = {"last_fill_poll_ms": now_ms() - 60_000, "tape_offsets": {}, "open": {}, "c1_fired": {},
                  "void_days": [], "f4_dirs_today": {}, "seed": None}
        if path.exists():
            self.d.update(json.loads(path.read_text(encoding="utf-8")))

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.d, indent=1), encoding="utf-8", newline="\n")
        tmp.replace(self.path)


def append(path: Path, row: dict):
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def read_new_tape_rows(tape_dir: Path, st: State, days: list[str]) -> list[tuple[int, dict]]:
    out = []
    for day in days:
        p = tape_dir / f"tape_MIDS_{day}.jsonl"
        if not p.exists():
            continue
        off = int(st.d["tape_offsets"].get(day, 0))
        with p.open("rb") as f:
            f.seek(off)
            chunk = f.read()
        if not chunk:
            continue
        lines = chunk.split(b"\n")
        tail = lines.pop()  # possibly partial last line
        consumed = len(chunk) - len(tail)
        for ln in lines:
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if "ms" in r and "mids" in r:
                out.append((int(r["ms"]), r["mids"]))
        st.d["tape_offsets"][day] = off + consumed
    out.sort(key=lambda x: x[0])
    return out


def poll_leader_opens(st: State, until_ms: int, out_dir: Path) -> list[dict]:
    """New qualifying opens across all leaders since the last poll, as F4 signals."""
    start = int(st.d["last_fill_poll_ms"]) + 1
    sigs: list[dict] = []
    failures = 0
    for addr in LEADERS:
        try:
            raw = post({"type": "userFillsByTime", "user": addr, "startTime": start, "endTime": until_ms})
            fills = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            failures += 1
            append(out_dir / f"signals_{day_of(until_ms)}.jsonl", {"type": "poll_failure", "leader": addr, "ms": until_ms, "error": type(e).__name__})
            continue
        for coin in COINS:
            sigs.extend(mk.f4_leader_opens(fills, MIN_NOTIONAL, coin, addr))
        time.sleep(0.1)
    if failures < len(LEADERS):
        st.d["last_fill_poll_ms"] = until_ms
    return sorted(sigs, key=lambda s: s["ms"])


def open_episode(st: State, fork: str, family: str, coin: str, direction: int, sig: dict, row_ms: int, mid: float, pin_dir: Path):
    half, src = l2book_half_spread_bps(coin, pin_dir, row_ms)
    st.d["open"][fork] = {"family": family, "coin": coin, "direction": direction, "entry_ms": row_ms, "entry_px": mid,
                          "signal_ms": sig["ms"], "signal": {k: v for k, v in sig.items() if k not in ("ms", "direction", "family", "coin")},
                          "entry_spread_bps": half, "entry_spread_source": src, "seed": st.d.get("seed")}


def close_episode(st: State, fork: str, row_ms: int, px: float, reason: str, out_dir: Path, pin_dir: Path, funding_hint: float = 0.0):
    e = st.d["open"].pop(fork)
    half, src = l2book_half_spread_bps(e["coin"], pin_dir, row_ms)
    d = int(e["direction"])
    gross = d * (px - e["entry_px"]) / e["entry_px"] * 10_000.0
    cost = 2.0 * FEE + e["entry_spread_bps"] + half
    row = {"fork": fork, "family": e["family"], "coin": e["coin"], "direction": d, "entry_ms": e["entry_ms"], "entry_px": e["entry_px"],
           "exit_ms": row_ms, "exit_px": px, "exit_reason": reason, "gross_bps": gross, "cost_bps": cost,
           "funding_bps": funding_hint, "net_bps": gross - cost + funding_hint, "in_sample": False,
           "spread_bps_per_leg": (e["entry_spread_bps"] + half) / 2.0,
           "spread_source": f"{e['entry_spread_source']}|{src}", "signal": e["signal"], "signal_ms": e["signal_ms"],
           "trigger_latency_ms": e["entry_ms"] - e["signal_ms"], "seed": e.get("seed"),
           "funding_note": "forward rows carry funding 0 at write time; the hourly prints are applied at the day's pin from fundingHistory (A17)"}
    append(out_dir / f"marks_{day_of(e['entry_ms'])}.jsonl", row)


def tick(a, st: State):
    t = now_ms()
    today = day_of(t)
    yesterday = day_of(t - 86_400_000)
    rows = read_new_tape_rows(a.tape_dir, st, [yesterday, today])
    newest_ms = rows[-1][0] if rows else None
    fresh = newest_ms is not None and t - newest_ms <= 6 * 60_000
    # S72: the sensor binds
    if not fresh:
        if rows == [] and st.d["tape_offsets"].get(today, 0) == 0:
            pass  # the day's file has not started yet: not a void, just early
        elif today not in st.d["void_days"]:
            st.d["void_days"].append(today)
            append(a.out_dir / f"marks_{today}.jsonl", {"type": "void", "day": today, "ms": t, "reason": "S72 tape stale > 6 min"})
            print(f"[{today}] S72 VOID: tape stale", flush=True)
    # F4 signals since the last poll
    sigs = poll_leader_opens(st, t, a.out_dir) if newest_ms else []
    for s in sigs:
        append(a.out_dir / f"signals_{day_of(s['ms'])}.jsonl", dict(s, type="F4_signal"))
        st.d["f4_dirs_today"].setdefault(day_of(s["ms"]), []).append(s["direction"])
    pending_entries: dict[str, tuple[str, str, int, dict]] = {}
    for s in sigs:
        fork = f"F4:{s['coin']}"
        if fork not in st.d["open"] and fork not in pending_entries:
            pending_entries[fork] = ("F4", s["coin"], int(s["direction"]), s)
    # C1: one minute per coin per day
    for coin in COINS:
        key = f"{today}:{coin}"
        if key in st.d["c1_fired"]:
            continue
        minute = mk.c1_minute(st.d["seed"], coin, today)
        fire_ms = mk.day_start_ms(today) + minute * 60_000
        if t >= fire_ms and not fresh:
            st.d["c1_fired"][key] = {"minute": minute, "missed": "tape stale at the drawn minute (S72)"}
            append(a.out_dir / f"signals_{today}.jsonl", {"type": "C1_missed", "coin": coin, "day": today, "minute": minute, "ms": t})
            continue
        if t >= fire_ms:
            dirs = st.d["f4_dirs_today"].get(today, [])
            share = (sum(1 for x in dirs if x > 0) / len(dirs)) if dirs else 0.5
            direction = mk.c1_direction(st.d["seed"], coin, today, share)
            fork = f"C1:{coin}"
            st.d["c1_fired"][key] = {"minute": minute, "direction": direction, "long_share": share}
            if fork not in st.d["open"]:
                pending_entries[fork] = ("C1", coin, direction, {"ms": fire_ms, "minute": minute, "long_share": share})
    # walk the new mids: exits first, then entries at the newest row
    for ms, mids in rows:
        for fork in list(st.d["open"].keys()):
            e = st.d["open"][fork]
            px = mids.get(e["coin"])
            if px is None:
                continue
            px = float(px)
            adverse = -e["direction"] * (px - e["entry_px"]) / e["entry_px"] * 10_000.0
            if adverse >= STOP - 1e-9:
                close_episode(st, fork, ms, px, "stop", a.out_dir, a.pin_dir)
            elif ms - e["entry_ms"] >= GATE:
                close_episode(st, fork, ms, px, "gate", a.out_dir, a.pin_dir)
    if rows and pending_entries and fresh:  # no entry on a stale tape: the day is void (S72)
        ms, mids = rows[-1]
        for fork, (family, coin, direction, sig) in pending_entries.items():
            if fork in st.d["open"] or mids.get(coin) is None:
                continue
            open_episode(st, fork, family, coin, direction, sig, ms, float(mids[coin]), a.pin_dir)
            print(f"[{day_of(ms)}] OPEN {fork} {'L' if direction > 0 else 'S'} @ {mids[coin]} (signal {sig.get('ms')})", flush=True)
    st.save()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tape-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--seed", required=True, help="the day's amendment commit sha (C1's seed; recorded on every row)")
    p.add_argument("--poll-seconds", type=int, default=60)
    p.add_argument("--once", action="store_true")
    a = p.parse_args(argv)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    a.pin_dir = a.out_dir / "l2book"
    st = State(a.out_dir / "marker_state.json")
    st.d["seed"] = a.seed
    print(f"forward marker: {len(LEADERS)} leaders, coins {COINS}, forks {FORWARD_FAMILIES}, stop {STOP} bps, gate {GATE} ms, seed {a.seed}", flush=True)
    while True:
        try:
            tick(a, st)
        except Exception as e:  # keep the sensor's companion alive; every failure is a row
            append(a.out_dir / f"signals_{day_of(now_ms())}.jsonl", {"type": "tick_error", "ms": now_ms(), "error": repr(e)[:300]})
            print("tick error:", repr(e)[:200], flush=True)
        if a.once:
            return 0
        time.sleep(a.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
