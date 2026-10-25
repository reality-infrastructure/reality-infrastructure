"""Stop watcher (NOT part of ri_core, NOT a test; PREREG A5, R27-R31): poll the public
HyperLiquid mid from the LIVE open fill until the five-hour gate, mark the live stop
control and every paper stop fork against that ONE tape, and pin the allMids payload at
each trigger. It READS only (R31): no preview, no order, no cancel, no transfer. The
live close, when the control fires, is submitted by the operator's hand under A4 R26.

    python rights_events/fixtures/agent_record/watch_stop_forks.py \
        --open-capture rights_events/fixtures/agent_record/capture_LIVE_<date>_<pv>.json \
        [--live-stop-bps 30] [--fork-bps 10,20,30,50,100] [--gate-hours 5] [--poll-seconds 5]

Outputs, beside the open capture:
    watch_LIVE_<date>_<pv>.jsonl   the tape: one {"ms", "mid"} row per poll (mid null on outage)
    forks_LIVE_<date>_<pv>.json    the fork capture (kind agent_record_fork_capture), rewritten
                                   after every trigger and at the gate
    hl_allMids_<ms>.json           the verbatim payload at each trigger poll and the gate poll
Prints `TRIGGER live <ms> <mid> <adverse_bps>` once when the control fires (and keeps
running to the gate so the wider forks and gate_only are marked), `TRIGGER gate <ms> <mid>`
at the gate, then exits 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
GATE_ONLY = "gate_only"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def adverse_bps(open_fill: Decimal, mid: Decimal, direction: int) -> Decimal:
    """R27 definition. direction +1 long, -1 short. Decimal only."""
    return (open_fill - mid) / open_fill * Decimal(10000) * direction


def new_state(open_doc: dict, live_stop_bps: int, fork_bps: list[int],
              gate_hours: int) -> dict:
    """Pure: the fork state from the pinned open capture (S27: every input is read
    from the capture; nothing is invented)."""
    intent, fill = open_doc["intent"], open_doc["live_fill"]
    if open_doc.get("mode") != "LIVE" or intent.get("kind") != "perp_open":
        raise SystemExit("S27: --open-capture must be the LIVE open leg; watcher not started")
    direction = 1 if intent["side"] in ("long", "buy") else -1
    open_fill = Decimal(fill["price_usd"])
    fill_ms = int(fill["fill_time_ms"])
    forks = {str(b): {"stop_bps": b, "triggered": False, "is_live_control": b == live_stop_bps}
             for b in sorted(set(fork_bps) | {live_stop_bps})}
    forks[GATE_ONLY] = {"stop_bps": None, "triggered": False, "is_live_control": False}
    return {
        "kind": "agent_record_fork_capture",
        "mode": "PAPER",
        "synthetic": False,
        "note": ("Paper stop forks (PREREG A5 R28): every distance marked against ONE tape of "
                 "polled HyperLiquid mids from the chain's open fill to the five-hour gate. "
                 "Simulations, self-asserted; nothing was submitted for any fork. The live "
                 "control's close, if it fired, is in the LIVE close capture beside this."),
        "actor": dict(open_doc["actor"]),
        "source_url": HL_INFO_URL,
        "open": {
            "capture": None,                     # filled by main (file name + sha)
            "capture_sha256": None,
            "intent_id": intent["intent_id"],
            "fill_event_id": f"agent_record:fill:{fill['fill_id']}",
            "fill_price_usd": fill["price_usd"],
            "fill_time_ms": fill_ms,
            "size": intent["size"],
            "side": intent["side"],
            "dir": direction,
            "market": intent["market"],
        },
        "rules": {
            "adverse_bps": "(open_fill - mid) / open_fill * 10000 * dir, Decimal",
            "live_stop_bps": live_stop_bps,
            "gate_ms": fill_ms + gate_hours * 3600 * 1000,
            "poll_seconds": None,
            "exit_mark_source": "hyperliquid allMids",
            "fee_model": "none (paper fork; compare to the live control's gross)",
        },
        "tape": {"file": None, "sha256": None, "rows": 0, "null_rows": 0},
        "forks": forks,
        "live_trigger": None,
        "gate": None,
        "complete": False,
    }


def mark(state: dict, ms: int, mid: Decimal | None) -> list[str]:
    """Pure: apply one poll to the fork state. Returns the fork keys that fired on
    this poll (first crossing only, R28). A null mid marks nothing."""
    fired: list[str] = []
    if mid is None:
        return fired
    o = state["open"]
    bps = adverse_bps(Decimal(o["fill_price_usd"]), mid, int(o["dir"]))
    at_gate = ms >= state["rules"]["gate_ms"]
    for key, f in state["forks"].items():
        if f["triggered"]:
            continue
        hit = (f["stop_bps"] is not None and bps >= Decimal(f["stop_bps"])) or at_gate
        if hit:
            f.update({"triggered": f["stop_bps"] is not None and bps >= Decimal(f["stop_bps"]),
                      "exit_ms": ms, "exit_mid_usd": str(mid), "adverse_bps_at_exit": str(bps),
                      "exit_reason": "stop" if (f["stop_bps"] is not None
                                                and bps >= Decimal(f["stop_bps"])) else "gate",
                      "gross_paper_pnl_usd": str((mid - Decimal(o["fill_price_usd"]))
                                                 * Decimal(o["size"]) * int(o["dir"]))})
            fired.append(key)
            if f["is_live_control"] and state["live_trigger"] is None:
                state["live_trigger"] = {"ms": ms, "mid": str(mid), "adverse_bps": str(bps),
                                         "reason": f["exit_reason"]}
    if at_gate and state["gate"] is None:
        state["gate"] = {"ms": ms, "mid": str(mid), "adverse_bps": str(bps)}
    return fired


def fetch_mids() -> tuple[bytes | None, int]:
    body = json.dumps({"type": "allMids"}).encode("utf-8")
    req = urllib.request.Request(HL_INFO_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    observed_ms = int(time.time() * 1000)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read(), observed_ms
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, observed_ms


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--open-capture", type=Path, required=True)
    p.add_argument("--live-stop-bps", type=int, default=30)
    p.add_argument("--fork-bps", default="10,20,30,50,100")
    p.add_argument("--gate-hours", type=int, default=5)
    p.add_argument("--poll-seconds", type=int, default=5)
    args = p.parse_args(argv)

    here = args.open_capture.resolve().parent
    open_raw = args.open_capture.read_bytes().replace(b"\r\n", b"\n")
    open_doc = json.loads(open_raw.decode("utf-8"))
    fork_bps = [int(x) for x in args.fork_bps.split(",") if x.strip()]
    state = new_state(open_doc, args.live_stop_bps, fork_bps, args.gate_hours)
    state["open"]["capture"] = args.open_capture.name
    state["open"]["capture_sha256"] = _sha(open_raw)
    state["rules"]["poll_seconds"] = args.poll_seconds
    pv = state["open"]["intent_id"]
    date = _iso(state["open"]["fill_time_ms"])
    tape_path = here / f"watch_LIVE_{date}_{pv}.jsonl"
    forks_path = here / f"forks_LIVE_{date}_{pv}.json"
    if tape_path.exists() or forks_path.exists():
        raise SystemExit(f"{tape_path.name} or {forks_path.name} already exists; not started")
    state["tape"]["file"] = tape_path.name
    gate_ms = state["rules"]["gate_ms"]
    coin = state["open"]["market"]

    def save_state(final: bool) -> None:
        raw = tape_path.read_bytes() if tape_path.exists() else b""
        state["tape"]["sha256"] = _sha(raw)
        state["complete"] = final
        forks_path.write_bytes((json.dumps(state, indent=2) + "\n").encode("utf-8"))

    print(f"WATCH {pv}: open fill {state['open']['fill_price_usd']} at ms "
          f"{state['open']['fill_time_ms']}, dir {state['open']['dir']}, live stop "
          f"{args.live_stop_bps} bps, forks {sorted(state['forks'])}, gate ms {gate_ms}",
          flush=True)
    rows = nulls = 0
    with tape_path.open("ab") as tape:
        while True:
            raw, ms = fetch_mids()
            mid = None
            if raw is not None:
                try:
                    mid = Decimal(json.loads(raw.decode("utf-8"))[coin])
                except (KeyError, ValueError, json.JSONDecodeError):
                    mid = None
            tape.write((json.dumps({"ms": ms, "mid": None if mid is None else str(mid)})
                        + "\n").encode("utf-8"))
            tape.flush()
            rows += 1
            nulls += mid is None
            state["tape"]["rows"], state["tape"]["null_rows"] = rows, nulls
            fired = mark(state, ms, mid)
            if fired:
                payload_path = here / f"hl_allMids_{ms}.json"
                if not payload_path.exists():
                    payload_path.write_bytes(raw)
                for key in fired:
                    state["forks"][key]["payload_file"] = payload_path.name
                    state["forks"][key]["payload_sha256"] = _sha(raw)
                    f = state["forks"][key]
                    tag = "live" if f["is_live_control"] else "fork"
                    print(f"TRIGGER {tag if f['exit_reason'] == 'stop' else 'gate'} {key} "
                          f"{ms} {mid} {f['adverse_bps_at_exit']}", flush=True)
                save_state(final=False)
            if state["gate"] is not None and all(f.get("exit_ms") for f in state["forks"].values()):
                save_state(final=True)
                print(f"GATE reached at ms {ms}; tape rows {rows} (null {nulls}); "
                      f"forks file {forks_path.name}", flush=True)
                return 0
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
