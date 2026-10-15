"""Upstream capture tool (NOT part of ri_core, NOT a test): snapshot one row of
gdex.pro's own HyperLiquid PnL leaderboard + the on-chain fills of the actor behind
it over the board's trailing-7d window, into the trader_record capture schema.

It reads the network and the clock, as any scraper does. The JSON artifacts it
freezes beside it (capture_REAL_<date>_gdex[_multi].json + MANIFEST_REAL_<date>_
gdex[_multi].json, plus the VERBATIM upstream payloads they were parsed from) are
then pure, deterministic inputs to the pure adapter (adapters/trader_record.py).

THE VENUE SIDE IS GDEX'S OWN SURFACE. The displayed stat comes from
    GET https://trade-api.gemach.io/v1/hl/top_traders_by_pnl
which is exactly the request the published gdex MCP server
(@gemachdao/gdex-mcp-server, tool `get_hl_top_traders_by_pnl`) and SDK
(@gemachdao/gdex-skill, GdexApiClient) make: keyless GET, browser User-Agent
(the endpoint answers 403 "Non-browser clients not allowed" to any other UA, so
the generator sends the SDK's own default UA, verbatim). Pass --board-json to
parse an already-saved payload instead (e.g. the MCP tool's response captured in
session); either way the payload is written verbatim beside the capture and its
sha256 pinned in the MANIFEST before anything is parsed from it.

THE CHAIN SIDE IS THE CHAIN. gdex exposes no per-fill history for a third-party
wallet (probed 2026-10-15, recorded in the MANIFEST), so fills come from the
HyperLiquid L1 info API (userFillsByTime) and each fill's source_url is its L1
explorer page. A fill is a signed transaction; the chain is its source.

THE ADDRESS->ACTOR GROUPING IS INPUT, NEVER COMPUTED HERE OR IN THE ADAPTER.
  default        identity grouping {address}.
  --subaccounts  the HyperLiquid sub-account registry for the address (info
                 type=subAccounts): every sub-account is created by the master's
                 own signed createSubAccount action, so the grouping is
                 chain-attested, not inferred. The registry response is saved
                 verbatim and pinned. (The wallet-independence library was NOT
                 used: it judges measures, never wallets, and emits no
                 address->actor grouping - recorded in the MANIFEST.)

    python rights_events/fixtures/trader_record/capture_from_gdex.py ADDRESS
        [--board-json PATH --board-observed-ms MS] [--subaccounts]

Re-running on a later date writes a new date-stamped set; it never overwrites.
No partial capture is ever written (a capped fill window aborts).
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

HERE = Path(__file__).resolve().parent

GDEX_BASE = "https://trade-api.gemach.io/v1"
GDEX_BOARD_URL = GDEX_BASE + "/hl/top_traders_by_pnl"
GDEX_MCP_TOOL = "@gemachdao/gdex-mcp-server: get_hl_top_traders_by_pnl"
# The gdex SDK's own default User-Agent (GdexApiClient DEFAULT_USER_AGENT). The
# endpoint rejects other UAs with HTTP 403; this is the request gdex itself makes.
GDEX_SDK_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_EXPLORER = "https://app.hyperliquid.xyz/explorer/tx/"
HL_FILL_CAP = 2000  # userFillsByTime returns at most 2000 fills per call

WEEK_MS = 7 * 86400 * 1000

GDEX_PROBE_2026_10_15 = {
    "what": "gdex read tools probed for a per-fill history of a third-party wallet "
            "(the chain side). None served one; the chain side therefore comes "
            "from the L1 info API and is labeled so.",
    "hl_tx_list (GET /v1/hl/tx_list?address=...)":
        "code 101 'missing params' for a leaderboard address (the endpoint lists a "
        "gdex copy-trade user's own transactions, not an arbitrary wallet's).",
    "get_wallet_performance (GET /v1/wallet_performance)":
        "code 101 'missing params' with and without a chain argument.",
    "get_hl_user_stats (GET /v1/hl/user_stats?user=...)":
        "code 103 'Wallet not found' for leaderboard addresses (gdex-managed "
        "wallets only).",
    "get_hl_trade_history":
        "ERR_MODULE_NOT_FOUND '@gdexsdk/hyper-liquid-trader' in the installed MCP "
        "server; and by its source it calls HyperLiquid userFills directly, not a "
        "gdex endpoint.",
    "get_hl_clearinghouse_state (GET /v1/hl/clearinghouse_state?address=...)":
        "works (positions/margin), but carries no fills.",
}

SELECTION_2026_10_15 = {
    "how": "Every distinct address on gdex's four PnL boards (day/week/month/"
           "allTime, 30 rows each) in the pinned payload was scanned: realized-"
           "closed net over the trailing-7d window vs the row's displayed 'week' "
           "bucket; the HL sub-account registry was read for each. One fully-"
           "covered (uncapped) divergence was selected per capture.",
    "distinct_addresses": 84,
    "displayed_vs_realized_bucket_divergence": 43,
    "with_at_least_one_fill": 33,
    "with_at_least_one_fill_and_divergent": 19,
    "fully_covered_with_fills": 11,
    "fully_covered_with_fills_and_divergent": 7,
    "nonzero_displayed_week_pnl_but_zero_closed_fills": 24,
    "with_registered_subaccounts": 25,
    "aggregate_finding": "The displayed week figure is not reproducible from the "
                         "same address's closed fills for 43 of 84 board rows; 24 "
                         "rows display a nonzero week PnL with zero closed fills "
                         "(unrealized mark-to-market only). The verification gap "
                         "is the norm on this board, not a contrived case.",
}


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


def _hl_info(payload: dict):
    req = urllib.request.Request(
        HL_INFO_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:  # 429 backoff
            last = exc
            time.sleep(12 if exc.code == 429 else 2 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - network retry
            last = exc
            time.sleep(2 * (attempt + 1))
    assert last is not None
    raise last


def fetch_gdex_board() -> tuple[bytes, int]:
    """GET the gdex leaderboard exactly as the gdex SDK/MCP does. Returns raw bytes
    and the wall-clock ms at which they were observed."""
    req = urllib.request.Request(GDEX_BOARD_URL, headers={
        "Accept": "application/json", "User-Agent": GDEX_SDK_UA})
    observed_ms = int(time.time() * 1000)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), observed_ms


def board_row(board: dict, addr: str) -> tuple[dict, list[str]]:
    """The row for addr and the boards (day/week/month/allTime) it appears on."""
    row, boards = None, []
    for name in ("week", "day", "month", "allTime"):
        for r in board["topTraders"].get(name, []):
            if r["ethAddress"].lower() == addr.lower():
                boards.append(name)
                row = row or r
    if row is None:
        raise SystemExit(f"{addr} is not on any gdex PnL board in this payload; "
                         "no capture is written.")
    return row, boards


def fills_for(addr: str, start_ms: int, end_ms: int) -> list[dict]:
    fills = _hl_info({"type": "userFillsByTime", "user": addr,
                      "startTime": start_ms, "endTime": end_ms})
    if len(fills) >= HL_FILL_CAP:
        raise SystemExit(f"{addr}: fills capped at {len(fills)}; window not fully "
                         "covered. No partial capture is written.")
    return fills


def build(addr: str, board_json: Path | None, board_observed_ms: int | None,
          subaccounts: bool) -> tuple[Path, Path]:
    addr = addr.lower()

    # --- venue side: gdex's own surface, saved verbatim, pinned before parsing --
    if board_json is not None:
        raw = board_json.read_bytes().replace(b"\r\n", b"\n")
        if board_observed_ms is None:
            raise SystemExit("--board-json requires --board-observed-ms (the ms at "
                             "which that payload was observed).")
        observed_ms = board_observed_ms
        board_origin = (f"saved payload {board_json.name} (the gdex MCP tool "
                        f"response, {GDEX_MCP_TOOL})")
    else:
        raw, observed_ms = fetch_gdex_board()
        board_origin = f"live GET {GDEX_BOARD_URL} with the gdex SDK default UA"
    observed_date = _iso(observed_ms)
    board_path = HERE / f"gdex_hl_top_traders_by_pnl_{observed_date}.json"
    if board_path.exists():
        if board_path.read_bytes().replace(b"\r\n", b"\n") != raw:
            raise SystemExit(f"{board_path.name} exists with different bytes.")
    else:
        _write_lf(board_path, raw.decode("utf-8"))
    board_sha = _sha(raw)
    board = json.loads(raw.decode("utf-8"))
    if not board.get("isSuccess"):
        raise SystemExit("gdex payload isSuccess != true; no capture is written.")
    row, boards = board_row(board, addr)
    wk = dict(row["windowPerformances"])["week"]
    disp_pnl = wk["pnl"]
    disp_bucket = _bucket(_d(disp_pnl))

    # --- grouping: INPUT. identity, or the chain-attested sub-account registry --
    grouping = [addr]
    registry_path: Path | None = None
    registry_sha: str | None = None
    if subaccounts:
        reg_raw_obj = _hl_info({"type": "subAccounts", "user": addr}) or []
        reg_text = json.dumps(reg_raw_obj, indent=2, sort_keys=True) + "\n"
        registry_path = HERE / f"hl_subaccounts_{addr}_{observed_date}.json"
        reg_bytes = _write_lf(registry_path, reg_text)
        registry_sha = _sha(reg_bytes)
        subs = sorted({s["subAccountUser"].lower() for s in reg_raw_obj
                       if s.get("master", "").lower() == addr})
        if not subs:
            raise SystemExit(f"{addr} has no registered sub-accounts; a multi-"
                             "address capture cannot be made without inventing "
                             "one. No capture is written.")
        grouping = [addr, *subs]

    # --- chain side: every grouped address's fills over the board's window -----
    end_ms = observed_ms
    start_ms = end_ms - WEEK_MS
    out_fills: list[dict] = []
    per_addr: dict[str, dict] = {}
    for a in grouping:
        fills = fills_for(a, start_ms, end_ms)
        net_a = Decimal(0)
        for f in sorted(fills, key=lambda f: (f["time"], str(f["tid"]))):
            net_a += _d(f.get("closedPnl", "0")) - _d(f.get("fee", "0"))
            out_fills.append({
                "fill_id": str(f["tid"]),
                "address": a,
                "token": f["coin"],
                "side": f.get("dir", f.get("side", "")),
                "realized_pnl_usdc": f.get("closedPnl", "0"),
                "fee_usdc": f.get("fee", "0"),
                "tx_sig": f["hash"],
                "source_url": HL_EXPLORER + f["hash"],
                "observed_date": _iso(f["time"]),
                "_t": f["time"],
            })
        per_addr[a] = {"fill_count": len(fills), "realized_net_usdc": str(net_a),
                       "bucket": _bucket(net_a)}
    if not out_fills:
        raise SystemExit("no fills in the window for the grouping; the adapter "
                         "requires >=1 fill. No capture is written.")
    out_fills.sort(key=lambda f: (f["_t"], f["fill_id"]))
    for f in out_fills:
        del f["_t"]
    net = sum((_d(f["realized_pnl_usdc"]) - _d(f["fee_usdc"]) for f in out_fills),
              Decimal(0))
    chain_bucket = _bucket(net)

    suffix = "_gdex_multi" if subaccounts else "_gdex"
    grouping_note = (
        "the master address plus its HyperLiquid-registered sub-accounts "
        "(chain-attested registry, saved verbatim); a fill outside it is rejected "
        "by the adapter." if subaccounts else "identity {address}.")
    capture = {
        "kind": "trader_record_capture",
        "synthetic": False,
        "note": ("REAL capture. VENUE SIDE: gdex.pro's own HyperLiquid PnL "
                 "leaderboard (GET " + GDEX_BOARD_URL + ", the request the gdex "
                 "MCP tool get_hl_top_traders_by_pnl makes); displayed_net_pnl_usdc "
                 "is the row's 'week' window PnL (includes unrealized mark-to-market "
                 "+ funding). CHAIN SIDE: realized closed PnL (closedPnl - fee) per "
                 "fill for every address in the declared actor grouping over the "
                 "same trailing-7d window ending at the board observation, each "
                 "with its L1 tx hash. GROUPING: " + grouping_note
                 + " See the MANIFEST beside this file."),
        "actor": {"actor_id": addr, "addresses": grouping},
        "venue_claim": {
            "actor_id": addr,
            "window": {"start": _iso(start_ms), "end": _iso(end_ms)},
            "displayed_net_pnl_usdc": disp_pnl,
            "displayed_bucket": disp_bucket,
            "source_url": GDEX_BOARD_URL,
            "observed_date": observed_date,
        },
        "fills": out_fills,
    }
    cap_path = HERE / f"capture_REAL_{observed_date}{suffix}.json"
    cap_bytes = _write_lf(cap_path, json.dumps(capture, indent=2) + "\n")

    if subaccounts:
        assert registry_path is not None and registry_sha is not None
        produced_by = (
            "HyperLiquid sub-account registry (info type=subAccounts) for the "
            "master address: each sub-account exists only because the master "
            "signed a createSubAccount action, so the grouping is chain-attested, "
            f"not inferred. Registry saved verbatim as {registry_path.name} "
            f"(sha256 {registry_sha}).")
        clustering_finding = (
            "wallet-independence (C:/Users/newce/wallet-independence) was examined "
            "as the intended clustering input and does NOT produce an address->"
            "actor grouping: its surveys judge measures, never wallets (M-WI-02: "
            "'no surviving measure is a verdict about any wallet'; 'Classification, "
            "if it ever happens, is a later contract'), and its tooling reads "
            "frozen Solana snapshots. Per the contract's kill rule (no invented "
            "association) the grouping was taken from a chain-attested registry "
            "instead and labeled so here.")
        scope_note = (
            " NOTE: the leaderboard row is PER ADDRESS (the master); per_address "
            "above shows the master-only bucket so a reader can see whether the "
            "divergence lives in the master's own fills or in a sub-account's.")
    else:
        produced_by = "identity grouping {address}: single-address account."
        clustering_finding = (
            "wallet-independence clustering is not applicable to a single address "
            "and was not run; see the _gdex_multi capture for the multi-address "
            "case and its clustering finding.")
        scope_note = ""

    manifest = {
        "fixture": cap_path.name,
        "status": "REAL",
        "bytes": len(cap_bytes),
        "sha256": _sha(cap_bytes),
        "generator": "capture_from_gdex.py",
        "source": {
            "venue_displayed": {
                "what": "gdex.pro HyperLiquid PnL leaderboard row, 'week' window "
                        "PnL (includes unrealized mark-to-market + funding).",
                "url": GDEX_BOARD_URL,
                "gdex_mcp_tool": GDEX_MCP_TOOL,
                "payload_origin": board_origin,
                "payload_verbatim_file": board_path.name,
                "payload_sha256": board_sha,
                "payload_observed_ms": observed_ms,
                "observed_date": observed_date,
                "row_boards": boards,
                "row_account_value": row.get("accountValue"),
                "row_display_name": row.get("displayName"),
                "access_note": "Keyless GET; the endpoint answers HTTP 403 "
                               "'Non-browser clients not allowed' unless the gdex "
                               "SDK's default browser User-Agent is sent, which is "
                               "what the gdex MCP server itself sends.",
            },
            "chain_fills": {
                "what": "Realized closed PnL (closedPnl - fee) per fill for every "
                        "address in the actor grouping over the trailing-7d window "
                        "[start,end] ending at the board observation.",
                "api": HL_INFO_URL + " (type=userFillsByTime)",
                "explorer": HL_EXPLORER + "<tx_hash>",
                "window_start_ms": start_ms,
                "window_end_ms": end_ms,
                "fill_count": len(out_fills),
                "fully_covered": True,
                "per_address": per_addr,
                "why_not_gdex": GDEX_PROBE_2026_10_15,
            },
        },
        "actor_grouping": {
            "rule": "address->actor grouping is an INPUT to the pure adapter, not "
                    "computed by it; a fill outside the grouping raises AdapterError.",
            "addresses": grouping,
            "produced_by": produced_by,
            "clustering_finding": clustering_finding,
        },
        "dispute_semantics": {
            "meaning": "A dispute fires when the displayed window bucket differs "
                       "from the bucket of realized-closed PnL over the same window "
                       "for the declared actor grouping. It records that the "
                       "displayed figure is not reproducible from the actor's "
                       "closed fills (the copier's verification gap) - NOT that any "
                       "single number was falsified." + scope_note,
            "displayed_bucket": disp_bucket,
            "displayed_net_pnl_usdc": disp_pnl,
            "chain_realized_net_pnl_usdc": str(net),
            "chain_bucket": chain_bucket,
            "dispute_expected": disp_bucket != chain_bucket,
        },
        "selection": SELECTION_2026_10_15,
    }
    man_path = HERE / f"MANIFEST_REAL_{observed_date}{suffix}.json"
    _write_lf(man_path, json.dumps(manifest, indent=2) + "\n")
    return cap_path, man_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("address")
    p.add_argument("--board-json", type=Path, default=None,
                   help="already-saved gdex payload (e.g. the MCP tool response)")
    p.add_argument("--board-observed-ms", type=int, default=None,
                   help="wall-clock ms the saved payload was observed at")
    p.add_argument("--subaccounts", action="store_true",
                   help="group the address with its HL-registered sub-accounts")
    a = p.parse_args(argv)
    cap, man = build(a.address, a.board_json, a.board_observed_ms, a.subaccounts)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    print(f"wrote {cap.name} ({cap.stat().st_size} bytes) and {man.name}")
    print(f"actor {doc['actor']['actor_id']}  addresses "
          f"{len(doc['actor']['addresses'])}  fills {len(doc['fills'])}")
    print(f"displayed {doc['venue_claim']['displayed_net_pnl_usdc']} "
          f"{doc['venue_claim']['displayed_bucket']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
