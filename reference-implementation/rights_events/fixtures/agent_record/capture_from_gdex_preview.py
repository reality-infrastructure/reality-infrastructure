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

THE CLOSE LEG (PREREG A1). The venue previews a close only against a real
position, and the open leg is paper, so the close intent is the paper agent's
own, quoted from the SAME source the venue's open preview quoted from
(HyperLiquid metaAndAssetCtxs, field markPx), saved verbatim and pinned; the
close paper fill is the allMids mid at the observation instant, as for the open.
The close capture names the pinned open capture it closes (file + sha256, intent
id, side, size, open fill price and fee), so the adapter can compute the realized
paper PnL over both legs without inventing an association.

    python rights_events/fixtures/agent_record/capture_from_gdex_preview.py \
        --close --open-capture PATH [--ctxs-json PATH --ctxs-observed-ms MS] \
        [--mids-json PATH --mids-observed-ms MS] [--max-bps 50]

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


def _bucket(x: Decimal) -> str:
    return "GAIN" if x > 0 else ("LOSS" if x < 0 else "FLAT")


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


HL_CTXS_QUERY = {"type": "metaAndAssetCtxs"}
HL_CTXS_SOURCE = "hyperliquid metaAndAssetCtxs"


def fetch_ctxs() -> tuple[bytes, int]:
    req = urllib.request.Request(
        HL_INFO_URL, data=json.dumps(HL_CTXS_QUERY).encode(),
        headers={"Content-Type": "application/json"})
    observed_ms = int(time.time() * 1000)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), observed_ms


def _load_mids(mids_json: Path | None, mids_observed_ms: int | None):
    if mids_json is not None:
        raw = mids_json.read_bytes().replace(b"\r\n", b"\n")
        if mids_observed_ms is None:
            raise SystemExit("--mids-json requires --mids-observed-ms.")
        return raw, mids_observed_ms, f"saved payload {mids_json.name}"
    raw, ms = fetch_mids()
    return raw, ms, f"live POST {HL_INFO_URL} {json.dumps(HL_MIDS_QUERY)}"


def _pin_verbatim(path: Path, raw: bytes) -> str:
    text = raw.decode("utf-8")
    if not text.endswith("\n"):
        text += "\n"
    return _sha(_write_lf(path, text))


def build_close(open_capture: Path, ctxs_json: Path | None,
                ctxs_observed_ms: int | None, mids_json: Path | None,
                mids_observed_ms: int | None, max_bps: str) -> tuple[Path, Path]:
    """The paper CLOSE leg of a pinned open capture (PREREG A1)."""
    open_raw = open_capture.read_bytes().replace(b"\r\n", b"\n")
    open_sha = _sha(open_raw)
    opened = json.loads(open_raw.decode("utf-8"))
    if opened.get("kind") != "agent_record_capture" or "closes" in opened:
        raise SystemExit("--open-capture must be an OPEN agent_record capture.")
    o_intent, o_fill = opened["intent"], opened["paper_fill"]
    coin, size, side = o_intent["market"], o_intent["size"], o_intent["side"]
    actor = opened["actor"]

    # --- close intent: the paper agent's own, quoted from markPx (verbatim) ---
    if ctxs_json is not None:
        raw_ctxs = ctxs_json.read_bytes().replace(b"\r\n", b"\n")
        if ctxs_observed_ms is None:
            raise SystemExit("--ctxs-json requires --ctxs-observed-ms.")
        quote_ms = ctxs_observed_ms
        ctxs_origin = f"saved payload {ctxs_json.name}"
    else:
        raw_ctxs, quote_ms = fetch_ctxs()
        ctxs_origin = f"live POST {HL_INFO_URL} {json.dumps(HL_CTXS_QUERY)}"
    meta, ctxs = json.loads(raw_ctxs.decode("utf-8"))
    idx = next((i for i, a in enumerate(meta["universe"]) if a["name"] == coin),
               None)
    if idx is None:
        raise SystemExit(f"{coin} not in metaAndAssetCtxs; no capture is written.")
    mark_px = ctxs[idx]["markPx"]
    ctxs_path = HERE / f"hl_metaAndAssetCtxs_{quote_ms}.json"
    ctxs_sha = _pin_verbatim(ctxs_path, raw_ctxs)
    intent_date = _iso(quote_ms)
    open_id = o_intent["intent_id"]
    close_id = f"paper:{open_id}:close"

    # --- close paper fill: the mid at the observation instant (verbatim) -----
    raw_mids, fill_ms, mids_origin = _load_mids(mids_json, mids_observed_ms)
    mids = json.loads(raw_mids.decode("utf-8"))
    if coin not in mids:
        raise SystemExit(f"{coin} not in allMids; no capture is written.")
    mids_path = HERE / f"hl_allMids_{fill_ms}.json"
    mids_sha = _pin_verbatim(mids_path, raw_mids)
    fill_date = _iso(fill_ms)

    quote, fill_px = _d(mark_px), _d(mids[coin])
    dev = abs(fill_px - quote) / quote * Decimal(10000)
    direction = 1 if side == "long" else -1
    fees = _d(o_fill["fee_usd"]) + Decimal(0)
    realized = (fill_px - _d(o_fill["price_usd"])) * _d(size) * direction - fees

    capture = {
        "kind": "agent_record_capture",
        "mode": "PAPER",
        "synthetic": False,
        "note": ("PAPER capture, CLOSE leg. INTENT SIDE: the paper agent's own close "
                 "intent for the whole open size, quoted from " + HL_CTXS_SOURCE
                 + " markPx (POST " + HL_INFO_URL + " {type: metaAndAssetCtxs}), the "
                 "same source the venue's open preview quoted from; the venue "
                 "previews a close only against a real position and the open leg "
                 "is paper. PAPER SIDE: this tool's own simulated fill at the "
                 "HyperLiquid allMids price at the observation instant; fee 0 and "
                 "labeled so. CLOSES: the pinned open capture named below. See the "
                 "MANIFEST beside this file."),
        "actor": actor,
        "closes": {
            "capture": open_capture.name,
            "sha256": open_sha,
            "intent_id": open_id,
            "fill_id": o_fill["fill_id"],
            "side": side,
            "size": size,
            "fill_price_usd": o_fill["price_usd"],
            "fill_fee_usd": o_fill["fee_usd"],
        },
        "intent": {
            "source": "paper-agent",
            "intent_id": close_id,
            "kind": "perp_close",
            "market": coin,
            "side": "close_long" if side == "long" else "close_short",
            "order_type": "market",
            "size": size,
            "quote_price_usd": str(mark_px),
            "quote_source": HL_CTXS_SOURCE,
            "quote_as_of_ms": quote_ms,
            "created_ms": quote_ms,
            "source_url": HL_INFO_URL,
            "observed_date": intent_date,
        },
        "paper_fill": {
            "fill_id": f"{close_id}:fill",
            "intent_id": close_id,
            "price_usd": str(mids[coin]),
            "size": size,
            "fee_usd": "0",
            "fee_model": "none (paper; a LIVE fill carries the chain's fee)",
            "mark_source": "hyperliquid allMids",
            "observed_ms": fill_ms,
            "source_url": HL_INFO_URL,
            "observed_date": fill_date,
        },
        "tolerance": {"max_quote_to_fill_bps": str(_d(max_bps))},
    }
    cap_path = HERE / f"capture_PAPER_{intent_date}_{open_id}_close.json"
    cap_bytes = _write_lf(cap_path, json.dumps(capture, indent=2) + "\n")

    manifest = {
        "fixture": cap_path.name,
        "status": "PAPER",
        "leg": "close",
        "bytes": len(cap_bytes),
        "sha256": _sha(cap_bytes),
        "generator": Path(__file__).name,
        "closes": {"capture": open_capture.name, "sha256": open_sha},
        "source": {
            "intent": {
                "what": "The paper agent's own close intent, quoted from the mark "
                        "price the venue's own open preview quoted from.",
                "why_not_gdex": "gdex_preview_trade {kind: perp_close} answers "
                                "VALIDATION_ERROR 'No open <coin> position found' "
                                "for a paper position (probed 2026-10-22).",
                "api": HL_INFO_URL + " " + json.dumps(HL_CTXS_QUERY),
                "payload_origin": ctxs_origin,
                "payload_verbatim_file": ctxs_path.name,
                "payload_sha256": ctxs_sha,
                "quote_field": "markPx",
                "observed_ms": quote_ms,
                "observed_date": intent_date,
            },
            "paper_fill": {
                "what": "Simulated fill of the open size at the HyperLiquid mid at "
                        "the observation instant. Self-asserted; not a chain event.",
                "api": HL_INFO_URL + " " + json.dumps(HL_MIDS_QUERY),
                "payload_origin": mids_origin,
                "payload_verbatim_file": mids_path.name,
                "payload_sha256": mids_sha,
                "observed_ms": fill_ms,
                "observed_date": fill_date,
                "fee_model": capture["paper_fill"]["fee_model"],
            },
        },
        "dispute_semantics": {
            "quote_price_usd": str(quote),
            "fill_price_usd": str(fill_px),
            "deviation_bps": str(dev),
            "max_quote_to_fill_bps": str(_d(max_bps)),
            "dispute_expected": dev > _d(max_bps),
        },
        "realized_paper_pnl": {
            "formula": "(close_fill - open_fill) * size * dir - fees, Decimal",
            "open_price_usd": o_fill["price_usd"],
            "close_price_usd": str(fill_px),
            "size": size,
            "dir": direction,
            "fees_usd": str(fees),
            "realized_pnl_usd": str(realized),
            "bucket": _bucket(realized),
        },
    }
    man_path = HERE / f"MANIFEST_PAPER_{intent_date}_{open_id}_close.json"
    _write_lf(man_path, json.dumps(manifest, indent=2) + "\n")
    return cap_path, man_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--close", action="store_true",
                    help="take the paper CLOSE leg of --open-capture (PREREG A1)")
    ap.add_argument("--open-capture", default=None, type=Path)
    ap.add_argument("--ctxs-json", default=None, type=Path)
    ap.add_argument("--ctxs-observed-ms", default=None, type=int)
    ap.add_argument("--preview-json", default=None, type=Path)
    ap.add_argument("--actor-id", default=None,
                    help="GDEX managed EVM wallet the preview binds to")
    ap.add_argument("--control-wallet", default=None)
    ap.add_argument("--mids-json", default=None, type=Path)
    ap.add_argument("--mids-observed-ms", default=None, type=int)
    ap.add_argument("--max-bps", default="50")
    args = ap.parse_args(argv)
    if args.close:
        if args.open_capture is None:
            raise SystemExit("--close requires --open-capture PATH")
        cap, man = build_close(args.open_capture, args.ctxs_json,
                               args.ctxs_observed_ms, args.mids_json,
                               args.mids_observed_ms, args.max_bps)
    else:
        if args.preview_json is None or args.actor_id is None:
            raise SystemExit("an open leg requires --preview-json and --actor-id")
        cap, man = build(args.preview_json, args.actor_id, args.control_wallet,
                         args.mids_json, args.mids_observed_ms, args.max_bps)
    print(f"wrote {cap.name}\nwrote {man.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
