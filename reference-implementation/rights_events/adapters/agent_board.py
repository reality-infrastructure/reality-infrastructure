"""Adapter: the venue's week board beside the operator's verified row -> rights events.

PREREG A3 (Day 4, 2026-10-25), rules R20-R25. Pure function of its inputs
(adapters/common.py): no network, no clock, no randomness; deterministic order;
AdapterError on malformed input; every event carries a real source_url +
observed_date or it does not exist.

Two inputs, two events:

  1. A board capture (`agent_record_board_capture`): the venue's public `week`
     board carried VERBATIM — 30 rows, the payload's own strings — plus whether
     the operator's own account appears on it. -> ONE `chain_assertion`,
     `self_asserted`, claimant `gdex-leaderboard` (R20). The venue speaks about
     its own users through its own channel; nothing is recomputed, re-ranked,
     corrected or checked against the chain here (R24; rung 3 is where that
     happens).

  2. A record summary: pure data the runner derives from the operator's
     committed run files AFTER each one reloads through RightsPipeline.load
     (signatures re-verify at intake; a tampered file never reaches here).
     -> ONE `chain_assertion`, `third_party_attested`, claimant
     `record-mirror-check`, prior ref = the board event (R21). PAPER and LIVE
     realized figures are summed within a mode across days and NEVER across
     modes (different positions, different fictions).

`cryptographically_signed` is UNUSED here and declared so (R25): the verified
row CITES the L1 hashes the LIVE run file carries; it does not re-sign them.
No dispute mechanism exists for Day 4: a venue row is not checked, so nothing
can be disputed yet — stated, not hidden.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

SUBJECT_PREFIX = "agent:"
CAPTURE_KIND = "agent_record_board_capture"
VENUE_CLAIMANT = "gdex-leaderboard"          # as trader_record's routing claimant
MIRROR_CLAIMANT = "record-mirror-check"
BOARD_OBSERVATION = "venue-board-observation"
VERIFIED_ROW = "verified-row"
STATUS_SELF_REPORTED = "self_reported"
STATUS_VERIFIED = "verified"
WINDOWS = ("week",)
MODES = ("PAPER", "LIVE")
_HEX64 = frozenset("0123456789abcdef")
_ROW_FIELDS = ("account_value_usdc", "week_pnl_usdc", "week_roi", "week_vlm")


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


def board_event_id(window: str, observed_ms: int) -> str:
    return f"agent_record:board:{window}:{observed_ms}"


def mirror_event_id(observed_date: str) -> str:
    return f"agent_record:mirror:{observed_date}"


def parse_board_capture(document_text: str) -> tuple[dict, RightsEvent]:
    """R20: one board capture -> (the parsed document, the board event)."""
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
    subject = f"{SUBJECT_PREFIX}{actor_id}"

    obs = doc.get("observation")
    if not isinstance(obs, dict):
        raise AdapterError("Document has no observation object")
    ctx = "observation"
    window = _require_str(obs, "window", ctx)
    if window not in WINDOWS:
        raise AdapterError(f"{ctx}.window {window!r} not in {WINDOWS} (only the "
                           "week board is mirrored under A3)")
    observed_ms = _require_int(obs, "observed_ms", ctx)
    observed_date = _require_str(obs, "observed_date", ctx)
    source_url = _require_str(obs, "source_url", ctx)
    payload_file = _require_str(obs, "payload_file", ctx)
    payload_sha = _require_sha256(obs, "payload_sha256", ctx)
    n_rows = _require_int(obs, "rows", ctx)
    actor_on_board = _require_bool(obs, "actor_on_board", ctx)
    listing = obs.get("boards_listing_actor")
    if not isinstance(listing, list) or not all(isinstance(w, str) and w
                                                for w in listing):
        raise AdapterError(f"{ctx}.boards_listing_actor must be a list of strings")

    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AdapterError("Document has no non-empty rows list")
    if len(rows) != n_rows:
        raise AdapterError(f"observation.rows {n_rows} != len(rows) {len(rows)} "
                           "(a row count is never invented)")
    verbatim: list[dict] = []
    for i, row in enumerate(rows):
        rctx = f"rows[{i}]"
        if not isinstance(row, dict):
            raise AdapterError(f"{rctx} must be an object")
        rank = _require_int(row, "rank", rctx)
        if rank != i + 1:
            raise AdapterError(f"{rctx}.rank {rank} != payload position {i + 1} "
                               "(no re-ranking, R24)")
        address = _require_address(row.get("address"), f"{rctx}.address")
        entry = {"rank": rank, "address": address}
        for field in _ROW_FIELDS:
            entry[field] = _decimal(row.get(field), f"{rctx}.{field}")
        verbatim.append(entry)
    on_board = any(r["address"].lower() == actor_id.lower() for r in verbatim)
    if on_board != actor_on_board:
        raise AdapterError(f"observation.actor_on_board {actor_on_board} disagrees "
                           f"with the rows ({on_board}); never invented")
    if (window in listing) != actor_on_board:
        raise AdapterError("observation.boards_listing_actor disagrees with "
                           "actor_on_board for the mirrored window")

    event = RightsEvent(
        event_id=board_event_id(window, observed_ms),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=VENUE_CLAIMANT,
        claim={
            "mechanism": BOARD_OBSERVATION,
            "window": window,
            "observed_ms": observed_ms,
            "payload_file": payload_file,
            "payload_sha256": payload_sha,
            "rows": n_rows,
            "actor_on_board": actor_on_board,
            "boards_listing_actor": list(listing),
            "rows_verbatim": verbatim,
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=source_url,
        observed_date=observed_date,
    )
    return doc, event


def _run_file_entry(raw, i: int) -> dict:
    ctx = f"record.run_files[{i}]"
    if not isinstance(raw, dict):
        raise AdapterError(f"{ctx} must be an object")
    entry = {
        "file": _require_str(raw, "file", ctx),
        "sha256": _require_sha256(raw, "sha256", ctx),
        "root": _require_sha256(raw, "root", ctx),
        "events": _require_int(raw, "events", ctx),
        "cryptographically_signed": _require_int(raw, "cryptographically_signed", ctx),
    }
    if entry["events"] <= 0:
        raise AdapterError(f"{ctx}.events must be positive")
    if entry["file"].startswith("run_BOARD_"):
        raise AdapterError(f"{ctx}: a board run file is never its own evidence (R22)")
    modes = raw.get("modes")
    if not isinstance(modes, list) or not modes or not all(m in MODES for m in modes):
        raise AdapterError(f"{ctx}.modes must be a non-empty list over {MODES}")
    if len(set(modes)) != 1:
        raise AdapterError(f"{ctx}.modes mixes {sorted(set(modes))} (R19)")
    entry["mode"] = modes[0]
    realized = raw.get("realized")
    if not isinstance(realized, list):
        raise AdapterError(f"{ctx}.realized must be a list")
    entry["realized"] = []
    for j, r in enumerate(realized):
        rctx = f"{ctx}.realized[{j}]"
        if not isinstance(r, dict):
            raise AdapterError(f"{rctx} must be an object")
        mode = _require_str(r, "mode", rctx)
        if mode != entry["mode"]:
            raise AdapterError(f"{rctx}.mode {mode!r} != run file mode {entry['mode']!r}")
        entry["realized"].append({
            "event_id": _require_str(r, "event_id", rctx),
            "mode": mode,
            "realized_pnl_usd": _decimal(r.get("realized_pnl_usd"),
                                         f"{rctx}.realized_pnl_usd"),
            "fees_usd": _decimal(r.get("fees_usd"), f"{rctx}.fees_usd"),
            "bucket": _require_str(r, "bucket", rctx),
        })
    for key in ("gaps_bps", "tx_hashes", "explorer_urls"):
        value = raw.get(key)
        if not isinstance(value, list):
            raise AdapterError(f"{ctx}.{key} must be a list")
        entry[key] = ([_decimal(v, f"{ctx}.{key}") for v in value] if key == "gaps_bps"
                      else [v for v in value if isinstance(v, str) and v])
        if len(entry[key]) != len(value):
            raise AdapterError(f"{ctx}.{key} holds an empty or non-string item")
    if entry["mode"] == "PAPER" and entry["tx_hashes"]:
        raise AdapterError(f"{ctx}: a PAPER run file cannot carry chain hashes")
    if len(entry["tx_hashes"]) != entry["cryptographically_signed"]:
        raise AdapterError(f"{ctx}: {len(entry['tx_hashes'])} tx hashes != "
                           f"{entry['cryptographically_signed']} signed events")
    return entry


def verified_row_event(board_event: RightsEvent, summary: dict,
                       source_url: str) -> RightsEvent:
    """R21: the operator's verified row, a mechanical computation over the
    reloaded run files, as one third_party_attested event referring to the
    board observation it stands beside."""
    if not isinstance(summary, dict):
        raise AdapterError("record summary must be an object")
    actor_id = _require_address(summary.get("actor_id"), "record.actor_id")
    if board_event.subject_ids != (f"{SUBJECT_PREFIX}{actor_id}",):
        raise AdapterError("record.actor_id is not the board event's subject")
    raw_files = summary.get("run_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise AdapterError("record.run_files must be a non-empty list")
    files = [_run_file_entry(raw, i) for i, raw in enumerate(raw_files)]
    if len({f["file"] for f in files}) != len(files):
        raise AdapterError("record.run_files names a file twice")

    settled = {m: 0 for m in MODES}
    realized = {m: Decimal(0) for m in MODES}
    fees = {m: Decimal(0) for m in MODES}
    realized_events: list[dict] = []
    gaps: list[Decimal] = []
    tx_hashes: list[str] = []
    explorer_urls: list[str] = []
    for f in files:
        for r in f["realized"]:
            settled[r["mode"]] += 1
            realized[r["mode"]] += r["realized_pnl_usd"]
            fees[r["mode"]] += r["fees_usd"]
            realized_events.append({"run_file": f["file"], **r})
        gaps.extend(f["gaps_bps"])
        for h in f["tx_hashes"]:
            if h not in tx_hashes:
                tx_hashes.append(h)
        for u in f["explorer_urls"]:
            if u not in explorer_urls:
                explorer_urls.append(u)
    if len(explorer_urls) != len(tx_hashes):
        raise AdapterError("explorer_urls and tx_hashes differ in count")
    verify_command = ("python -m rights_events.agent_record --verify --run "
                      "rights_events/fixtures/agent_record/<run file>")
    return RightsEvent(
        event_id=mirror_event_id(board_event.observed_date),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=board_event.subject_ids,
        claimant=MIRROR_CLAIMANT,
        claim={
            "mechanism": VERIFIED_ROW,
            "status": STATUS_VERIFIED,
            "actor_id": actor_id,
            "run_files": [{k: f[k] for k in ("file", "sha256", "root", "events",
                                             "cryptographically_signed", "mode")}
                          for f in files],
            "roots": [f["root"] for f in files],
            "tx_hashes": tx_hashes,
            "explorer_urls": explorer_urls,
            "settled_pairs": dict(settled),
            "realized_events": realized_events,
            "realized_paper_usd": realized["PAPER"],
            "realized_live_usd": realized["LIVE"],
            "fees_live_usd": fees["LIVE"],
            "gaps_bps": gaps,
            "never_summed_across_modes": True,
            "actor_on_board": board_event.claim["actor_on_board"],
            "board_event_id": board_event.event_id,
            "verify_command": verify_command,
        },
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url=source_url,
        observed_date=board_event.observed_date,
        prior_event_refs=(board_event.event_id,),
    )


def parse_events(document_text: str, summary: dict,
                 record_source_url: str) -> list[RightsEvent]:
    """Both Day-4 events in deterministic order (R5 analog)."""
    _doc, board = parse_board_capture(document_text)
    mirror = verified_row_event(board, summary, record_source_url)
    events = [board, mirror]
    events.sort(key=lambda e: (e.observed_date, e.event_id))
    return events
