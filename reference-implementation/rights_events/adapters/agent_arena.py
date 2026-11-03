"""Adapter: THE ARENA — Proof of Outcome for any address (PREREG A18, R89–R97).

Pure functions of their inputs (adapters/common.py): no network, no clock, no randomness;
deterministic order; AdapterError on malformed input; every event carries a real
source_url + observed_date or it does not exist. No reasoning, log or transcript is ever
an input (R96): only the capture document and the pinned page bytes the runner hands in
after checking their sha256 (S84).

Three kinds of event, all `chain_assertion`:

  1. The venue's boards, observed (`venue-boards-observation`): every unique address across
     the four windows of ONE pinned board payload, the venue's own strings carried verbatim
     (self_reported; a venue claim about its own users, never checked here). `self_asserted`,
     claimant `gdex-leaderboard` (R92).

  2. One settled outcome per address (`settled-outcome`, R89/R90): the chain's fills and
     funding as HyperLiquid's public info API served them, pages verbatim, summed by the
     founder's document (SETTLED.md): realized_ex_funding = Σ closedPnl − Σ fee (fee already
     holds builderFee, A8); net_with_funding adds Σ funding.usdc. Coverage FULL / PARTIAL /
     NONE is a disclosure, never an estimate. `third_party_attested`, claimant
     `hyperliquid-l1-fills`.

  3. The ranking (`arena-ranking`, R91): FULL rows ranked by net_with_funding; PARTIAL,
     NONE and REFUSED rows listed unranked with their reason; the operator's RECORD row and
     the forks' PAPER rows in the same table; cohort median and share net-positive beside.
     `third_party_attested`, claimant `arena-grader`.

Nothing here opens, closes, sizes or signs anything on any venue.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

SUBJECT_PREFIX = "agent:"
CAPTURE_KIND = "agent_record_arena_capture"
VENUE_CLAIMANT = "gdex-leaderboard"
FILLS_CLAIMANT = "hyperliquid-l1-fills"
GRADER_CLAIMANT = "arena-grader"
BOARDS_OBSERVATION = "venue-boards-observation"
SETTLED_OUTCOME = "settled-outcome"
ARENA_RANKING = "arena-ranking"
WINDOWS = ("day", "week", "month", "allTime")
STATUS_FULL = "FULL"
STATUS_PARTIAL = "PARTIAL"
STATUS_NONE = "NONE"
STATUS_REFUSED = "REFUSED"
STATUS_RECORD = "RECORD"
STATUS_PAPER = "PAPER"
PAGE_CAP = 2000             # fills a response (measured 2026-11-03; the venue's docs agree)
HORIZON_CAP = 10000         # only the 10 000 most recent fills are available
LATE_START_MS = 24 * 3600 * 1000
_HEX64 = frozenset("0123456789abcdef")
_DISPLAYED = ("pnl", "roi", "vlm")


def _require_str(container: dict, key: str, ctx: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{ctx}: missing or empty {key!r}")
    return value


def _require_int(container: dict, key: str, ctx: str) -> int:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdapterError(f"{ctx}: {key!r} must be an integer")
    return value


def _require_bool(container: dict, key: str, ctx: str) -> bool:
    value = container.get(key)
    if not isinstance(value, bool):
        raise AdapterError(f"{ctx}: {key!r} must be a boolean")
    return value


def _decimal(raw, ctx: str) -> Decimal:
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        raise AdapterError(f"{ctx}: numeric value may not be a bool")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise AdapterError(f"{ctx}: {raw!r} is not numeric") from exc
    raise AdapterError(f"{ctx}: missing or non-numeric value {raw!r}")


def _require_sha256(container: dict, key: str, ctx: str) -> str:
    value = _require_str(container, key, ctx)
    if len(value) != 64 or not set(value) <= _HEX64:
        raise AdapterError(f"{ctx}: {key!r} must be 64 lowercase hex characters")
    return value


def _require_address(raw, ctx: str) -> str:
    if not isinstance(raw, str) or len(raw) != 42 or not raw.startswith("0x") \
            or not set(raw[2:].lower()) <= _HEX64:
        raise AdapterError(f"{ctx}: {raw!r} is not an EVM address")
    return raw


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def day_of_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def boards_event_id(observed_ms: int) -> str:
    return f"agent_record:arena:boards:{observed_ms}"


def settled_event_id(cohort_date: str, as_of_date: str, address: str) -> str:
    return f"agent_record:arena:settled:{cohort_date}:{as_of_date}:{address.lower()}"


def ranking_event_id(cohort_date: str, as_of_date: str) -> str:
    return f"agent_record:arena:ranking:{cohort_date}:{as_of_date}"


# --- 1. the capture document and the boards event --------------------------------------

def _parse_window(doc: dict) -> dict:
    win = doc.get("window")
    if not isinstance(win, dict):
        raise AdapterError("Document has no window object")
    ctx = "window"
    t0 = _require_int(win, "t0_ms", ctx)
    t1 = _require_int(win, "t1_ms", ctx)
    if t0 <= 0 or t1 <= t0:
        raise AdapterError(f"{ctx}: t1_ms must exceed t0_ms > 0")
    started = _require_bool(win, "started", ctx)
    days = _require_int(win, "days", ctx)
    if days <= 0:
        raise AdapterError(f"{ctx}.days must be positive")
    return {"t0_ms": t0, "t1_ms": t1, "t0_date": day_of_ms(t0), "t1_date": day_of_ms(t1),
            "days": days, "started": started,
            "complete": _require_bool(win, "complete", ctx)}


def parse_arena_capture(document_text: str) -> tuple[dict, RightsEvent]:
    """R92: one capture -> (the parsed document, the boards event)."""
    try:
        doc = json.loads(document_text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("Document must be a JSON object")
    if doc.get("kind") != CAPTURE_KIND:
        raise AdapterError(f"Document kind must be {CAPTURE_KIND!r}")
    actor = doc.get("actor")
    if not isinstance(actor, dict):
        raise AdapterError("Document has no actor object")
    actor_id = _require_address(actor.get("actor_id"), "actor.actor_id")

    co = doc.get("cohort")
    if not isinstance(co, dict):
        raise AdapterError("Document has no cohort object")
    ctx = "cohort"
    cohort_date = _require_str(co, "cohort_date", ctx)
    observed_ms = _require_int(co, "observed_ms", ctx)
    if day_of_ms(observed_ms) != cohort_date:
        raise AdapterError(f"{ctx}: observed_ms {observed_ms} is not on {cohort_date}")
    payload_file = _require_str(co, "payload_file", ctx)
    payload_sha = _require_sha256(co, "payload_sha256", ctx)
    source_url = _require_str(co, "source_url", ctx)
    rpw = co.get("rows_per_window")
    if not isinstance(rpw, dict) or set(rpw) != set(WINDOWS) \
            or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                       for v in rpw.values()):
        raise AdapterError(f"{ctx}.rows_per_window must count every window in {WINDOWS}")
    addresses = co.get("addresses")
    if not isinstance(addresses, list) or not addresses:
        raise AdapterError(f"{ctx}.addresses must be a non-empty list")
    verbatim: list[dict] = []
    seen: set[str] = set()
    for i, a in enumerate(addresses):
        actx = f"{ctx}.addresses[{i}]"
        if not isinstance(a, dict):
            raise AdapterError(f"{actx} must be an object")
        address = _require_address(a.get("address"), f"{actx}.address")
        if address.lower() in seen:
            raise AdapterError(f"{actx}: {address} listed twice (a cohort is unique addresses)")
        seen.add(address.lower())
        first_window = _require_str(a, "first_window", actx)
        if first_window not in WINDOWS:
            raise AdapterError(f"{actx}.first_window {first_window!r} not in {WINDOWS}")
        first_rank = _require_int(a, "first_rank", actx)
        if first_rank <= 0:
            raise AdapterError(f"{actx}.first_rank must be positive")
        account_value = _decimal(a.get("account_value"), f"{actx}.account_value")
        displayed = a.get("displayed")
        if not isinstance(displayed, dict) or not displayed:
            raise AdapterError(f"{actx}.displayed must be a non-empty object")
        shown = {}
        for w in WINDOWS:
            if w not in displayed:
                continue
            d = displayed[w]
            if not isinstance(d, dict):
                raise AdapterError(f"{actx}.displayed.{w} must be an object")
            shown[w] = {"rank": _require_int(d, "rank", f"{actx}.displayed.{w}")}
            for k in _DISPLAYED:
                shown[w][k] = _decimal(d.get(k), f"{actx}.displayed.{w}.{k}")
        if first_window not in shown:
            raise AdapterError(f"{actx}: first_window {first_window!r} not among displayed")
        verbatim.append({"address": address, "first_window": first_window,
                         "first_rank": first_rank, "account_value": account_value,
                         "displayed": shown})
    window = _parse_window(doc)
    if window["t0_ms"] <= observed_ms:
        raise AdapterError("window.t0_ms must open AFTER the observation (R91: rows observed "
                           "on D are graded on D+1 onward)")
    as_of = doc.get("as_of")
    if not isinstance(as_of, dict):
        raise AdapterError("Document has no as_of object")
    as_of_date = _require_str(as_of, "as_of_date", "as_of")
    _require_str(as_of, "api", "as_of")

    event = RightsEvent(
        event_id=boards_event_id(observed_ms),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(f"{SUBJECT_PREFIX}{actor_id}",),
        claimant=VENUE_CLAIMANT,
        claim={
            "mechanism": BOARDS_OBSERVATION,
            "cohort_date": cohort_date,
            "observed_ms": observed_ms,
            "payload_file": payload_file,
            "payload_sha256": payload_sha,
            "windows": list(WINDOWS),
            "rows_per_window": {w: rpw[w] for w in WINDOWS},
            "addresses": len(verbatim),
            "addresses_verbatim": verbatim,
            "window": {k: window[k] for k in ("t0_ms", "t1_ms", "t0_date", "t1_date",
                                               "days", "started", "complete")},
            "as_of_date": as_of_date,
            "what_is_not_done": ("No venue number is recomputed, re-ranked or corrected; "
                                 "each address is graded separately on the chain's fills "
                                 "in a window that opens after this observation."),
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=source_url,
        observed_date=cohort_date,
    )
    return doc, event


# --- 2. one settled outcome per address ---------------------------------------------------

def _page_pins(row: dict, key: str, ctx: str) -> list[dict]:
    pages = row.get(key)
    if not isinstance(pages, list):
        raise AdapterError(f"{ctx}.{key} must be a list")
    out = []
    for i, p in enumerate(pages):
        pctx = f"{ctx}.{key}[{i}]"
        if not isinstance(p, dict):
            raise AdapterError(f"{pctx} must be an object")
        out.append({"line": _require_int(p, "line", pctx),
                    "sha256": _require_sha256(p, "sha256", pctx),
                    "bytes": _require_int(p, "bytes", pctx),
                    "items": _require_int(p, "items", pctx)})
        if out[-1]["line"] != i:
            raise AdapterError(f"{pctx}.line {out[-1]['line']} != position {i}")
    return out


def check_pages(pins: list[dict], pages: list[bytes], ctx: str) -> None:
    """S84: every page's bytes must hash to its pin; a mismatch refuses the row."""
    if len(pins) != len(pages):
        raise AdapterError(f"{ctx}: {len(pages)} pages on disk, {len(pins)} pinned")
    for pin, data in zip(pins, pages):
        if len(data) != pin["bytes"] or sha256_hex(data) != pin["sha256"]:
            raise AdapterError(f"{ctx}: page {pin['line']} does not hash to its pin (S84)")


def _load_items(pages: list[bytes], ctx: str) -> list[dict]:
    items: list[dict] = []
    for i, data in enumerate(pages):
        try:
            page = json.loads(data.decode("utf-8"), parse_float=Decimal)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError(f"{ctx}: page {i} is not valid JSON: {exc}") from exc
        if not isinstance(page, list):
            raise AdapterError(f"{ctx}: page {i} is not a JSON list")
        for j, it in enumerate(page):
            if not isinstance(it, dict):
                raise AdapterError(f"{ctx}: page {i} item {j} is not an object")
            items.append(it)
    return items


def settle(fills: list[dict], funding: list[dict], t0: int, t1: int, ctx: str) -> dict:
    """SETTLED.md §2–§3 over the items the pages hold, restricted to the window.
    Pure arithmetic on the payload's own strings."""
    seen_tid: set = set()
    in_window: list[dict] = []
    for i, f in enumerate(fills):
        fctx = f"{ctx}.fills[{i}]"
        t = _require_int(f, "time", fctx)
        if t < t0 or t > t1:
            continue
        tid = f.get("tid")
        if tid is not None:
            if tid in seen_tid:
                continue
            seen_tid.add(tid)
        in_window.append(f)
    in_window.sort(key=lambda f: (f["time"], str(f.get("tid", "")), str(f.get("hash", ""))))
    closed = Decimal(0)
    fees = Decimal(0)
    position: dict[str, Decimal] = {}
    daily: dict[str, Decimal] = {}
    hashes: list[str] = []
    for i, f in enumerate(in_window):
        fctx = f"{ctx}.fills[{i}]"
        coin = _require_str(f, "coin", fctx)
        cp = _decimal(f.get("closedPnl"), f"{fctx}.closedPnl")
        fee = _decimal(f.get("fee"), f"{fctx}.fee")
        sz = _decimal(f.get("sz"), f"{fctx}.sz")
        side = _require_str(f, "side", fctx)
        start = _decimal(f.get("startPosition"), f"{fctx}.startPosition")
        h = _require_str(f, "hash", fctx)
        if side not in ("A", "B"):
            raise AdapterError(f"{fctx}.side {side!r} is neither A nor B")
        closed += cp
        fees += fee
        position[coin] = start + (sz if side == "B" else -sz)
        day = day_of_ms(f["time"])
        daily[day] = daily.get(day, Decimal(0)) + cp - fee
        hashes.append(h)
    funding_sum = Decimal(0)
    funding_rows = 0
    seen_f: set = set()
    for i, r in enumerate(funding):
        rctx = f"{ctx}.funding[{i}]"
        t = _require_int(r, "time", rctx)
        if t < t0 or t > t1:
            continue
        delta = r.get("delta")
        if not isinstance(delta, dict):
            raise AdapterError(f"{rctx}.delta must be an object")
        if delta.get("type") != "funding":
            continue
        key = (t, str(delta.get("coin")), str(delta.get("usdc")))
        if key in seen_f:
            continue
        seen_f.add(key)
        usdc = _decimal(delta.get("usdc"), f"{rctx}.delta.usdc")
        funding_sum += usdc
        funding_rows += 1
        day = day_of_ms(t)
        daily[day] = daily.get(day, Decimal(0)) + usdc
    open_at_end = {c: p for c, p in sorted(position.items()) if p != 0}
    return {
        "fills": len(in_window),
        "closed_pnl": closed,
        "fees": fees,
        "realized_ex_funding": closed - fees,
        "funding": funding_sum,
        "funding_rows": funding_rows,
        "net_with_funding": closed - fees + funding_sum,
        "open_at_window_end": open_at_end,
        "first_time_ms": in_window[0]["time"] if in_window else None,
        "last_time_ms": in_window[-1]["time"] if in_window else None,
        "first_tx": hashes[0] if hashes else None,
        "last_tx": hashes[-1] if hashes else None,
        "daily": [{"day": d, "net": daily[d]} for d in sorted(daily)],
    }


def coverage(n_fills: int, pins: list[dict], first_time_ms: int | None, t0: int) -> tuple[str, str]:
    """R90: FULL / PARTIAL / NONE, with the reason in words. Never an estimate."""
    served = sum(p["items"] for p in pins)
    if n_fills == 0:
        return STATUS_NONE, ("zero fills served in the window: nothing settled under this "
                            "address on the perp L1 as the public API serves it")
    if served >= HORIZON_CAP:
        return STATUS_PARTIAL, (f"{served} fills served = the API's horizon (only the "
                                f"{HORIZON_CAP} most recent fills are available); earlier "
                                "fills in the window are beyond it")
    first_full = bool(pins) and pins[0]["items"] >= PAGE_CAP
    if first_full and first_time_ms is not None and first_time_ms > t0 + LATE_START_MS:
        return STATUS_PARTIAL, ("the first served fill is more than 24 h after the window "
                                "opened and the first page is full: the API's horizon cut "
                                "the start of the window")
    return STATUS_FULL, "every fill in the window the API holds was served"


def settled_event(doc: dict, boards: RightsEvent, row: dict, fill_pages: list[bytes],
                  funding_pages: list[bytes], source_url: str) -> RightsEvent:
    """R89/R90: one address, its pages (already sha-checked by check_pages), one event."""
    ctx = f"rows[{row.get('address')}]"
    address = _require_address(row.get("address"), f"{ctx}.address")
    fill_pins = _page_pins(row, "fills_pages", ctx)
    fund_pins = _page_pins(row, "funding_pages", ctx)
    check_pages(fill_pins, fill_pages, ctx + ".fills")
    check_pages(fund_pins, funding_pages, ctx + ".funding")
    win = boards.claim["window"]
    t0, t1 = win["t0_ms"], win["t1_ms"]
    fills = _load_items(fill_pages, ctx + ".fills")
    funding = _load_items(funding_pages, ctx + ".funding")
    s = settle(fills, funding, t0, t1, ctx)
    status, reason = coverage(s["fills"], fill_pins, s["first_time_ms"], t0)
    as_of_date = boards.claim["as_of_date"]
    claim = {
        "mechanism": SETTLED_OUTCOME,
        "cohort_date": boards.claim["cohort_date"],
        "as_of_date": as_of_date,
        "address": address,
        "window": dict(win),
        "fills_file": _require_str(row, "fills_file", ctx),
        "funding_file": _require_str(row, "funding_file", ctx),
        "fills_pages": fill_pins,
        "funding_pages": fund_pins,
        "fills_served": sum(p["items"] for p in fill_pins),
        "coverage": status,
        "coverage_reason": reason,
        **{k: s[k] for k in ("fills", "closed_pnl", "fees", "realized_ex_funding", "funding",
                             "funding_rows", "net_with_funding", "open_at_window_end",
                             "first_time_ms", "last_time_ms", "first_tx", "last_tx", "daily")},
        "rule": ("SETTLED.md: realized_ex_funding = sum closedPnl - sum fee (fee includes "
                 "builderFee, A8); net_with_funding adds sum funding.usdc; Decimal from the "
                 "payload's own strings; positions open at the window's end counted, never valued"),
        "boards_event_id": boards.event_id,
    }
    return RightsEvent(
        event_id=settled_event_id(boards.claim["cohort_date"], as_of_date, address),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(f"{SUBJECT_PREFIX}{address}",),
        claimant=FILLS_CLAIMANT,
        claim=claim,
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url=source_url,
        observed_date=as_of_date,
        prior_event_refs=(boards.event_id,),
    )


# --- 3. the ranking -------------------------------------------------------------------------

def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    v = sorted(values)
    n = len(v)
    if n % 2:
        return v[n // 2]
    return (v[n // 2 - 1] + v[n // 2]) / 2


def ranking_event(boards: RightsEvent, settled: list[RightsEvent], refused: list[dict],
                  record_row: dict | None, paper_rows: list[dict], source_url: str,
                  verify_command: str) -> RightsEvent:
    """R91: FULL rows ranked by net_with_funding; everything else listed, unranked."""
    as_of_date = boards.claim["as_of_date"]
    cohort_date = boards.claim["cohort_date"]
    by_addr = {e.claim["address"].lower(): e for e in settled}
    listed = [a["address"].lower() for a in boards.claim["addresses_verbatim"]]
    for a in by_addr:
        if a not in listed and (record_row is None or a != record_row["address"].lower()):
            raise AdapterError(f"settled event for {a} is not a cohort address")
    full = [e for e in settled if e.claim["coverage"] == STATUS_FULL
            and e.claim["address"].lower() in listed]
    full.sort(key=lambda e: (-e.claim["net_with_funding"], e.claim["address"].lower()))
    ranked = [{"rank": i + 1, "address": e.claim["address"], "event_id": e.event_id,
               "fills": e.claim["fills"], "realized_ex_funding": e.claim["realized_ex_funding"],
               "funding": e.claim["funding"], "net_with_funding": e.claim["net_with_funding"],
               "open_at_window_end": e.claim["open_at_window_end"]}
              for i, e in enumerate(full)]
    unranked = [{"status": e.claim["coverage"], "address": e.claim["address"],
                 "event_id": e.event_id, "fills": e.claim["fills"],
                 "fills_served": e.claim["fills_served"],
                 "realized_ex_funding": e.claim["realized_ex_funding"],
                 "funding": e.claim["funding"], "net_with_funding": e.claim["net_with_funding"],
                 "reason": e.claim["coverage_reason"]}
                for e in sorted((e for e in settled if e.claim["coverage"] != STATUS_FULL
                                 and e.claim["address"].lower() in listed),
                                key=lambda e: e.claim["address"].lower())]
    for r in refused:
        if not isinstance(r, dict) or not isinstance(r.get("address"), str) \
                or not isinstance(r.get("reason"), str):
            raise AdapterError("a refused row must carry address and reason")
    refused_rows = sorted(({"status": STATUS_REFUSED, "address": r["address"],
                            "reason": r["reason"]} for r in refused),
                          key=lambda r: r["address"].lower())
    counts = {STATUS_FULL: len(full), STATUS_PARTIAL: 0, STATUS_NONE: 0,
              STATUS_REFUSED: len(refused_rows)}
    for u in unranked:
        counts[u["status"]] += 1
    nets = [e.claim["net_with_funding"] for e in full]
    share_positive = (Decimal(sum(1 for n in nets if n > 0)) / Decimal(len(nets))
                      if nets else None)
    missing = [a for a in listed if a not in by_addr
               and a not in {r["address"].lower() for r in refused_rows}]
    if missing and boards.claim["window"]["started"]:
        raise AdapterError(f"{len(missing)} cohort addresses have neither a settled event "
                           f"nor a refusal: {missing[:3]}")
    claim = {
        "mechanism": ARENA_RANKING,
        "cohort_date": cohort_date,
        "as_of_date": as_of_date,
        "window": dict(boards.claim["window"]),
        "addresses_in_cohort": len(listed),
        "counts": counts,
        "ranked": ranked,
        "unranked": unranked,
        "refused": refused_rows,
        "median_net_full": _median(nets),
        "share_positive_full": share_positive,
        "record_row": record_row,
        "paper_rows": paper_rows,
        "nothing_averaged_across_cohorts": True,
        "verify_command": verify_command,
        "boards_event_id": boards.event_id,
    }
    refs = tuple([boards.event_id] + sorted(e.event_id for e in settled))
    return RightsEvent(
        event_id=ranking_event_id(cohort_date, as_of_date),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=boards.subject_ids,
        claimant=GRADER_CLAIMANT,
        claim=claim,
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url=source_url,
        observed_date=as_of_date,
        prior_event_refs=refs,
    )
