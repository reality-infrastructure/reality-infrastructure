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

THE LIVE LEG (PREREG A2). The intent is again GDEX's own preview, saved
verbatim. The OUTCOME is the real fill the HyperLiquid L1 recorded under the
actor's wallet, read back from the info API (POST {type: userFillsByTime,
user, startTime}) — never from this tool placing anything: the operator
submits the preview through their own GDEX account, by hand, inside its
60-second expiry; this tool only polls for the fill, then at once takes the
allMids mid as the PAPER shadow fill at the same instant. Both payloads are
saved verbatim and pinned. The fill rows are associated to the intent only by
coin, chain `dir`, time window and one order id, with sizes summing exactly to
the intent's (select_fill_rows, pure); anything else writes nothing. The
adapter types the live fill `cryptographically_signed` because it carries the
L1 transaction hash(es); the shadow stays `self_asserted` PAPER; the gap
between them is the day's number.

    python rights_events/fixtures/agent_record/capture_from_gdex_preview.py \
        --live --preview-json PATH --actor-id 0x<managed evm wallet> \
        [--open-capture PATH            # for a perp_close preview: the LIVE open leg] \
        [--fills-json PATH --fills-observed-ms MS] [--mids-json PATH --mids-observed-ms MS] \
        [--max-bps 50] [--max-shadow-lag-ms 5000] [--max-fill-after-expiry-ms 60000] \
        [--max-pnl-recon-usd 0.000001] [--poll-seconds 120]

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


HL_FILLS_TYPE = "userFillsByTime"
HL_EXPLORER_TX = "https://app.hyperliquid.xyz/explorer/tx/"
_BUY_SIDES = ("long", "buy", "close_short")
_SELL_SIDES = ("short", "sell", "close_long")
_DIR_FOR = {("perp_open", 1): "Open Long", ("perp_open", -1): "Open Short",
            ("perp_close", -1): "Close Long", ("perp_close", 1): "Close Short"}


def _fmt(x: Decimal) -> str:
    return format(x, "f")


def _side_sign(side: str) -> int:
    if side in _BUY_SIDES:
        return 1
    if side in _SELL_SIDES:
        return -1
    raise SystemExit(f"preview side {side!r} is outside the closed buy/sell "
                     "vocabulary; no capture is written.")


def fetch_fills(actor_id: str, start_ms: int) -> tuple[bytes, int, dict]:
    query = {"type": HL_FILLS_TYPE, "user": actor_id, "startTime": int(start_ms)}
    req = urllib.request.Request(
        HL_INFO_URL, data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"})
    observed_ms = int(time.time() * 1000)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), observed_ms, query


def select_fill_rows(rows, coin: str, expected_dir: str, size,
                     created_ms: int, deadline_ms: int):
    """PURE (A2 R11). The rows that ARE the intent's fill, sorted by (time, tid),
    or None while the fill has not (fully) arrived. SystemExit when the rows can
    never be associated: more than one order in the window, or more size than
    the intent. Nothing is inferred beyond coin, dir, window and one oid."""
    want = _d(size)
    cands = [r for r in rows
             if r.get("coin") == coin and r.get("dir") == expected_dir
             and created_ms <= int(r["time"]) <= deadline_ms]
    if not cands:
        return None
    oids = sorted({int(r["oid"]) for r in cands})
    if len(oids) > 1:
        raise SystemExit(f"{len(oids)} orders {oids} match the intent's window; "
                         "ambiguous, no capture is written.")
    total = sum((_d(r["sz"]) for r in cands), Decimal(0))
    if total < want:
        return None
    if total > want:
        raise SystemExit(f"matched fills sum to {total} > intent size {want}; "
                         "no capture is written.")
    return sorted(cands, key=lambda r: (int(r["time"]), int(r["tid"])))


def build_live(preview_json: Path, actor_id: str, control_wallet: str | None,
               open_capture: Path | None, fills_json: Path | None,
               fills_observed_ms: int | None, mids_json: Path | None,
               mids_observed_ms: int | None, max_bps: str, max_shadow_lag_ms: int,
               max_fill_after_expiry_ms: int, max_pnl_recon_usd: str,
               poll_seconds: int) -> tuple[Path, Path]:
    """The LIVE leg (PREREG A2): the venue's preview beside the chain's fill and
    a PAPER shadow at the same instant. READS only; never submits."""
    actor_id = actor_id.lower()

    # --- intent side: the gdex preview, saved verbatim, pinned before parsing ---
    raw_prev = preview_json.read_bytes().replace(b"\r\n", b"\n")
    prev_sha = _sha(raw_prev)
    prev = json.loads(raw_prev.decode("utf-8"))
    preview_id = prev["previewId"]
    terms = prev["terms"]
    kind = prev.get("kind")
    if kind not in ("perp_open", "perp_close"):
        raise SystemExit(f"preview kind {kind!r} is out of scope; no capture is "
                         "written.")
    if terms.get("dex"):
        raise SystemExit("builder-DEX previews are out of scope; no capture is "
                         "written.")
    created_ms, expires_ms = int(prev["createdAt"]), int(prev["expiresAt"])
    intent_date = _iso(created_ms)
    coin, size, side = terms["coin"], terms["size"], terms["side"]
    side_sign = _side_sign(side)
    dest_prev = HERE / f"gdex_preview_{preview_id}.json"
    if dest_prev.exists():
        if dest_prev.read_bytes().replace(b"\r\n", b"\n") != raw_prev:
            raise SystemExit(f"{dest_prev.name} exists with different bytes.")
    elif dest_prev.resolve() != preview_json.resolve():
        _write_lf(dest_prev, raw_prev.decode("utf-8"))

    # --- a close leg names the pinned LIVE open leg it closes (R17) ------------
    closes = None
    open_id = preview_id
    if kind == "perp_close":
        if open_capture is None:
            raise SystemExit("a perp_close preview requires --open-capture (the "
                             "pinned LIVE open leg); no capture is written.")
        open_raw = open_capture.read_bytes().replace(b"\r\n", b"\n")
        opened = json.loads(open_raw.decode("utf-8"))
        if (opened.get("kind") != "agent_record_capture"
                or opened.get("mode") != "LIVE" or "closes" in opened
                or opened["intent"].get("kind") != "perp_open"):
            raise SystemExit("--open-capture must be a LIVE OPEN agent_record "
                             "capture.")
        o_intent, o_fill = opened["intent"], opened["live_fill"]
        if o_intent["market"] != coin or _d(o_intent["size"]) != _d(size):
            raise SystemExit("the close preview's coin/size differ from the open "
                             "leg's; no capture is written.")
        open_dir = _side_sign(o_intent["side"])
        if side_sign != -open_dir:
            raise SystemExit(f"close side {side!r} does not close a "
                             f"{o_intent['side']} position; no capture is written.")
        open_id = o_intent["intent_id"]
        expected_dir = _DIR_FOR[("perp_close", side_sign)]
        closes = {
            "capture": open_capture.name,
            "sha256": _sha(open_raw),
            "intent_id": open_id,
            "fill_id": o_fill["fill_id"],
            "side": "long" if open_dir == 1 else "short",
            "size": size,
            "fill_price_usd": o_fill["price_usd"],
            "fill_fee_usd": o_fill["fee_usd"],
        }
    else:
        expected_dir = _DIR_FOR[("perp_open", side_sign)]
    deadline_ms = expires_ms + int(max_fill_after_expiry_ms)

    # --- outcome side: the chain's fill record, polled, verbatim ---------------
    if fills_json is not None:
        raw_fills = fills_json.read_bytes().replace(b"\r\n", b"\n")
        if fills_observed_ms is None:
            raise SystemExit("--fills-json requires --fills-observed-ms.")
        fills_ms = fills_observed_ms
        fills_query = {"type": HL_FILLS_TYPE, "user": actor_id,
                       "startTime": created_ms}
        fills_origin = f"saved payload {fills_json.name}"
        rows = select_fill_rows(json.loads(raw_fills.decode("utf-8")), coin,
                                expected_dir, size, created_ms, deadline_ms)
        if rows is None:
            raise SystemExit("the saved fills payload holds no complete fill for "
                             "this intent; no capture is written.")
    else:
        started = time.time()
        while True:
            raw_fills, fills_ms, fills_query = fetch_fills(actor_id, created_ms)
            rows = select_fill_rows(json.loads(raw_fills.decode("utf-8")), coin,
                                    expected_dir, size, created_ms, deadline_ms)
            if rows is not None:
                break
            if time.time() - started > poll_seconds:
                raise SystemExit(f"no complete {expected_dir} {coin} fill of {size} "
                                 f"for {actor_id} within {poll_seconds}s; no "
                                 "capture is written.")
            time.sleep(2)
        fills_origin = f"live POST {HL_INFO_URL} {json.dumps(fills_query)}"

    # --- the PAPER shadow at the same instant, verbatim ------------------------
    raw_mids, shadow_ms, mids_origin = _load_mids(mids_json, mids_observed_ms)
    mids = json.loads(raw_mids.decode("utf-8"))
    if coin not in mids:
        raise SystemExit(f"{coin} not in allMids; no capture is written.")

    fills_path = HERE / f"hl_{HL_FILLS_TYPE}_{fills_ms}.json"
    fills_sha = _pin_verbatim(fills_path, raw_fills)
    mids_path = HERE / f"hl_allMids_{shadow_ms}.json"
    mids_sha = _pin_verbatim(mids_path, raw_mids)

    # --- aggregate the fill rows (R11): one order, sizes summing to the intent ---
    total_sz = sum((_d(r["sz"]) for r in rows), Decimal(0))
    live_px = sum((_d(r["px"]) * _d(r["sz"]) for r in rows), Decimal(0)) / total_sz
    fee = sum((_d(r["fee"]) + _d(r.get("builderFee", "0")) for r in rows), Decimal(0))
    tokens = sorted({r.get("feeToken") for r in rows})
    if tokens != ["USDC"]:
        raise SystemExit(f"fee token(s) {tokens} are not USDC; no capture is "
                         "written (no conversion is invented).")
    tx_hashes = [r["hash"] for r in rows]
    tids = [int(r["tid"]) for r in rows]
    fill_time_ms = int(rows[-1]["time"])
    fill_date = _iso(fill_time_ms)
    closed_pnl = sum((_d(r["closedPnl"]) for r in rows), Decimal(0))
    quote, shadow_px = _d(terms["price"]), _d(mids[coin])
    gap_bps = (live_px - shadow_px) / shadow_px * Decimal(10000) * side_sign
    shadow_lag_ms = shadow_ms - fill_time_ms
    dev_live = abs(live_px - quote) / quote * Decimal(10000)
    dev_shadow = abs(shadow_px - quote) / quote * Decimal(10000)

    leg = "close" if kind == "perp_close" else "open"
    live_fill_id = f"live:{open_id}:{leg}"
    shadow_fill_id = f"paper:{open_id}:{leg}:shadow"
    capture = {
        "kind": "agent_record_capture",
        "mode": "LIVE",
        "synthetic": False,
        "note": ("LIVE capture, " + leg.upper() + " leg. INTENT SIDE: GDEX's own "
                 "preview (" + GDEX_MCP_TOOL + "), exact executable terms; the "
                 "operator submitted it by hand through their own GDEX account. "
                 "OUTCOME SIDE: the fill the HyperLiquid L1 recorded under the "
                 "actor's wallet (POST " + HL_INFO_URL + " {type: " + HL_FILLS_TYPE
                 + "}), with its transaction hash(es) and the chain's fee; a "
                 "cryptographically signed chain event. SHADOW: this tool's own "
                 "simulated fill at the allMids mid at the instant the fill was "
                 "observed (PAPER, self-asserted), so the sim-to-real gap is one "
                 "number. This tool READ the fill; it submitted nothing. See the "
                 "MANIFEST beside this file."),
        "actor": {
            "actor_id": actor_id,
            "custody": "GDEX managed custody (managed EVM wallet = actor_id)",
            **({"control_wallet": control_wallet.lower()} if control_wallet else {}),
        },
        **({"closes": closes} if closes else {}),
        "intent": {
            "intent_id": preview_id,
            "kind": kind,
            "market": coin,
            "side": side,
            "order_type": terms["orderType"],
            "size": size,
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
            "expires_ms": expires_ms,
            "binding": prev["binding"],
            "tool": GDEX_MCP_TOOL,
            "source_url": GDEX_BASE,
            "observed_date": intent_date,
        },
        "live_fill": {
            "fill_id": live_fill_id,
            "intent_id": preview_id,
            "price_usd": _fmt(live_px),
            "size": size,
            "fee_usd": _fmt(fee),
            "fee_token": "USDC",
            "tx_hashes": tx_hashes,
            "tids": tids,
            "oid": int(rows[-1]["oid"]),
            "fill_time_ms": fill_time_ms,
            "dir": expected_dir,
            "closed_pnl_usd": _fmt(closed_pnl),
            "start_position": str(rows[0]["startPosition"]),
            "explorer_url": HL_EXPLORER_TX + tx_hashes[0],
            "rows": len(rows),
            "mode": "LIVE",
            "source_url": HL_INFO_URL,
            "observed_date": fill_date,
        },
        "shadow_fill": {
            "fill_id": shadow_fill_id,
            "intent_id": preview_id,
            "price_usd": str(mids[coin]),
            "size": size,
            "fee_usd": "0",
            "fee_model": "none (paper shadow at the live fill's instant; the live "
                         "fill beside it carries the chain's fee)",
            "mark_source": "hyperliquid allMids",
            "observed_ms": shadow_ms,
            "source_url": HL_INFO_URL,
            "observed_date": _iso(shadow_ms),
        },
        "association": {"max_fill_after_expiry_ms": int(max_fill_after_expiry_ms)},
        "tolerance": {
            "max_quote_to_fill_bps": str(_d(max_bps)),
            "max_shadow_lag_ms": int(max_shadow_lag_ms),
            **({"max_pnl_recon_usd": str(_d(max_pnl_recon_usd))} if closes else {}),
        },
    }
    suffix = "_close" if closes else ""
    cap_path = HERE / f"capture_LIVE_{intent_date}_{open_id}{suffix}.json"
    cap_bytes = _write_lf(cap_path, json.dumps(capture, indent=2) + "\n")

    manifest = {
        "fixture": cap_path.name,
        "status": "LIVE",
        "leg": leg,
        "bytes": len(cap_bytes),
        "sha256": _sha(cap_bytes),
        "generator": Path(__file__).name,
        **({"closes": {"capture": closes["capture"], "sha256": closes["sha256"]}}
           if closes else {}),
        "source": {
            "intent": {
                "what": "GDEX preview: exact executable terms for an explicit trade "
                        "intent, bound to GDEX managed custody; submitted by the "
                        "operator's own hand, never by this tool.",
                "gdex_mcp_tool": GDEX_MCP_TOOL,
                "custody_backend": GDEX_BASE,
                "payload_verbatim_file": dest_prev.name,
                "payload_sha256": prev_sha,
                "preview_created_ms": created_ms,
                "preview_expires_ms": expires_ms,
                "quote_source": terms["priceSource"],
                "quote_as_of_ms": int(terms["priceAsOf"]),
                "observed_date": intent_date,
            },
            "live_fill": {
                "what": "The fill the HyperLiquid L1 recorded under the actor's "
                        "wallet: a chain event carrying its transaction hash(es) "
                        "and the chain's fee.",
                "api": HL_INFO_URL + " " + json.dumps(fills_query),
                "payload_origin": fills_origin,
                "payload_verbatim_file": fills_path.name,
                "payload_sha256": fills_sha,
                "payload_observed_ms": fills_ms,
                "association": {
                    "rule": "coin == intent.market, dir == expected, created_ms <= "
                            "time <= expires_ms + max_fill_after_expiry_ms, one oid, "
                            "sizes sum exactly to intent.size",
                    "expected_dir": expected_dir,
                    "window_ms": [created_ms, deadline_ms],
                    "rows_matched": len(rows),
                    "oid": int(rows[-1]["oid"]),
                    "tx_hashes": tx_hashes,
                },
                "fee_rule": "sum of fee + builderFee over the matched rows, USDC",
                "observed_date": fill_date,
            },
            "shadow_fill": {
                "what": "Simulated fill of the intent's size at the HyperLiquid mid "
                        "at the instant the live fill was observed. Self-asserted; "
                        "not a chain event.",
                "api": HL_INFO_URL + " " + json.dumps(HL_MIDS_QUERY),
                "payload_origin": mids_origin,
                "payload_verbatim_file": mids_path.name,
                "payload_sha256": mids_sha,
                "observed_ms": shadow_ms,
                "observed_date": _iso(shadow_ms),
            },
        },
        "dispute_semantics": {
            "quote_price_usd": _fmt(quote),
            "live_fill_price_usd": _fmt(live_px),
            "live_deviation_bps": _fmt(dev_live),
            "live_dispute_expected": dev_live > _d(max_bps),
            "shadow_fill_price_usd": _fmt(shadow_px),
            "shadow_deviation_bps": _fmt(dev_shadow),
            "shadow_dispute_expected": dev_shadow > _d(max_bps),
            "max_quote_to_fill_bps": str(_d(max_bps)),
        },
        "sim_to_real_gap": {
            "formula": "(live - paper) / paper * 10000 * cost_sign, Decimal; "
                       "cost_sign +1 when the agent buys, -1 when it sells; "
                       "positive = live cost more than paper",
            "live_price_usd": _fmt(live_px),
            "paper_price_usd": _fmt(shadow_px),
            "cost_sign": side_sign,
            "gap_bps": _fmt(gap_bps),
            "shadow_lag_ms": shadow_lag_ms,
            "max_shadow_lag_ms": int(max_shadow_lag_ms),
            "stale_dispute_expected": abs(shadow_lag_ms) > int(max_shadow_lag_ms),
        },
    }
    if closes:
        open_dir = 1 if closes["side"] == "long" else -1
        fees = _d(closes["fill_fee_usd"]) + fee
        realized = (live_px - _d(closes["fill_price_usd"])) * _d(size) * open_dir - fees
        gross = realized + fees
        manifest["realized_live_pnl"] = {
            "formula": "(close_fill - open_fill) * size * dir - (open_fee + "
                       "close_fee), Decimal, fees from the chain",
            "open_price_usd": closes["fill_price_usd"],
            "close_price_usd": _fmt(live_px),
            "size": size,
            "dir": open_dir,
            "fees_usd": _fmt(fees),
            "realized_pnl_usd": _fmt(realized),
            "bucket": _bucket(realized),
            "venue_closed_pnl_usd": _fmt(closed_pnl),
            "recon_difference_usd": _fmt(abs(gross - closed_pnl)),
            "max_pnl_recon_usd": str(_d(max_pnl_recon_usd)),
            "recon_dispute_expected": abs(gross - closed_pnl) > _d(max_pnl_recon_usd),
        }
    man_path = HERE / f"MANIFEST_LIVE_{intent_date}_{open_id}{suffix}.json"
    _write_lf(man_path, json.dumps(manifest, indent=2) + "\n")
    return cap_path, man_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--close", action="store_true",
                    help="take the paper CLOSE leg of --open-capture (PREREG A1)")
    ap.add_argument("--live", action="store_true",
                    help="LIVE leg (PREREG A2): read the chain's fill of the "
                         "preview the operator submitted by hand; never submits")
    ap.add_argument("--fills-json", default=None, type=Path)
    ap.add_argument("--fills-observed-ms", default=None, type=int)
    ap.add_argument("--max-shadow-lag-ms", default=5000, type=int)
    ap.add_argument("--max-fill-after-expiry-ms", default=60000, type=int)
    ap.add_argument("--max-pnl-recon-usd", default="0.000001")
    ap.add_argument("--poll-seconds", default=120, type=int)
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
    if args.live and args.close:
        raise SystemExit("--live and --close are different legs; pick one")
    if args.live:
        if args.preview_json is None or args.actor_id is None:
            raise SystemExit("--live requires --preview-json and --actor-id")
        cap, man = build_live(args.preview_json, args.actor_id, args.control_wallet,
                              args.open_capture, args.fills_json,
                              args.fills_observed_ms, args.mids_json,
                              args.mids_observed_ms, args.max_bps,
                              args.max_shadow_lag_ms, args.max_fill_after_expiry_ms,
                              args.max_pnl_recon_usd, args.poll_seconds)
    elif args.close:
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
