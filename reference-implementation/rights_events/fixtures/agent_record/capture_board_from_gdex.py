"""Upstream capture tool (NOT part of ri_core, NOT a test): freeze the venue's
public `week` board VERBATIM beside whether the operator's own account appears on
it, into the agent_record_board_capture schema (PREREG A3, Day 4).

It reads the network and the clock, as any capture tool does. The JSON artifacts
it freezes (gdex_hl_top_traders_by_pnl_<date>.json verbatim, capture_BOARD_<date>
.json, MANIFEST_BOARD_<date>.json) are then pure, deterministic inputs to the pure
adapter (adapters/agent_board.py).

THE VENUE SIDE IS GDEX'S OWN PAYLOAD. `GET https://trade-api.gemach.io/v1/hl/
top_traders_by_pnl` is the request the gdex SDK and the gdex MCP tool
`get_hl_top_traders_by_pnl` make. Measured 2026-10-25: the endpoint answers HTTP
403 "Access denied: Non-browser clients not allowed" to a bare client and 200 to
the gdex SDK's own default User-Agent, which this tool sends (the same UA
trader_record's capture_from_gdex.py sends). The payload is saved byte-for-byte
and its sha256 pinned before anything is parsed from it. Only the `week` list is
carried; every number stays the payload's own string (R24: nothing recomputed,
re-ranked or corrected).

THIS TOOL READS ONE PUBLIC PAGE. It fetches no address's fills, previews nothing,
submits nothing, moves nothing (S21). No partial capture is ever written: a
payload without isSuccess or without a week list aborts (S18).

    python rights_events/fixtures/agent_record/capture_board_from_gdex.py \
        --actor-id 0x<managed evm wallet> [--control-wallet 0x...] \
        [--board-json PATH --board-observed-ms MS]
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
from pathlib import Path

HERE = Path(__file__).resolve().parent

GDEX_BASE = "https://trade-api.gemach.io/v1"
GDEX_BOARD_URL = GDEX_BASE + "/hl/top_traders_by_pnl"
GDEX_MCP_TOOL = "@gemachdao/gdex-mcp-server: get_hl_top_traders_by_pnl"
# The gdex SDK's own default User-Agent (GdexApiClient DEFAULT_USER_AGENT). The
# endpoint rejects other UAs with HTTP 403; this is the request gdex itself makes.
GDEX_SDK_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
UA_RULE = ("the gdex SDK default User-Agent (GdexApiClient DEFAULT_USER_AGENT); a "
           "bare client is answered HTTP 403 'Access denied: Non-browser clients "
           "not allowed' (measured 2026-10-25)")
WINDOW = "week"
ALL_WINDOWS = ("day", "week", "month", "allTime")


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_lf(path: Path, text: str) -> bytes:
    data = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def fetch_board() -> tuple[bytes, int]:
    """GET the board exactly as the gdex SDK does. Raw bytes + observed ms."""
    req = urllib.request.Request(GDEX_BOARD_URL, headers={
        "Accept": "application/json", "User-Agent": GDEX_SDK_UA})
    observed_ms = int(time.time() * 1000)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(), observed_ms
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{GDEX_BOARD_URL} answered HTTP {exc.code}; no capture "
                         "is written.") from exc


def week_rows(board: dict) -> list[dict]:
    """The `week` list as rows in payload order, strings carried unchanged (S18)."""
    if board.get("isSuccess") is not True:
        raise SystemExit("payload isSuccess != true; no capture is written (S18).")
    top = board.get("topTraders")
    if not isinstance(top, dict) or not isinstance(top.get(WINDOW), list) \
            or not top[WINDOW]:
        raise SystemExit(f"payload has no topTraders.{WINDOW} list; no capture is "
                         "written (S18).")
    rows = []
    for i, r in enumerate(top[WINDOW]):
        perf = dict(r.get("windowPerformances") or [])
        wk = perf.get(WINDOW)
        if not isinstance(r.get("ethAddress"), str) or "accountValue" not in r \
                or not isinstance(wk, dict) or not {"pnl", "roi", "vlm"} <= set(wk):
            raise SystemExit(f"week row {i} lacks ethAddress/accountValue/week "
                             "performance; no capture is written (S18).")
        rows.append({
            "rank": i + 1,
            "address": r["ethAddress"],
            "account_value_usdc": str(r["accountValue"]),
            "week_pnl_usdc": str(wk["pnl"]),
            "week_roi": str(wk["roi"]),
            "week_vlm": str(wk["vlm"]),
        })
    return rows


def boards_listing(board: dict, actor_id: str) -> list[str]:
    """Every window whose list carries the actor's address (any case)."""
    top = board.get("topTraders") or {}
    out = []
    for name in ALL_WINDOWS:
        rows = top.get(name) or []
        if any(isinstance(r, dict) and str(r.get("ethAddress", "")).lower()
               == actor_id.lower() for r in rows):
            out.append(name)
    return out


def build_capture(board: dict, observed_ms: int, actor_id: str,
                  control_wallet: str | None, payload_file: str,
                  payload_sha: str, payload_origin: str) -> tuple[dict, dict]:
    """Pure: (payload dict, observation facts) -> (capture, manifest)."""
    rows = week_rows(board)
    listing = boards_listing(board, actor_id)
    observed_date = _iso(observed_ms)
    capture = {
        "kind": "agent_record_board_capture",
        "synthetic": False,
        "note": ("BOARD capture (PREREG A3, Day 4). VENUE SIDE: gdex.pro's public "
                 "HyperLiquid PnL board, `week` window, carried VERBATIM from the "
                 "payload named below — the venue's displayed figures, unverified "
                 "here (self_reported). Nothing is recomputed, re-ranked or "
                 "corrected; no address's fills are fetched. The operator's own "
                 "account is checked for presence on the board and nothing else. "
                 "This tool READ one public page; it submitted nothing."),
        "actor": {
            "actor_id": actor_id,
            "custody": "GDEX managed custody (managed EVM wallet = actor_id)",
            **({"control_wallet": control_wallet} if control_wallet else {}),
        },
        "observation": {
            "window": WINDOW,
            "observed_ms": observed_ms,
            "observed_date": observed_date,
            "source_url": GDEX_BOARD_URL,
            "user_agent_rule": UA_RULE,
            "payload_file": payload_file,
            "payload_sha256": payload_sha,
            "rows": len(rows),
            "actor_on_board": WINDOW in listing,
            "boards_listing_actor": listing,
        },
        "rows": rows,
    }
    cap_text = json.dumps(capture, indent=2) + "\n"
    manifest = {
        "fixture": f"capture_BOARD_{observed_date}.json",
        "status": "BOARD",
        "bytes": len(cap_text.encode("utf-8")),
        "sha256": _sha(cap_text.encode("utf-8")),
        "generator": "capture_board_from_gdex.py",
        "source": {
            "venue_board": {
                "what": ("gdex.pro HyperLiquid PnL leaderboard, `week` window, every "
                         "row as displayed (self_reported; a venue claim about its "
                         "own users, not a chain event). Only presence of the "
                         "operator's own address is checked."),
                "api": f"GET {GDEX_BOARD_URL}",
                "gdex_mcp_tool": GDEX_MCP_TOOL,
                "payload_origin": payload_origin,
                "payload_verbatim_file": payload_file,
                "payload_sha256": payload_sha,
                "payload_observed_ms": observed_ms,
                "user_agent_rule": UA_RULE,
                "windows_in_payload": [w for w in ALL_WINDOWS
                                       if isinstance((board.get("topTraders") or {})
                                                     .get(w), list)],
                "rows_per_window": {w: len((board.get("topTraders") or {}).get(w) or [])
                                    for w in ALL_WINDOWS},
                "observed_date": observed_date,
            },
            "record": {
                "what": ("The operator's own committed run files (Days 1-3), read by "
                         "the runner through RightsPipeline.load — not by this tool."),
            },
        },
        "known_answer": {
            "rows": len(rows),
            "actor_on_board": WINDOW in listing,
            "boards_listing_actor": listing,
        },
    }
    return capture, manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--actor-id", required=True)
    p.add_argument("--control-wallet", default=None)
    p.add_argument("--board-json", type=Path, default=None,
                   help="use this saved payload instead of fetching")
    p.add_argument("--board-observed-ms", type=int, default=None)
    args = p.parse_args(argv)

    if args.board_json is not None:
        if args.board_observed_ms is None:
            raise SystemExit("--board-json requires --board-observed-ms")
        raw = args.board_json.read_bytes().replace(b"\r\n", b"\n")
        observed_ms = args.board_observed_ms
        origin = f"saved payload {args.board_json.name}"
    else:
        raw, observed_ms = fetch_board()
        origin = f"live GET {GDEX_BOARD_URL} with the gdex SDK default UA"
    observed_date = _iso(observed_ms)
    board = json.loads(raw.decode("utf-8"))
    payload_file = f"gdex_hl_top_traders_by_pnl_{observed_date}.json"
    payload_path = HERE / payload_file
    payload_sha = _sha(raw)
    capture, manifest = build_capture(board, observed_ms, args.actor_id,
                                      args.control_wallet, payload_file,
                                      payload_sha, origin)
    if payload_path.exists() and payload_path.read_bytes().replace(b"\r\n", b"\n") != raw:
        raise SystemExit(f"{payload_file} exists with different bytes; nothing written.")
    cap_path = HERE / f"capture_BOARD_{observed_date}.json"
    man_path = HERE / f"MANIFEST_BOARD_{observed_date}.json"
    for path in (cap_path, man_path):
        if path.exists():
            raise SystemExit(f"{path.name} already exists; nothing written.")
    payload_path.write_bytes(raw)
    _write_lf(cap_path, json.dumps(capture, indent=2) + "\n")
    _write_lf(man_path, json.dumps(manifest, indent=2) + "\n")
    print(f"BOARD capture: {cap_path.name}  rows {capture['observation']['rows']}  "
          f"actor_on_board {capture['observation']['actor_on_board']}  "
          f"boards_listing_actor {capture['observation']['boards_listing_actor']}")
    print(f"payload: {payload_file}  bytes {len(raw)}  sha256 {payload_sha}")
    print(f"manifest: {man_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
