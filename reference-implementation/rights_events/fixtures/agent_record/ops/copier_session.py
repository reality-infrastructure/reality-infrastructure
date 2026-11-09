"""A38.2 (R157 as amended by the operator's word of 2026-11-09, "all of mine to do I'm authorizing you to do"):
THE SESSION'S PAIR under the standing go of A34 and the entry rule of R155.

One process, one window, at most one pair, one attempt per leg (S54). The venue is reached only through the
record's own stdio client to the same GDEX MCP server binary the hand used (gdex_stdio_client.Server, one
server process kept alive for the window so the preview's 60-second expiry is never spent on a cold start),
and every answer is saved verbatim beside the previews, as the hand's were.

  1. gdex_status, then one gdex_connect {accountRef} (R79's refresh), both saved.
  2. Poll the KEEP addresses' public fills through [start, end). The first qualifying open (a declared coin,
     notional >= 10 000 USD) is the signal (R155). None by `end` -> the MISS line, exit 3.
  3. gdex_preview_trade {kind: perp_open, coin, side, size} with one unit by R156 (BTC 0.00014; else the venue's
     minimum, 10 USD of notional at the mid, rounded up to szDecimals) -> the preview saved and written as
     gdex_preview_<previewId>.json -> capture_from_gdex_preview.py --live started (it polls the chain for the
     fill) -> gdex_execute_trade {previewId, userApproved: true} ONCE. A refusal (no previewId, an error text,
     a 403) is logged and ends the run with exit 4: nothing is retried, nothing else is sent.
  4. The exit (A34's terms, R60 automated): poll allMids every few seconds; at 30 bps adverse to the live fill
     price, or at the open fill's time + 5 h, gdex_preview_trade {kind: perp_close, coin} -> saved ->
     capture --live --open-capture <the open leg> started -> gdex_execute_trade ONCE. Exit 0 when the close
     capture is written.

Every step is a row in copier/session_<date>.jsonl with the sha256 of every file it wrote. The operator may
stop the process at any time; a stop before step 3 submits nothing; a stop during step 4 leaves the position
to the hand (the log says so). No key enters this file: the server reads the account store itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent            # .../fixtures/agent_record/ops
FIXTURES = HERE.parent                            # .../fixtures/agent_record
HL_INFO_URL = "https://api.hyperliquid.xyz/info"
COINS = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
MIN_NOTIONAL_USD = 10_000.0
UNIT_BTC = "0.00014"
VENUE_MIN_NOTIONAL_USD = 10.0
STOP_BPS = 30.0
GATE_MS = 18_000_000
ACCOUNT_REF = "acct_8c48b321e89c"
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
SERVER_CMD_DEFAULT = "npx.cmd -y @gemachdao/gdex-mcp-server@5.2.1"


# ----------------------------------------------------------------------------- pure
def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ms_of(date: str, hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    y, mo, d = (int(x) for x in date.split("-"))
    return int(dt.datetime(y, mo, d, h, m, tzinfo=dt.timezone.utc).timestamp() * 1000)


def iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def qualifying(fill: dict, leader: str) -> dict | None:
    if fill.get("coin") not in COINS:
        return None
    d = str(fill.get("dir", ""))
    if not d.startswith("Open"):
        return None
    px, sz = float(fill["px"]), float(fill["sz"])
    if px * sz < MIN_NOTIONAL_USD:
        return None
    return {"ms": int(fill["time"]), "leader": leader.lower(), "coin": fill["coin"], "direction": 1 if "Long" in d else -1,
            "leader_px": px, "leader_sz": sz, "leader_notional": px * sz, "tid": fill.get("tid"), "family": "F6"}


def unit_size(coin: str, mid: float, sz_decimals: int) -> str:
    """R156, as a decimal string the venue accepts."""
    if coin == "BTC":
        return UNIT_BTC
    step = 10.0 ** (-sz_decimals)
    n = math.ceil((VENUE_MIN_NOTIONAL_USD / mid) / step - 1e-12)
    return f"{n * step:.{sz_decimals}f}"


def adverse_bps(direction: int, fill_px: float, mid: float) -> float:
    return -direction * (mid - fill_px) / fill_px * 10_000.0


def parse_tool_json(text: str) -> dict | None:
    try:
        v = json.loads(text)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def refused(text: str) -> bool:
    t = text.lower()
    return ("session_origin_denied" in t or "\"error\"" in t or "rejected" in t or " 403" in t or "unauthorized" in t
            or "insufficient" in t or "failed" in t)


# ----------------------------------------------------------------------------- venue reads (public)
def post(body: dict, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(HL_INFO_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def all_mids() -> dict[str, float]:
    return {k: float(v) for k, v in json.loads(post({"type": "allMids"})).items()}


def sz_decimals() -> dict[str, int]:
    return {u["name"]: int(u["szDecimals"]) for u in json.loads(post({"type": "meta"})).get("universe", [])}


# ----------------------------------------------------------------------------- the stdio server
def load_client():
    spec = importlib.util.spec_from_file_location("gdex_stdio_client", FIXTURES / "gdex_stdio_client.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


class Venue:
    """One live server process; each tool call saved verbatim in the hand's format (A13 R67)."""

    def __init__(self, client_mod, save_dir: Path, log):
        self.c = client_mod
        self.s = client_mod.start(timeout=240)
        self.save_dir = save_dir
        self.log = log

    def call(self, name: str, args: dict, tag: str, timeout: float = 120) -> tuple[str, Path]:
        sent = int(time.time() * 1000)
        r = self.s.call("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        recv = int(time.time() * 1000)
        text = self.c.tool_text(r)
        p = self.save_dir / f"{tag}_{sent}.json"
        p.write_text(json.dumps({"tool": name, "arguments": args, "sent_ms": sent, "received_ms": recv,
                                 "response_text": text, "raw": r}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        self.log({"type": "venue_call", "tool": name, "arguments": args, "sent_ms": sent, "received_ms": recv,
                  "saved": p.name, "sha256": sha256_file(p), "head": text[:200]})
        return text, p

    def close(self):
        self.s.close()


# ----------------------------------------------------------------------------- the run
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", required=True)
    p.add_argument("--start", default="14:00")
    p.add_argument("--end", default="15:00")
    p.add_argument("--keep", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, default=FIXTURES / "copier")
    p.add_argument("--account", default=ACCOUNT_REF)
    p.add_argument("--actor", default=ACTOR)
    p.add_argument("--poll-seconds", type=int, default=15)
    p.add_argument("--exit-poll-seconds", type=int, default=5)
    p.add_argument("--capture-poll-seconds", type=int, default=240)
    a = p.parse_args(argv)
    os.environ.setdefault("GDEX_MCP_SERVER_CMD", SERVER_CMD_DEFAULT)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = a.out_dir / f"session_{a.date}.jsonl"

    def log(row: dict):
        row = dict(row, ms=int(time.time() * 1000))
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        print(json.dumps(row, sort_keys=True)[:300], flush=True)

    keep = sorted({str(x).lower() for x in json.loads(a.keep.read_bytes()).get("addresses", [])})
    t0, t1 = ms_of(a.date, a.start), ms_of(a.date, a.end)
    log({"type": "start", "window": [iso(t0), iso(t1)], "keep": len(keep), "account": a.account, "actor": a.actor,
         "server": os.environ["GDEX_MCP_SERVER_CMD"], "rule": "A38.2: the session submits both legs under A34's standing go and R155; one attempt per leg (S54)"})

    # 1. the venue: status, then one connect
    venue = Venue(load_client(), FIXTURES, log)
    try:
        st_text, _ = venue.call("gdex_status", {}, "session_status")
        cn_text, _ = venue.call("gdex_connect", {"accountRef": a.account}, "session_connect")
        cn = parse_tool_json(cn_text)
        if not cn or cn.get("accountRef") != a.account or refused(cn_text):
            log({"type": "REFUSED", "step": "connect", "text": cn_text[:400]})
            return 4

        # 2. the window
        seen: set = set()
        signal = None
        while signal is None:
            now = int(time.time() * 1000)
            if now < t0:
                time.sleep(min(a.poll_seconds, max(1, (t0 - now) // 1000)))
                continue
            if now >= t1:
                line = f"live leg MISS by rule (R155): no KEEP leader opened inside [{a.start}, {a.end})Z on {a.date}; nothing reached the venue; flat."
                log({"type": "window_end", "line": line})
                return 3
            sigs = []
            for addr in keep:
                try:
                    fills = json.loads(post({"type": "userFillsByTime", "user": addr, "startTime": t0, "endTime": min(now, t1 - 1)}))
                except Exception as e:
                    log({"type": "poll_failure", "leader": addr, "error": type(e).__name__})
                    continue
                for fl in fills:
                    s = qualifying(fl, addr)
                    if s and t0 <= s["ms"] < t1 and (s["leader"], s["tid"], s["ms"]) not in seen:
                        seen.add((s["leader"], s["tid"], s["ms"]))
                        sigs.append(s)
                time.sleep(0.1)
            sigs.sort(key=lambda s: (s["ms"], s["leader"]))
            for s in sigs:
                log(dict(s, type="F6_signal"))
            if sigs:
                signal = sigs[0]
            else:
                time.sleep(a.poll_seconds)

        # 3. the open
        mids, szd = all_mids(), sz_decimals()
        coin, direction = signal["coin"], int(signal["direction"])
        size = unit_size(coin, mids[coin], szd.get(coin, 0))
        side = "long" if direction > 0 else "short"
        log({"type": "ORDER", "coin": coin, "side": side, "size": size, "mid": mids[coin], "signal_ms": signal["ms"], "rule": "R155/R156"})
        pv_text, pv_saved = venue.call("gdex_preview_trade", {"kind": "perp_open", "coin": coin, "side": side, "size": size}, "session_preview_open")
        pv = parse_tool_json(pv_text)
        if not pv or "previewId" not in pv or refused(pv_text):
            log({"type": "REFUSED", "step": "preview_open", "text": pv_text[:400]})
            return 4
        pv_path = FIXTURES / f"gdex_preview_{pv['previewId']}.json"
        pv_path.write_text(json.dumps(pv, indent=1) + "\n", encoding="utf-8", newline="\n")
        log({"type": "preview_written", "file": pv_path.name, "sha256": sha256_file(pv_path), "expiresAt": pv.get("expiresAt")})
        cap = subprocess.Popen([sys.executable, str(FIXTURES / "capture_from_gdex_preview.py"), "--live", "--preview-json", str(pv_path),
                                "--actor-id", a.actor, "--poll-seconds", str(a.capture_poll_seconds)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        ex_text, _ = venue.call("gdex_execute_trade", {"previewId": pv["previewId"], "userApproved": True}, "session_execute_open")
        if refused(ex_text):
            log({"type": "REFUSED", "step": "execute_open", "text": ex_text[:400], "note": "one attempt (S54); nothing else is sent"})
            cap.terminate()
            return 4
        out, _ = cap.communicate(timeout=a.capture_poll_seconds + 120)
        open_cap = FIXTURES / f"capture_LIVE_{a.date}_{pv['previewId']}.json"
        if cap.returncode != 0 or not open_cap.exists():
            log({"type": "OPEN_UNCAPTURED", "capture_rc": cap.returncode, "tail": (out or "")[-600:],
                 "note": "the execute was sent; the chain's fill was not captured in time; the position, if any, is the hand's"})
            return 5
        opened = json.loads(open_cap.read_text(encoding="utf-8"))
        fill_px = float(opened["live_fill"]["price_usd"])
        fill_ms = int(opened["live_fill"].get("time_ms") or opened["live_fill"].get("observed_ms") or int(time.time() * 1000))
        log({"type": "OPEN_CAPTURED", "file": open_cap.name, "sha256": sha256_file(open_cap), "fill_px": fill_px, "fill_ms": fill_ms})

        # 4. the exit
        gate_ms = fill_ms + GATE_MS
        reason = None
        while reason is None:
            now = int(time.time() * 1000)
            try:
                mid = all_mids()[coin]
            except Exception as e:
                log({"type": "mids_failure", "error": type(e).__name__})
                time.sleep(a.exit_poll_seconds)
                continue
            adv = adverse_bps(direction, fill_px, mid)
            if adv >= STOP_BPS - 1e-9:
                reason = "stop"
            elif now >= gate_ms:
                reason = "gate"
            else:
                time.sleep(a.exit_poll_seconds)
        log({"type": "EXIT_TRIGGER", "reason": reason, "mid": mid, "adverse_bps": adv, "gate_ms": gate_ms})
        cl_text, _ = venue.call("gdex_preview_trade", {"kind": "perp_close", "coin": coin}, "session_preview_close")
        cl = parse_tool_json(cl_text)
        if not cl or "previewId" not in cl or refused(cl_text):
            log({"type": "REFUSED", "step": "preview_close", "text": cl_text[:400], "note": "the open position is the hand's"})
            return 4
        cl_path = FIXTURES / f"gdex_preview_{cl['previewId']}.json"
        cl_path.write_text(json.dumps(cl, indent=1) + "\n", encoding="utf-8", newline="\n")
        cap2 = subprocess.Popen([sys.executable, str(FIXTURES / "capture_from_gdex_preview.py"), "--live", "--preview-json", str(cl_path),
                                 "--open-capture", str(open_cap), "--actor-id", a.actor, "--poll-seconds", str(a.capture_poll_seconds)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        ex2_text, _ = venue.call("gdex_execute_trade", {"previewId": cl["previewId"], "userApproved": True}, "session_execute_close")
        if refused(ex2_text):
            log({"type": "REFUSED", "step": "execute_close", "text": ex2_text[:400], "note": "one attempt (S54); the open position is the hand's"})
            cap2.terminate()
            return 4
        out2, _ = cap2.communicate(timeout=a.capture_poll_seconds + 120)
        close_cap = FIXTURES / f"capture_LIVE_{a.date}_{pv['previewId']}_close.json"
        if cap2.returncode != 0 or not close_cap.exists():
            log({"type": "CLOSE_UNCAPTURED", "capture_rc": cap2.returncode, "tail": (out2 or "")[-600:]})
            return 5
        log({"type": "PAIR_SETTLED", "open": open_cap.name, "close": close_cap.name, "close_sha256": sha256_file(close_cap), "reason": reason})
        return 0
    finally:
        venue.close()


if __name__ == "__main__":
    sys.exit(main())
