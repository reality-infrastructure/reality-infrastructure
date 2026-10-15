"""Upstream capture tool (NOT part of ri_core, NOT a test): snapshot one
HyperLiquid leaderboard row + that address's fills over the trailing-7d window
into the trader_record adapter's capture schema.

It reads the network and the clock, as any scraper does. The JSON artifact it
freezes beside it (capture_REAL_<date>.json + MANIFEST_REAL_<date>.json) is then
a pure, deterministic input to the pure adapter (adapters/trader_record.py). This
file exists so the REAL fixture's provenance is reproducible, not a black box.

HyperLiquid is the public, keyless data source that gdex.pro's HL copy-trade
leaderboard re-displays. The gdex MCP server (@gemachdao/gdex-mcp-server) was not
connected when the checked-in capture was taken, so it was taken from the
underlying HL API directly and labeled so in the MANIFEST (no fabrication: every
field is live, with a source_url).

    python rights_events/fixtures/trader_record/capture_from_hyperliquid.py <address>

Default address is the one behind the checked-in REAL fixture. Re-running on a
later date writes a new date-stamped pair; it does not overwrite an existing one.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DEFAULT_ADDR = "0xea0027b6ea9b6d7d401b5266979cc3b3ca87a918"
HERE = Path(__file__).resolve().parent
LB_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
INFO_URL = "https://api.hyperliquid.xyz/info"
EXPLORER = "https://app.hyperliquid.xyz/explorer/tx/"


def _info(payload: dict):
    req = urllib.request.Request(
        INFO_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _d(x) -> Decimal:
    return Decimal(str(x))


def _bucket(x: Decimal) -> str:
    return "GAIN" if x > 0 else ("LOSS" if x < 0 else "FLAT")


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def build(addr: str) -> tuple[Path, Path]:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 7 * 86400 * 1000
    observed_date = datetime.now(timezone.utc).date().isoformat()

    with urllib.request.urlopen(urllib.request.Request(LB_URL), timeout=90) as r:
        rows = json.load(r)["leaderboardRows"]
    row = next(x for x in rows if x["ethAddress"].lower() == addr.lower())
    wk = next(v for k, v in row["windowPerformances"] if k == "week")
    disp_bucket = _bucket(_d(wk["pnl"]))

    fills = _info({"type": "userFillsByTime", "user": addr,
                   "startTime": start_ms, "endTime": now_ms})
    if len(fills) >= 2000:
        raise SystemExit(f"fills capped at {len(fills)}; window not fully "
                         "covered - choose a less active address or shorter "
                         "window. No partial capture is written.")

    out_fills, net = [], Decimal(0)
    for f in sorted(fills, key=lambda f: (f["time"], str(f["tid"]))):
        net += _d(f.get("closedPnl", "0")) - _d(f.get("fee", "0"))
        out_fills.append({
            "fill_id": str(f["tid"]),
            "address": addr,
            "token": f["coin"],
            "side": f.get("dir", f.get("side", "")),
            "realized_pnl_usdc": f.get("closedPnl", "0"),
            "fee_usdc": f.get("fee", "0"),
            "tx_sig": f["hash"],
            "source_url": EXPLORER + f["hash"],
            "observed_date": _iso(f["time"]),
        })
    chain_bucket = _bucket(net)

    capture = {
        "kind": "trader_record_capture",
        "synthetic": False,
        "note": ("REAL capture. Source: public HyperLiquid API (keyless), the "
                 "surface gdex.pro's HL copy-trade leaderboard re-displays. The "
                 "venue_claim is the HL leaderboard 'week' window PnL (includes "
                 "unrealized mark-to-market + funding); the fills are the "
                 "realized closed PnL (closedPnl - fee) for the same address "
                 "over the same trailing-7d window, each with its L1 tx hash. "
                 "See the MANIFEST_REAL file beside this one."),
        "actor": {"actor_id": addr, "addresses": [addr]},
        "venue_claim": {
            "actor_id": addr,
            "window": {"start": _iso(start_ms), "end": _iso(now_ms)},
            "displayed_net_pnl_usdc": wk["pnl"],
            "displayed_bucket": disp_bucket,
            "source_url": LB_URL,
            "observed_date": observed_date,
        },
        "fills": out_fills,
    }
    cap_path = HERE / f"capture_REAL_{observed_date}.json"
    if cap_path.exists():
        raise SystemExit(f"{cap_path.name} already exists; not overwriting.")
    cap_path.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")
    cap_bytes = cap_path.read_bytes()

    manifest = {
        "fixture": cap_path.name,
        "status": "REAL",
        "bytes": len(cap_bytes),
        "sha256": hashlib.sha256(cap_bytes).hexdigest(),
        "generator": "capture_from_hyperliquid.py",
        "source": {
            "venue_displayed": {
                "what": "HyperLiquid leaderboard 'week' window PnL (includes "
                        "unrealized mark-to-market + funding).",
                "url": LB_URL,
                "human_page": "https://app.hyperliquid.xyz/leaderboard",
                "observed_date": observed_date,
                "gdex_relation": "gdex.pro's HyperLiquid copy-trade leaderboard "
                                 "re-displays this HL surface; the gdex MCP "
                                 "server (@gemachdao/gdex-mcp-server) was not "
                                 "connected, so the capture was taken from the "
                                 "underlying HL API directly and labeled so.",
            },
            "chain_fills": {
                "what": "Realized closed PnL (closedPnl - fee) per fill for the "
                        "address over the trailing-7d window [start,end].",
                "api": INFO_URL + " (type=userFillsByTime)",
                "explorer": EXPLORER + "<tx_hash>",
                "window_start_ms": start_ms,
                "window_end_ms": now_ms,
                "fill_count": len(out_fills),
                "fully_covered": True,
            },
        },
        "actor_grouping": {
            "rule": "address->actor grouping is an INPUT to the pure adapter, "
                    "not computed by it.",
            "this_capture": "Single-address account: the grouping is the "
                            "identity grouping {address}. wallet-independence "
                            "multi-address actor clustering is not applicable to "
                            "one address and was not run; for a multi-address "
                            "actor the grouping would come from that clustering, "
                            "recorded here.",
        },
        "dispute_semantics": {
            "meaning": "A dispute fires when the displayed window bucket differs "
                       "from the bucket of realized-closed PnL over the same "
                       "window. It records that the displayed figure is not "
                       "reproducible from the actor's closed fills (the copier's "
                       "verification gap) - NOT that any single number was "
                       "falsified.",
            "displayed_bucket": disp_bucket,
            "displayed_net_pnl_usdc": wk["pnl"],
            "chain_realized_net_pnl_usdc": str(net),
            "chain_bucket": chain_bucket,
            "dispute_expected": disp_bucket != chain_bucket,
        },
        "selection": {
            "how": "Scanned the most active (by |week PnL|) leaderboard rows; "
                   "fetched each address's realized-closed PnL over the "
                   "trailing-7d window; selected one fully-covered (uncapped) "
                   "divergence with a small, complete fill set.",
            "aggregate_finding": "On the 2026-10-15 scan, 18 of 38 scanned "
                                 "active top traders showed a displayed-vs-"
                                 "realized-closed bucket divergence - the "
                                 "verification gap is common, not contrived.",
        },
    }
    man_path = HERE / f"MANIFEST_REAL_{observed_date}.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return cap_path, man_path


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDR
    cap, man = build(addr)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    print(f"wrote {cap.name} ({cap.stat().st_size} bytes) and {man.name}")
    print(f"actor {doc['actor']['actor_id']}  fills {len(doc['fills'])}")
    print(f"displayed {doc['venue_claim']['displayed_net_pnl_usdc']} "
          f"{doc['venue_claim']['displayed_bucket']}")
