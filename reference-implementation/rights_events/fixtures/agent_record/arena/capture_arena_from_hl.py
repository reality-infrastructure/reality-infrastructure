"""Upstream capture tool (NOT part of ri_core, NOT a test): THE ARENA's inputs, pinned
verbatim (PREREG A18, R90, R92).

It reads the network and the clock, as any capture tool does. What it freezes is then a
pure, deterministic input to the pure adapter (adapters/agent_arena.py) and runner
(rights_events/agent_arena.py):

  * the cohort: every unique address across the four windows (day, week, month, allTime)
    of ONE board payload — either the pinned payload of an earlier observation (cohort 1 =
    2026-10-25) or a fresh one fetched now and saved byte-for-byte beside this tool;
  * for every cohort address and the operator's own address, the chain's fills and funding
    in the declared window as HyperLiquid's public info API serves them: every HTTP response
    body saved byte-for-byte as ONE LINE of `hl_fills_<address>.jsonl.gz` /
    `hl_funding_<address>.jsonl.gz` (gzip, mtime 0), its sha256 pinned in the capture;
  * `capture_ARENA_<cohort>_<as_of>.json` and `MANIFEST_ARENA_<cohort>_<as_of>.json`.

Pagination (measured 2026-11-03 and the venue's docs): `userFillsByTime` answers at most
2 000 fills a response and only the 10 000 most recent fills exist; the next page starts at
the last fill's `time` + 1. S83: a page that is not HTTP 200 + valid JSON is never written,
the address gets no files and its row is NONE with the error quoted; no partial page exists.

THIS TOOL READS PUBLIC PAGES. It previews nothing, submits nothing, moves nothing.

    python rights_events/fixtures/agent_record/arena/capture_arena_from_hl.py \
        --cohort-date 2026-10-25 --board-json ../gdex_hl_top_traders_by_pnl_2026-10-25.json \
        --observed-ms 1792906235038 --t0 2026-10-26T00:00:00Z --t1 2026-11-02T23:59:59.999Z \
        --actor-id 0x... [--paper-marks ../vps/marks_2026-11-01_as_read_2026-11-03.jsonl ...]
    python .../capture_arena_from_hl.py --fetch-board --actor-id 0x... --days 7 --no-fills
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
GDEX_BASE = "https://trade-api.gemach.io/v1"
GDEX_BOARD_URL = GDEX_BASE + "/hl/top_traders_by_pnl"
GDEX_SDK_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
UA_RULE = ("the gdex SDK default User-Agent (GdexApiClient DEFAULT_USER_AGENT); a bare "
           "client is answered HTTP 403 'Access denied: Non-browser clients not allowed' "
           "(measured 2026-10-25)")
WINDOWS = ("day", "week", "month", "allTime")
FILL_PAGE_CAP = 2000
FUNDING_PAGE_CAP = 500
HORIZON_CAP = 10000
MAX_PAGES = 12
SLEEP_S = 0.6


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_iso(s: str) -> int:
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _gz(lines: list[bytes]) -> bytes:
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g:
        for line in lines:
            g.write(line + b"\n")
    return bio.getvalue()


def _write_lf(path: Path, text: str) -> bytes:
    data = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(data)
    return data


class PageError(Exception):
    pass


def post_info(body: dict) -> bytes:
    """One HTTP response body, byte-for-byte, or PageError (S83). Retries on 429/5xx."""
    data = json.dumps(body).encode("utf-8")
    last = None
    for attempt in range(4):
        req = urllib.request.Request(HL_INFO_URL, data=data, headers={
            "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                if resp.status != 200:
                    raise PageError(f"HTTP {resp.status}")
                try:
                    json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise PageError(f"invalid JSON: {exc}") from exc
                if b"\n" in raw:
                    raise PageError("response body contains a newline; cannot be one line")
                return raw
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 429 or exc.code >= 500:
                time.sleep(61 if exc.code == 429 else 5 * (attempt + 1))
                continue
            raise PageError(last) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"network: {exc}"
            time.sleep(5 * (attempt + 1))
    raise PageError(last or "unknown")


def fetch_pages(kind: str, address: str, t0: int, t1: int) -> list[dict]:
    """All pages of `userFillsByTime` or `userFunding` over [t0, t1], paginated by the
    last item's time + 1. Returns [{raw, items, first, last}] in fetch order."""
    cap = FILL_PAGE_CAP if kind == "userFillsByTime" else FUNDING_PAGE_CAP
    pages = []
    start = t0
    total = 0
    for _ in range(MAX_PAGES):
        body = {"type": kind, "user": address, "startTime": start, "endTime": t1}
        if kind == "userFillsByTime":
            body["aggregateByTime"] = False
        raw = post_info(body)
        time.sleep(SLEEP_S)
        items = json.loads(raw.decode("utf-8"))
        if not isinstance(items, list):
            raise PageError(f"{kind}: page is not a list")
        times = [int(it["time"]) for it in items if isinstance(it, dict) and "time" in it]
        pages.append({"raw": raw, "items": len(items),
                      "first": min(times) if times else None,
                      "last": max(times) if times else None, "request": body})
        total += len(items)
        if len(items) < cap or not times or max(times) >= t1 or total >= HORIZON_CAP:
            break
        start = max(times) + 1
    return pages


def fetch_board() -> tuple[bytes, int]:
    req = urllib.request.Request(GDEX_BOARD_URL, headers={
        "Accept": "application/json", "User-Agent": GDEX_SDK_UA})
    observed_ms = int(time.time() * 1000)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), observed_ms


def cohort_addresses(board: dict) -> tuple[list[dict], dict]:
    """Every unique address across the four windows, in payload order (week, day, month,
    allTime as the venue orders them: first appearance wins), the venue's strings unchanged."""
    if board.get("isSuccess") is not True:
        raise SystemExit("payload isSuccess != true; no capture is written (S83).")
    top = board.get("topTraders")
    if not isinstance(top, dict):
        raise SystemExit("payload has no topTraders; no capture is written (S83).")
    rows_per_window = {w: len(top.get(w) or []) for w in WINDOWS}
    out: list[dict] = []
    index: dict[str, dict] = {}
    for w in WINDOWS:
        for i, r in enumerate(top.get(w) or []):
            addr = r["ethAddress"]
            perf = dict(r.get("windowPerformances") or [])
            d = perf.get(w)
            if not isinstance(d, dict) or not {"pnl", "roi", "vlm"} <= set(d):
                raise SystemExit(f"{w} row {i} lacks its performance; no capture (S83).")
            entry = index.get(addr.lower())
            if entry is None:
                entry = {"address": addr, "first_window": w, "first_rank": i + 1,
                         "account_value": str(r["accountValue"]), "displayed": {}}
                index[addr.lower()] = entry
                out.append(entry)
            entry["displayed"][w] = {"rank": i + 1, "pnl": str(d["pnl"]), "roi": str(d["roi"]),
                                     "vlm": str(d["vlm"])}
    return out, rows_per_window


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cohort-date", default=None, help="YYYY-MM-DD of the pinned observation")
    p.add_argument("--board-json", type=Path, default=None, help="pinned payload (verbatim)")
    p.add_argument("--observed-ms", type=int, default=None)
    p.add_argument("--fetch-board", action="store_true", help="observe the boards now")
    p.add_argument("--t0", default=None, help="window open, ISO (inclusive)")
    p.add_argument("--t1", default=None, help="window close, ISO (inclusive)")
    p.add_argument("--days", type=int, default=7, help="window length when --t0/--t1 absent")
    p.add_argument("--actor-id", required=True)
    p.add_argument("--no-fills", action="store_true", help="window not started: cohort only")
    p.add_argument("--paper-marks", action="append", default=[],
                   help="pinned marks files (relative to the fixtures dir) for PAPER rows")
    p.add_argument("--as-of-date", default=None)
    p.add_argument("--only", type=int, default=None, help="debug: first N addresses")
    a = p.parse_args(argv)

    if a.fetch_board:
        raw, observed_ms = fetch_board()
        cohort_date = datetime.fromtimestamp(observed_ms / 1000, tz=timezone.utc).date().isoformat()
        payload_file = f"gdex_hl_top_traders_by_pnl_{cohort_date}.json"
        out_dir = HERE / cohort_date
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / payload_file).write_bytes(raw)
        payload_rel = payload_file
        payload_origin = f"live GET {GDEX_BOARD_URL} with the gdex SDK default UA at {observed_ms}"
    else:
        if not (a.cohort_date and a.board_json and a.observed_ms):
            print("ERROR: --cohort-date, --board-json and --observed-ms are required without --fetch-board")
            return 2
        raw = a.board_json.read_bytes()
        observed_ms = a.observed_ms
        cohort_date = a.cohort_date
        out_dir = HERE / cohort_date
        out_dir.mkdir(parents=True, exist_ok=True)
        payload_rel = "../../" + a.board_json.resolve().relative_to(FIXTURES).as_posix()
        payload_origin = f"the pinned payload {a.board_json.name} (A3.1, observed {observed_ms})"
    payload_sha = _sha(raw)
    board = json.loads(raw.decode("utf-8"))
    addresses, rows_per_window = cohort_addresses(board)
    if a.only:
        addresses = addresses[:a.only]

    if a.t0 and a.t1:
        t0, t1 = _parse_iso(a.t0), _parse_iso(a.t1)
    else:
        d = datetime.fromisoformat(cohort_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
        t0 = int(d.timestamp() * 1000)
        t1 = int((d + timedelta(days=a.days)).timestamp() * 1000) - 1
    if t0 <= observed_ms:
        print("ERROR: the window must open after the observation (R91)")
        return 2
    now_ms = int(time.time() * 1000)
    as_of_date = a.as_of_date or datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).date().isoformat()
    days = round((t1 + 1 - t0) / 86_400_000)
    started = now_ms >= t0 and not a.no_fills
    complete = now_ms > t1

    rows = []
    targets = list(addresses)
    if a.actor_id.lower() not in {x["address"].lower() for x in targets}:
        targets.append({"address": a.actor_id})
    if started:
        for n, entry in enumerate(targets, 1):
            addr = entry["address"]
            try:
                fills = fetch_pages("userFillsByTime", addr, t0, t1)
                funding = fetch_pages("userFunding", addr, t0, t1)
            except PageError as exc:
                print(f"[{n}/{len(targets)}] {addr} S83 {exc}: no files written")
                rows.append({"address": addr, "error": str(exc)})
                continue
            fills_name = f"hl_fills_{addr.lower()}.jsonl.gz"
            fund_name = f"hl_funding_{addr.lower()}.jsonl.gz"
            (out_dir / fills_name).write_bytes(_gz([pg["raw"] for pg in fills]))
            (out_dir / fund_name).write_bytes(_gz([pg["raw"] for pg in funding]))
            rows.append({
                "address": addr,
                "fills_file": fills_name,
                "fills_pages": [{"line": i, "sha256": _sha(pg["raw"]), "bytes": len(pg["raw"]),
                                 "items": pg["items"], "first_time_ms": pg["first"],
                                 "last_time_ms": pg["last"], "request": pg["request"]}
                                for i, pg in enumerate(fills)],
                "funding_file": fund_name,
                "funding_pages": [{"line": i, "sha256": _sha(pg["raw"]), "bytes": len(pg["raw"]),
                                   "items": pg["items"], "first_time_ms": pg["first"],
                                   "last_time_ms": pg["last"], "request": pg["request"]}
                                  for i, pg in enumerate(funding)],
                "fetched_ms": int(time.time() * 1000),
            })
            print(f"[{n}/{len(targets)}] {addr} fills {sum(pg['items'] for pg in fills)} in "
                  f"{len(fills)} page(s), funding {sum(pg['items'] for pg in funding)} in "
                  f"{len(funding)} page(s)")
    paper_files = []
    for rel in a.paper_marks:
        path = FIXTURES / rel
        paper_files.append({"file": rel, "sha256": _sha(path.read_bytes())})

    capture = {
        "kind": "agent_record_arena_capture",
        "synthetic": False,
        "note": ("ARENA capture (PREREG A18). VENUE SIDE: gdex.pro's public HyperLiquid PnL "
                 "boards, every unique address across day/week/month/allTime carried VERBATIM "
                 "(self_reported). CHAIN SIDE: each address's fills and funding in the declared "
                 "window as HyperLiquid's public info API serves them, every HTTP response body "
                 "pinned byte-for-byte as one line of a gzip file. Nothing recomputed, re-ranked "
                 "or corrected; nothing submitted."),
        "actor": {"actor_id": a.actor_id,
                  "custody": "GDEX managed custody (managed EVM wallet = actor_id)"},
        "cohort": {
            "cohort_date": cohort_date,
            "observed_ms": observed_ms,
            "payload_file": payload_rel,
            "payload_sha256": payload_sha,
            "payload_origin": payload_origin,
            "source_url": GDEX_BOARD_URL,
            "user_agent_rule": UA_RULE,
            "rows_per_window": rows_per_window,
            "addresses": addresses,
        },
        "window": {"t0_ms": t0, "t1_ms": t1, "t0_iso": _iso_ms(t0), "t1_iso": _iso_ms(t1),
                   "days": days, "started": started, "complete": complete},
        "as_of": {"as_of_date": as_of_date, "fetched_ms": now_ms, "api": HL_INFO_URL,
                  "pagination": ("userFillsByTime: <= 2000 fills a page, only the 10000 most "
                                 "recent fills exist; next startTime = last time + 1; "
                                 "userFunding paged the same way")},
        "paper": {"files": paper_files},
        "rows": rows,
    }
    cap_name = f"capture_ARENA_{cohort_date}_{as_of_date}.json"
    cap_text = json.dumps(capture, indent=2) + "\n"
    cap_bytes = _write_lf(out_dir / cap_name, cap_text)
    files = sorted(p.name for p in out_dir.iterdir() if p.is_file() and p.name != f"MANIFEST_ARENA_{cohort_date}_{as_of_date}.json")
    manifest = {
        "fixture": cap_name,
        "status": "ARENA",
        "bytes": len(cap_bytes),
        "sha256": _sha(cap_bytes),
        "generator": "arena/capture_arena_from_hl.py",
        "cohort_date": cohort_date,
        "as_of_date": as_of_date,
        "window": capture["window"],
        "addresses": len(addresses),
        "rows_with_pages": sum(1 for r in rows if "fills_file" in r),
        "rows_with_errors": sum(1 for r in rows if "error" in r),
        "files": [{"name": n, "bytes": (out_dir / n).stat().st_size,
                   "sha256": _sha((out_dir / n).read_bytes())} for n in files],
        "source": {"venue_boards": {"api": f"GET {GDEX_BOARD_URL}", "payload_origin": payload_origin,
                                    "payload_sha256": payload_sha, "user_agent_rule": UA_RULE},
                   "chain": {"api": HL_INFO_URL, "requests": ["userFillsByTime", "userFunding"],
                             "pages_verbatim": "one HTTP response body a line, gzip mtime 0"}},
    }
    _write_lf(out_dir / f"MANIFEST_ARENA_{cohort_date}_{as_of_date}.json", json.dumps(manifest, indent=2) + "\n")
    print(f"capture: {out_dir / cap_name}  sha256 {manifest['sha256']}  rows {len(rows)} "
          f"(errors {manifest['rows_with_errors']})  window started {started} complete {complete}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
