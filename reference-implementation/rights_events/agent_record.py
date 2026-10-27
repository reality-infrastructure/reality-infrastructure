"""Agent-record evidence run — ingest, prove, save, re-verify.

The operator's own intent-and-outcome record on GDEX (PAPER, and LIVE under
PREREG A2). Takes the adapter's events (adapters/agent_record.py) from the
named captures, submits them through the unmodified engine (EP typing, HMAC
signatures, Merkle event log) as ONE log, proves each event's RFC 9162
inclusion against the event-log root, writes a run file, and reloads it so
every signature re-verifies — a single altered byte makes the reload fail. No
belief is folded; no trade is executed.

Usage:
    python -m rights_events.agent_record [--capture CAPTURE ...] [--out RUN_FILE]
    python -m rights_events.agent_record --verify --run RUN_FILE

With no --capture, every pinned `capture_PAPER_*.json` in fixtures/agent_record
is ingested in sorted name order (an open leg sorts before its `_close` leg).
A LIVE run names its captures with --capture explicitly and is written beside
the PAPER run files (A2 R19); PAPER and LIVE captures are never mixed in one
run — they are different positions — and the runner refuses the mix.
The second form is the stranger's check: rebuild the logs from the run file
(signatures re-verify at intake) and verify every event's inclusion proof
against the rebuilt root. Exit 0 all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rights_events.adapters.agent_fork import CAPTURE_KIND as FORK_KIND
from rights_events.adapters.agent_fork import parse_events as parse_fork_events
from rights_events.adapters.agent_record import parse_events
from rights_events.adapters.common import AdapterError
from rights_events.pipeline import RightsPipeline
from rights_events.schema import EPType, EventType
from rights_events.trader_record import _all_inclusions_verify, verify_run

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
_FIXTURE = _FIXTURES / "capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json"


def pinned_captures() -> list[Path]:
    """Every pinned PAPER capture, sorted by name (open before `_close`)."""
    return sorted(_FIXTURES.glob("capture_PAPER_*.json"))


def _is_fork(document_text: str) -> bool:
    try:
        return json.loads(document_text).get("kind") == FORK_KIND
    except (json.JSONDecodeError, AttributeError):
        return False


def ingest_captures(document_texts: list[str]) -> tuple[RightsPipeline, list, dict]:
    """Parse every capture, ingest all events into ONE log (PREREG A1 R9)."""
    events: list = []
    for text in document_texts:
        # A5 R30: a fork capture (the paper stop forks of ONE live position) goes
        # through its own pure adapter into the same log; everything else is an
        # agent_record_capture.
        events.extend(parse_fork_events(text) if _is_fork(text) else parse_events(text))
    modes = {e.claim["mode"] for e in events
             if e.event_id.startswith("agent_record:intent:")}
    if len(modes) > 1:
        # A2 R19: different positions, different logs.
        raise AdapterError(f"PAPER and LIVE captures are never mixed in one run "
                           f"(PREREG A2 R19); got modes {sorted(modes)}")
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)
    return pipeline, events, indices


def ingest_capture(document_text: str) -> tuple[RightsPipeline, list, dict]:
    """Parse and ingest one capture. Returns (pipeline, events, indices)."""
    return ingest_captures([document_text])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.agent_record",
        description="Agent-record evidence run: ingest the pinned captures, "
                    "prove inclusion, save, and re-verify. No fold; no trade.")
    parser.add_argument("--out", default="agent_record_run.ri",
                        help="run file to write (default: agent_record_run.ri)")
    parser.add_argument("--verify", action="store_true",
                        help="verify an existing run file instead of building one")
    parser.add_argument("--run", default=None,
                        help="run file to verify (with --verify)")
    parser.add_argument("--capture", action="append", default=None,
                        help="capture document(s) to ingest (default: every "
                             "pinned PAPER capture, sorted)")
    args = parser.parse_args(argv)

    if args.verify:
        if not args.run:
            print("ERROR: --verify requires --run RUN_FILE")
            return 2
        ok, report = verify_run(args.run)
        print(f"VERIFY {args.run}: {report}")
        print(f"RESULT: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1

    paths = [Path(p) for p in args.capture] if args.capture else pinned_captures()
    texts = [p.read_text(encoding="utf-8") for p in paths]
    docs = [json.loads(t, parse_float=str) for t in texts]

    print("=" * 70)
    print("AGENT-RECORD EVIDENCE RUN -- END TO END")
    for p, d in zip(paths, docs):
        if d.get("kind") == FORK_KIND:
            print(f"PAPER fork capture (stop forks of the live position): {p.name}")
            continue
        leg = "close" if "closes" in d else "open"
        print(f"{d.get('mode')} capture ({leg} leg): {p.name}")
    print("The operator's own intent beside the outcome it produced; see the")
    print("MANIFEST beside each capture. No belief is folded. No trade is executed.")
    print("=" * 70)
    print()

    pipeline, events, indices = ingest_captures(texts)
    subject = events[0].subject_ids[0]

    print(f"Subject: {subject}")
    print("Events submitted through the engine (EP-typed, signed, logged):")
    for event in sorted(events, key=lambda e: indices[e.event_id]):
        print(f"  [{indices[event.event_id]}] {event.event_id}")
        print(f"      {event.event_type.value}, {event.ep_type.value}, "
              f"observed {event.observed_date}, claimant {event.claimant}")
    print()

    root = pipeline.event_log.root(len(pipeline.event_log))
    run_bytes = pipeline.save(args.out)

    intents = [e for e in events if e.event_id.startswith("agent_record:intent:")]
    fills = [e for e in events if e.event_id.startswith("agent_record:fill:")]
    realized = [e for e in events if e.event_id.startswith("agent_record:realized:")]
    gaps = [e for e in events if e.event_id.startswith("agent_record:gap:")]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    legs = [d for d in docs if d.get("kind") != FORK_KIND]
    n_live = sum(1 for d in legs if d.get("mode") == "LIVE")
    expected_fills = sum(2 if d.get("mode") == "LIVE" else 1 for d in legs)
    forks = [e for e in events if e.event_id.startswith("agent_record:fork:")]
    n_fork_docs = len(docs) - len(legs)
    logged = set(indices)
    refs_ok = all(ref in logged for e in events for ref in e.prior_event_refs)
    inclusions_ok = _all_inclusions_verify(pipeline)
    reload_ok, reload_report = verify_run(args.out)
    reloaded_root_ok = reload_ok and reload_report.endswith(root.hex())

    c1_label = (f"C1 adapter produced {len(events)} events: {len(intents)} intent, "
                f"{len(fills)} fill, {len(realized)} realized, {len(disputes)} dispute")
    if n_live:
        c1_label += f", {len(gaps)} gap, {len(signed)} cryptographically_signed"
    if n_fork_docs:
        c1_label += f", {len(forks)} paper stop fork"
    checks = [
        (c1_label,
         len(intents) == len(legs) and len(fills) == expected_fills
         and (n_fork_docs == 0 or (len(forks) >= 2 and all(
             e.ep_type is EPType.SELF_ASSERTED for e in forks)))
         and len(gaps) == n_live and len(signed) == n_live
         and len(realized) <= len(intents)),
        (f"C2 all {len(pipeline.event_log)} inclusion proofs verify against "
         f"the root", inclusions_ok),
        ("C3 saved run reloads; every signature re-verifies; root unchanged",
         reloaded_root_ok),
        ("C4 every prior_event_ref resolves inside this run's own log", refs_ok),
    ]
    for e in gaps:
        c = e.claim
        print(f"Sim-to-real gap ({c['live_fill_event_id'].split(':')[3]}, "
              f"{e.event_id.rsplit(':', 1)[1]} leg): {c['gap_bps']} bps "
              f"(live {c['live_price_usd']} vs paper {c['paper_price_usd']}, "
              f"cost sign {c['cost_sign']:+d}, shadow lag {c['shadow_lag_ms']} ms, "
              f"live fee {c['live_fee_usd']} USD)")
    for e in sorted(forks, key=lambda e: (e.claim["stop_bps"] is None, e.claim["stop_bps"] or 0)):
        c = e.claim
        print(f"Paper stop fork {c['fork']:>9}{' (live control)' if c['is_live_control'] else ''}: "
              f"{'triggered' if c['triggered'] else 'untriggered'}, exit by {c['exit_reason']} at "
              f"mid {c['exit_mid_usd']} (adverse {c['adverse_bps_at_exit']} bps), gross "
              f"{c['gross_paper_pnl_usd']} USD"
              + (" -- GATE LATE, unusable for R29"
                 if c.get("gate_late") and c["exit_reason"] == "gate" else ""))
    for e in realized:
        label = "live" if e.claim["mode"] == "LIVE" else "paper"
        print(f"Realized {label} PnL ({e.claim['open_intent_id']}): "
              f"{e.claim['realized_pnl_usd']} USD, {e.claim['bucket']} "
              f"(open {e.claim['open_price_usd']}, close {e.claim['close_price_usd']}, "
              f"size {e.claim['size']}, fees {e.claim['fees_usd']}"
              + (f", venue closedPnl {e.claim['venue_closed_pnl_usd']}"
                 if label == "live" else "") + ")")
    if realized or gaps or forks:
        print()

    print(f"Event log root: {root.hex()}")
    print(f"Run file:       {args.out} ({len(run_bytes)} bytes)")
    print()
    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    print()
    print("Verify independently (reload + re-verify signatures + inclusions):")
    print(f"  python -m rights_events.agent_record --verify --run {args.out}")
    print()
    print(f"AGENT-RECORD RUN: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
