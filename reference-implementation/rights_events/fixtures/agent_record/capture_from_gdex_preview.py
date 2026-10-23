"""Upstream capture tool (NOT part of ri_core, NOT a test): freeze one GDEX
preview (the agent's INTENT, exact executable terms from gdex_preview_trade) beside
its PAPER fill (the HyperLiquid mid price at the moment the paper leg was taken),
into the agent_record capture schema.

It reads the network and the clock, as any capture tool does. The JSON artifacts
it freezes (capture_PAPER_<date>_<previewId>.json + MANIFEST_PAPER_<date>_
<previewId>.json, plus the VERBATIM upstream payloads they were parsed from) are
then pure, deterministic inputs to the pure adapter (adapters/agent_record.py).

THE INTENT SIDE IS GDEX'S OWN PREVIEW. `gdex_preview_trade` (published gdex MCP
server, @gemachdao/gdex-mcp-server) turns an explicit trade intent into exact
terms bound to GDEX managed custody (trade-api.gemach.io/v1): coin, side, size
rounded to szDecimals, notional, margin, leverage, margin mode, the quote price
and its source and time, a 60-second expiry, and a binding hash. The preview is
NOT a trade: nothing is submitted. Its response is saved verbatim beside the
capture and its sha256 pinned before anything is parsed from it.

THE PAPER SIDE IS THE PUBLIC MID. A paper fill is this tool's OWN assertion: the
intent's size taken at the HyperLiquid `allMids` price for the coin at the
observation instant (POST https://api.hyperliquid.xyz/info {type: allMids}),
fee 0 and labeled so (the preview reports no fee; a LIVE fill carries the
chain's fee). The allMids payload is saved verbatim and pinned. The adapter
types a paper fill `self_asserted`, never `cryptographically_signed`: it is a
simulation, and the record says so on every event.

    python rights_events/fixtures/agent_record/capture_from_gdex_preview.py \
        --preview-json PATH --actor-id 0x<managed evm wallet> \
        [--control-wallet 0x...] [--mids-json PATH --mids-observed-ms MS] \
        [--max-bps 50]

Re-running writes a new set keyed by date + previewId; it never overwrites.
No partial capture is ever written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent

GDEX_BASE = "https://trade-api.gemach.io/v1"
GDEX_MCP_TOOL = "@gemachdao/gdex-mcp-server: gdex_preview_trade"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_MIDS_QUERY = {"type": "allMids"}


def _d(x) -> Decimal:
    return Decimal(str(x))


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_lf(path: Path, text: str) -> bytes:
    if path.exists():
        raise SystemExit(f"{path.name} already exists; not overwriting.")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path.read_bytes()


def fetch_mids() -> tuple[bytes, int]:
    req = urllib.request.Request(
        HL_INFO_URL, data=json.dumps(HL_MIDS_QUERY).encode(),
        headers={"Content-Type": "application/json"})
    observed_ms = int(time.time() * 1000)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), observed_ms


def build(preview_json: Path, actor_id: str, control_wallet: str | None,
          mids_json: Path | None, mids_observed_ms: int | None,
          max_bps: str) -> tuple[Path, Path]:
    actor_id = actor_id.lower()

    # --- intent side: the gdex preview, saved verbatim, pinned before parsing ---
    raw_prev = preview_json.read_bytes().replace(b"\r\n", b"\n")
    prev_sha = _sha(raw_prev)
    prev = json.loads(raw_prev.decode("utf-8"))
    preview_id = prev["previewId"]
    terms = prev["terms"]
    if prev.get("kind") != "perp_open":
        raise SystemExit("only perp_open previews are captured in this contract; "
                         "no capture is written.")
    if terms.get("dex"):
        raise SystemExit("builder-DEX previews are out of scope; no capture is "
                         "written.")
    created_ms = int(prev["createdAt"])
    intent_date = _iso(created_ms)
    dest_prev = HERE / f"gdex_preview_{preview_id}.json"
    if dest_prev.exists():
        if dest_prev.read_bytes().replace(b"\r\n", b"\n") != raw_prev:
            raise SystemExit(f"{dest_prev.name} exists with different bytes.")
    elif dest_prev.resolve() != preview_json.resolve():
        _write_lf(dest_prev, raw_prev.decode("utf-8"))

    # --- paper side: the public mid at the observation instant, verbatim ---------
    if mids_json is not None:
        raw_mids = mids_json.read_bytes().replace(b"\r\n", b"\n")
        if mids_observed_ms is None:
            raise SystemExit("--mids-json requires --mids-observed-ms.")
        observed_ms = mids_observed_ms
        mids_origin = f"saved payload {mids_json.name}"
    else:
        raw_mids, observed_ms = fetch_mids()
        mids_origin = f"live POST {HL_INFO_URL} {json.dumps(HL_MIDS_QUERY)}"
    mids = json.loads(raw_mids.decode("utf-8"))
    coin = terms["coin"]
    if coin not in mids:
        raise SystemExit(f"{coin} not in allMids; no capture is written.")
    mids_path = HERE / f"hl_allMids_{observed_ms}.json"
    mids_bytes = _write_lf(mids_path, raw_mids.decode("utf-8")
                           if raw_mids.endswith(b"\n")
                           else raw_mids.decode("utf-8") + "\n")
    mids_sha = _sha(mids_bytes)
    fill_date = _iso(observed_ms)

    quote = _d(terms["price"])
    fill_px = _d(mids[coin])
    deviation_bps = (abs(fill_px - quote) / quote * Decimal(10000))
    dispute_expected = deviation_bps > _d(max_bps)

    capture = {
        "kind": "agent_record_capture",
        "mode": "PAPER",
        "synthetic": False,
        "note": ("PAPER capture. INTENT SIDE: GDEX's own preview (" + GDEX_MCP_TOOL
                 + ", bound to GDEX managed custody at " + GDEX_BASE + "); exact "
                 "executable terms, nothing submitted. PAPER SIDE: this tool's own "
                 "simulated fill of the intent's size at the HyperLiquid allMids "
                 "price for the coin at the observation instant (POST " + HL_INFO_URL
                 + " {type: allMids}); fee 0 and labeled so. A paper fill is "
                 "self-asserted simulation, never a chain fill. See the MANIFEST "
                 "beside this file."),
        "actor": {
            "actor_id": actor_id,
            "custody": "GDEX managed custody (managed EVM wallet = actor_id)",
            **({"control_wallet": control_wallet.lower()} if control_wallet else {}),
        },
        "intent": {
            "intent_id": preview_id,
            "kind": prev["kind"],
            "market": coin,
            "side": terms["side"],
            "order_type": terms["orderType"],
            "size": terms["size"],
            "sz_decimals": int(terms["szDecimals"]),
            "notional_usd": terms["notionalUsd"],
            "margin_usd": terms["marginUsd"],
            "leverage": int(terms["leverage"]),
            "margin_mode": terms["marginMode"],
            "quote_price_usd": terms["price"],
            "mark_price_usd": terms["markPx"],
            "quote_source": terms["priceSource"],
            "quote_as_of_ms": int(terms["priceAsOf"]),
            "created_ms": created_ms,
            "expires_ms": int(prev["expiresAt"]),
            "binding": prev["binding"],
            "tool": GDEX_MCP_TOOL,
            "source_url": GDEX_BASE,
            "observed_date": intent_date,
        },
        "paper_fill": {
            "fill_id": f"paper:{preview_id}:open",
            "intent_id": preview_id,
            "price_usd": str(mids[coin]),
            "size": terms["size"],
            "fee_usd": "0",
            "fee_model": "none (paper; the preview reports no fee; a LIVE fill "
                         "carries the chain's fee)",
            "mark_source": "hyperliquid allMids",
            "observed_ms": observed_ms,
            "source_url": HL_INFO_URL,
            "observed_date": fill_date,
        },
        "tolerance": {"max_quote_to_fill_bps": str(_d(max_bps))},
    }
    cap_path = HERE / f"capture_PAPER_{intent_date}_{preview_id}.json"
    cap_bytes = _write_lf(cap_path, json.dumps(capture, indent=2) + "\n")

    manifest = {
        "fixture": cap_path.name,
        "status": "PAPER",
        "bytes": len(cap_bytes),
        "sha256": _sha(cap_bytes),
        "generator": Path(__file__).name,
        "source": {
            "intent": {
                "what": "GDEX preview: exact executable terms for an explicit trade "
                        "intent, bound to GDEX managed custody; nothing submitted.",
                "gdex_mcp_tool": GDEX_MCP_TOOL,
                "custody_backend": GDEX_BASE,
                "payload_verbatim_file": dest_prev.name,
                "payload_sha256": prev_sha,
                "preview_created_ms": created_ms,
                "preview_expires_ms": int(prev["expiresAt"]),
                "quote_source": terms["priceSource"],
                "quote_as_of_ms": int(terms["priceAsOf"]),
                "observed_date": intent_date,
            },
            "paper_fill": {
                "what": "Simulated fill of the intent's size at the HyperLiquid mid "
                        "for the coin at the observation instant. Self-asserted by "
                        "this tool; not a chain event.",
                "api": HL_INFO_URL + " " + json.dumps(HL_MIDS_QUERY),
                "payload_origin": mids_origin,
                "payload_verbatim_file": mids_path.name,
                "payload_sha256": mids_sha,
                "observed_ms": observed_ms,
                "observed_date": fill_date,
                "fee_model": capture["paper_fill"]["fee_model"],
            },
        },
        "actor": {
            "rule": "actor_id is the GDEX managed EVM wallet the preview binds to; "
                    "the control wallet (if given) only signed the session in.",
            "actor_id": actor_id,
            **({"control_wallet": control_wallet.lower()} if control_wallet else {}),
        },
        "dispute_semantics": {
            "meaning": "A dispute fires when the paper fill price deviates from the "
                       "preview's quote price by more than max_quote_to_fill_bps. "
                       "It records that the intent's terms were not reproducible at "
                       "the fill instant - NOT that any number was falsified.",
            "quote_price_usd": str(quote),
            "fill_price_usd": str(fill_px),
            "deviation_bps": str(deviation_bps),
            "max_quote_to_fill_bps": str(_d(max_bps)),
            "dispute_expected": dispute_expected,
        },
    }
    man_path = HERE / f"MANIFEST_PAPER_{intent_date}_{preview_id}.json"
    _write_lf(man_path, json.dumps(manifest, indent=2) + "\n")
    return cap_path, man_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--preview-json", required=True, type=Path)
    ap.add_argument("--actor-id", required=True,
                    help="GDEX managed EVM wallet the preview binds to")
    ap.add_argument("--control-wallet", default=None)
    ap.add_argument("--mids-json", default=None, type=Path)
    ap.add_argument("--mids-observed-ms", default=None, type=int)
    ap.add_argument("--max-bps", default="50")
    args = ap.parse_args(argv)
    cap, man = build(args.preview_json, args.actor_id, args.control_wallet,
                     args.mids_json, args.mids_observed_ms, args.max_bps)
    print(f"wrote {cap.name}\nwrote {man.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
