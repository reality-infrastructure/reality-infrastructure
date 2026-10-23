"""Agent-record evidence run — ingest, prove, save, re-verify.

The operator's own intent-and-outcome record on GDEX (Day 1: PAPER). Takes the
adapter's events (adapters/agent_record.py), submits them through the unmodified
engine (EP typing, HMAC signatures, Merkle event log), proves each event's RFC
9162 inclusion against the event-log root, writes a run file, and reloads it so
every signature re-verifies — a single altered byte makes the reload fail. No
belief is folded; no trade is executed.

Usage:
    python -m rights_events.agent_record [--capture CAPTURE] [--out RUN_FILE]
    python -m rights_events.agent_record --verify --run RUN_FILE

The second form is the stranger's check: rebuild the logs from the run file
(signatures re-verify at intake) and verify every event's inclusion proof
against the rebuilt root. Exit 0 all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rights_events.adapters.agent_record import parse_events
from rights_events.pipeline import RightsPipeline
from rights_events.schema import EventType
from rights_events.trader_record import _all_inclusions_verify, verify_run

_FIXTURE = (Path(__file__).parent / "fixtures" / "agent_record"
            / "capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json")


def ingest_capture(document_text: str) -> tuple[RightsPipeline, list, dict]:
    """Parse and ingest a capture. Returns (pipeline, events, indices)."""
    events = parse_events(document_text)
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)
    return pipeline, events, indices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.agent_record",
        description="Agent-record evidence run: ingest a capture, prove "
                    "inclusion, save, and re-verify. No fold; no trade.")
    parser.add_argument("--out", default="agent_record_run.ri",
                        help="run file to write (default: agent_record_run.ri)")
    parser.add_argument("--verify", action="store_true",
                        help="verify an existing run file instead of building one")
    parser.add_argument("--run", default=None,
                        help="run file to verify (with --verify)")
    parser.add_argument("--capture", default=None,
                        help="capture document to ingest (default: the pinned "
                             "PAPER capture)")
    args = parser.parse_args(argv)

    if args.verify:
        if not args.run:
            print("ERROR: --verify requires --run RUN_FILE")
            return 2
        ok, report = verify_run(args.run)
        print(f"VERIFY {args.run}: {report}")
        print(f"RESULT: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1

    capture_path = Path(args.capture) if args.capture else _FIXTURE
    capture_text = capture_path.read_text(encoding="utf-8")
    doc = json.loads(capture_text)

    print("=" * 70)
    print("AGENT-RECORD EVIDENCE RUN -- END TO END")
    print(f"{doc.get('mode')} capture: {capture_path.name}")
    print("The operator's own intent (GDEX preview, nothing submitted) beside")
    print("the outcome it produced; see the MANIFEST beside the capture.")
    print("No belief is folded. No trade is executed.")
    print("=" * 70)
    print()

    pipeline, events, indices = ingest_capture(capture_text)
    subject = events[0].subject_ids[0]

    print(f"Subject: {subject}")
    print("Events submitted through the engine (EP-typed, signed, logged):")
    for event in events:
        print(f"  [{indices[event.event_id]}] {event.event_id}")
        print(f"      {event.event_type.value}, {event.ep_type.value}, "
              f"observed {event.observed_date}, claimant {event.claimant}")
    print()

    root = pipeline.event_log.root(len(pipeline.event_log))
    run_bytes = pipeline.save(args.out)

    intent = [e for e in events if e.event_id.startswith("agent_record:intent:")]
    fills = [e for e in events if e.event_id.startswith("agent_record:fill:")]
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    max_bps = json.loads(capture_text, parse_float=str)["tolerance"][
        "max_quote_to_fill_bps"]
    inclusions_ok = _all_inclusions_verify(pipeline)
    reload_ok, reload_report = verify_run(args.out)
    reloaded_root_ok = reload_ok and reload_report.endswith(root.hex())

    checks = [
        (f"C1 adapter produced {len(events)} events: {len(intent)} intent, "
         f"{len(fills)} fill, {len(disputes)} dispute (tolerance {max_bps} bps)",
         len(intent) == 1 and len(fills) == 1 and len(disputes) in (0, 1)),
        (f"C2 all {len(pipeline.event_log)} inclusion proofs verify against "
         f"the root", inclusions_ok),
        ("C3 saved run reloads; every signature re-verifies; root unchanged",
         reloaded_root_ok),
    ]

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
