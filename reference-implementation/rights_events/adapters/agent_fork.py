"""Adapter: the paper stop-fork population -> rights events (PREREG A5, R28-R30).

Pure function of one `agent_record_fork_capture` document (written by the
watcher, watch_stop_forks.py, which READ the public mid from the chain's open
fill to the five-hour gate). Each fork — a stop distance in bps, or `gate_only`
— becomes ONE `chain_assertion`, `ep_type = self_asserted` (a simulation; the
record says so on the event), `claimant = "paper-simulator"`, mode PAPER on the
event, hanging off the REAL open fill event by `prior_event_refs`. Nothing was
submitted for any fork; the live control's real close lives in the LIVE close
capture beside this one.

What the adapter checks rather than trusts (S29: nothing invented):
  - the capture is complete (every fork has an exit; the gate was reached);
  - a fork marked `stop` exited at or after its distance and before the gate; a
    fork marked `gate` exited at or after the gate and never crossed;
  - the gross paper PnL is recomputed from exit_mid, open fill, size and dir
    and must equal the capture's figure;
  - exactly one fork is the live control and its distance is the declared one;
  - `gate_only` carries no distance; every other fork a positive integer.
Forks are compared on GROSS price PnL (a paper fork pays no fee); the
fee_model string says so on every event.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

SUBJECT_PREFIX = "agent:"
CAPTURE_KIND = "agent_record_fork_capture"
FORK_CLAIMANT = "paper-simulator"
FORK = "paper-stop-fork"
GATE_ONLY = "gate_only"
_EXIT_REASONS = ("stop", "gate")
# The public source behind a declared exit mark source (a declared constant, not an
# invention); a document may also carry its own `source_url`.
_SOURCE_URLS = {"hyperliquid allMids": "https://api.hyperliquid.xyz/info"}
_HEX64 = frozenset("0123456789abcdef")


def _require_str(c: dict, key: str, ctx: str) -> str:
    v = c.get(key)
    if not isinstance(v, str) or not v:
        raise AdapterError(f"{ctx}: missing or empty {key!r}")
    return v


def _require_int(c: dict, key: str, ctx: str) -> int:
    v = c.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        raise AdapterError(f"{ctx}: {key!r} must be an integer")
    return v


def _require_bool(c: dict, key: str, ctx: str) -> bool:
    v = c.get(key)
    if not isinstance(v, bool):
        raise AdapterError(f"{ctx}: {key!r} must be a boolean")
    return v


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


def _require_sha256(c: dict, key: str, ctx: str) -> str:
    v = _require_str(c, key, ctx)
    if len(v) != 64 or not set(v) <= _HEX64:
        raise AdapterError(f"{ctx}: {key!r} must be 64 lowercase hex characters")
    return v


def _utc_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def fork_event_id(open_intent_id: str, key: str) -> str:
    return f"agent_record:fork:{open_intent_id}:{key}"


def parse_events(document_text: str) -> list[RightsEvent]:
    """One fork capture -> one self_asserted PAPER event per fork, deterministic order."""
    try:
        doc = json.loads(document_text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("Document must be a JSON object")
    if doc.get("kind") != CAPTURE_KIND:
        raise AdapterError(f"Document kind must be {CAPTURE_KIND!r}")
    if doc.get("mode") != "PAPER":
        raise AdapterError("a fork capture is PAPER by definition (R28)")
    if doc.get("complete") is not True:
        raise AdapterError("fork capture is not complete: the gate was not reached or a "
                           "fork has no exit (S29; nothing is back-filled)")

    actor = doc.get("actor")
    if not isinstance(actor, dict):
        raise AdapterError("Document has no actor object")
    subject = f"{SUBJECT_PREFIX}{_require_str(actor, 'actor_id', 'actor')}"

    o = doc.get("open")
    if not isinstance(o, dict):
        raise AdapterError("Document has no open object")
    ctx = "open"
    open_intent_id = _require_str(o, "intent_id", ctx)
    open_fill_event_id = _require_str(o, "fill_event_id", ctx)
    if not open_fill_event_id.startswith("agent_record:fill:live:"):
        raise AdapterError(f"{ctx}.fill_event_id must name a LIVE fill event")
    open_fill = _decimal(o.get("fill_price_usd"), f"{ctx}.fill_price_usd")
    if open_fill <= 0:
        raise AdapterError(f"{ctx}.fill_price_usd must be positive")
    fill_ms = _require_int(o, "fill_time_ms", ctx)
    size = _decimal(o.get("size"), f"{ctx}.size")
    direction = _require_int(o, "dir", ctx)
    if direction not in (1, -1):
        raise AdapterError(f"{ctx}.dir must be 1 or -1")
    open_capture = _require_str(o, "capture", ctx)
    open_capture_sha = _require_sha256(o, "capture_sha256", ctx)

    rules = doc.get("rules")
    if not isinstance(rules, dict):
        raise AdapterError("Document has no rules object")
    live_stop_bps = _require_int(rules, "live_stop_bps", "rules")
    gate_ms = _require_int(rules, "gate_ms", "rules")
    if gate_ms <= fill_ms:
        raise AdapterError("rules.gate_ms must be after the open fill")
    exit_source = _require_str(rules, "exit_mark_source", "rules")
    source_url = doc.get("source_url") or _SOURCE_URLS.get(exit_source)
    if not isinstance(source_url, str) or not source_url:
        raise AdapterError(f"no source_url for exit_mark_source {exit_source!r} (S6)")
    fee_model = _require_str(rules, "fee_model", "rules")

    tape = doc.get("tape")
    if not isinstance(tape, dict):
        raise AdapterError("Document has no tape object")
    tape_file = _require_str(tape, "file", "tape")
    tape_sha = _require_sha256(tape, "sha256", "tape")
    tape_rows = _require_int(tape, "rows", "tape")
    tape_nulls = _require_int(tape, "null_rows", "tape")
    if tape_rows <= 0 or tape_nulls < 0 or tape_nulls > tape_rows:
        raise AdapterError("tape.rows / tape.null_rows are inconsistent")

    forks = doc.get("forks")
    if not isinstance(forks, dict) or not forks:
        raise AdapterError("Document has no non-empty forks object")
    if GATE_ONLY not in forks:
        raise AdapterError(f"the fork set must contain {GATE_ONLY!r} (R28)")
    events: list[RightsEvent] = []
    controls = []
    for key in sorted(forks, key=lambda k: (k == GATE_ONLY, int(k) if k != GATE_ONLY else 0)):
        f = forks[key]
        fctx = f"forks[{key}]"
        if not isinstance(f, dict):
            raise AdapterError(f"{fctx} must be an object")
        stop_bps = f.get("stop_bps")
        if key == GATE_ONLY:
            if stop_bps is not None:
                raise AdapterError(f"{fctx}.stop_bps must be null")
        else:
            if isinstance(stop_bps, bool) or not isinstance(stop_bps, int) or stop_bps <= 0 \
                    or str(stop_bps) != key:
                raise AdapterError(f"{fctx}.stop_bps must be the positive integer {key}")
        triggered = _require_bool(f, "triggered", fctx)
        is_control = _require_bool(f, "is_live_control", fctx)
        if is_control:
            controls.append(key)
            if stop_bps != live_stop_bps:
                raise AdapterError(f"{fctx} is the live control but its distance "
                                   f"{stop_bps} != rules.live_stop_bps {live_stop_bps}")
        exit_ms = _require_int(f, "exit_ms", fctx)
        exit_mid = _decimal(f.get("exit_mid_usd"), f"{fctx}.exit_mid_usd")
        adverse = _decimal(f.get("adverse_bps_at_exit"), f"{fctx}.adverse_bps_at_exit")
        reason = _require_str(f, "exit_reason", fctx)
        if reason not in _EXIT_REASONS:
            raise AdapterError(f"{fctx}.exit_reason {reason!r} not in {_EXIT_REASONS}")
        if exit_ms < fill_ms:
            raise AdapterError(f"{fctx}.exit_ms is before the open fill")
        # S29: the recorded facts must agree with the rule they claim to follow.
        recomputed = (open_fill - exit_mid) / open_fill * Decimal(10000) * direction
        if recomputed != adverse:
            raise AdapterError(f"{fctx}.adverse_bps_at_exit {adverse} != recomputed {recomputed}")
        if reason == "stop":
            if not triggered or stop_bps is None or adverse < Decimal(stop_bps) or exit_ms >= gate_ms:
                raise AdapterError(f"{fctx}: a stop exit must be a triggered fork at or beyond "
                                   "its distance before the gate")
        else:
            if triggered or exit_ms < gate_ms:
                raise AdapterError(f"{fctx}: a gate exit is untriggered and at or after the gate")
        gross = (exit_mid - open_fill) * size * direction
        if _decimal(f.get("gross_paper_pnl_usd"), f"{fctx}.gross_paper_pnl_usd") != gross:
            raise AdapterError(f"{fctx}.gross_paper_pnl_usd != recomputed {gross}")
        payload_file = _require_str(f, "payload_file", fctx)
        payload_sha = _require_sha256(f, "payload_sha256", fctx)
        events.append(RightsEvent(
            event_id=fork_event_id(open_intent_id, key),
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=FORK_CLAIMANT,
            claim={
                "mechanism": FORK,
                "fork": key,
                "open_intent_id": open_intent_id,
                "open_fill_event_id": open_fill_event_id,
                "open_capture": open_capture,
                "open_capture_sha256": open_capture_sha,
                "open_fill_price_usd": open_fill,
                "size": size,
                "dir": direction,
                "stop_bps": stop_bps,
                "live_stop_bps": live_stop_bps,
                "is_live_control": is_control,
                "triggered": triggered,
                "exit_reason": reason,
                "exit_ms": exit_ms,
                "exit_mid_usd": exit_mid,
                "adverse_bps_at_exit": adverse,
                "exit_mark_source": exit_source,
                "gross_paper_pnl_usd": gross,
                "fee_model": fee_model,
                "gate_ms": gate_ms,
                "tape_file": tape_file,
                "tape_sha256": tape_sha,
                "tape_rows": tape_rows,
                "tape_null_rows": tape_nulls,
                "payload_file": payload_file,
                "payload_sha256": payload_sha,
                "mode": "PAPER",
            },
            ep_type=EPType.SELF_ASSERTED,
            source_url=source_url,
            observed_date=_utc_date(exit_ms),
            prior_event_refs=(open_fill_event_id,),
        ))
    if len(controls) != 1:
        raise AdapterError(f"exactly one fork must be the live control, got {controls}")
    events.sort(key=lambda e: (e.observed_date, e.event_id))
    return events
