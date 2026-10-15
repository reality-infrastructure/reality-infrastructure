"""Trader-record evidence run (PATH A) — ingest, prove, save, re-verify.

SYNTHETIC: runs the labeled-synthetic capture fixture
(fixtures/trader_record/capture_SYNTHETIC.json + MANIFEST.json). No real
wallet, venue, trader, or transaction appears.

This is the gdex.pro copy-trade use case on the UNMODIFIED engine, minus the
fold that the Gate-0 finding put out of scope (CONTRACT.md). It takes the
adapter's events, submits them through the engine (EP typing, HMAC signatures,
Merkle event log), proves each event's RFC 9162 inclusion against the event-log
root, writes a run file, and reloads it so every signature re-verifies — a
single altered byte makes the reload fail. No belief is folded.

Usage:
    python -m rights_events.trader_record [--out RUN_FILE]
    python -m rights_events.trader_record --verify --run RUN_FILE

The second form is the stranger's check: rebuild the logs from the run file
(signatures re-verify at intake) and verify every event's inclusion proof
against the rebuilt root. Exit 0 all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ri_core.log import leaf_hash, verify_inclusion

from rights_events.adapters.trader_record import parse_events
from rights_events.pipeline import PipelineError, RightsPipeline

_FIXTURE = (Path(__file__).parent / "fixtures" / "trader_record"
            / "capture_SYNTHETIC.json")


def ingest_capture(document_text: str) -> tuple[RightsPipeline, list, dict]:
    """Parse and ingest a capture. Returns (pipeline, events, indices)."""
    events = parse_events(document_text)
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)
    return pipeline, events, indices


def _all_inclusions_verify(pipeline: RightsPipeline) -> bool:
    """Every event-log entry has a valid inclusion proof against the root."""
    size = len(pipeline.event_log)
    root = pipeline.event_log.root(size)
    for idx in range(size):
        entry = pipeline.event_log.entry(idx)
        proof = pipeline.event_log.inclusion_proof(idx, size)
        if not verify_inclusion(leaf_hash(entry), proof.index, proof.tree_size,
                                proof.hashes, proof.root_hash):
            return False
        if proof.root_hash != root:
            return False
    return True


def verify_run(run_path: str | Path) -> tuple[bool, str]:
    """Stranger's check: reload and re-verify a run file. (ok, one-line report)."""
    try:
        pipeline = RightsPipeline.load(run_path)
    except PipelineError as exc:
        return False, f"reload FAILED (tamper or corruption): {exc}"
    if not _all_inclusions_verify(pipeline):
        return False, "inclusion proofs FAILED against the rebuilt root"
    n = len(pipeline.event_log)
    root = pipeline.event_log.root(n).hex()
    return True, (f"reloaded {n} events, all signatures re-verified, all "
                  f"inclusion proofs verified; event-log root {root}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.trader_record",
        description="Trader-record evidence run (PATH A): ingest a capture, "
                    "prove inclusion, save, and re-verify. No belief fold.")
    parser.add_argument("--out", default="trader_record_run.ri",
                        help="run file to write (default: trader_record_run.ri)")
    parser.add_argument("--verify", action="store_true",
                        help="verify an existing run file instead of building one")
    parser.add_argument("--run", default=None,
                        help="run file to verify (with --verify)")
    parser.add_argument("--capture", default=None,
                        help="capture document to ingest (default: the pinned "
                             "SYNTHETIC fixture). A REAL capture carries live "
                             "source_urls + observed_dates per the MANIFEST.")
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
    is_synthetic = capture_path == _FIXTURE

    print("=" * 70)
    print("TRADER-RECORD EVIDENCE RUN (PATH A) -- END TO END")
    if is_synthetic:
        print("SYNTHETIC fixture: a gdex.pro leaderboard claim beside on-chain")
        print("fills; no real wallet, venue, trader, or transaction.")
    else:
        print(f"REAL capture: {capture_path.name}")
        print("Live HyperLiquid leaderboard claim beside the same address's")
        print("on-chain fills (realized closedPnl - fee); see MANIFEST.")
    print("No belief is folded (Gate-0 finding; see CONTRACT.md).")
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

    dispute = [e for e in events if e.event_type.value == "dispute"]
    inclusions_ok = _all_inclusions_verify(pipeline)
    reload_ok, reload_report = verify_run(args.out)
    reloaded_root_ok = reload_ok and reload_report.endswith(root.hex())

    checks = [
        (f"C1 adapter produced {len(events)} events incl. "
         f"{len(dispute)} dispute (mismatch recorded)", len(dispute) == 1),
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
    print(f"  python -m rights_events.trader_record --verify --run {args.out}")
    print()
    print(f"TRADER-RECORD RUN: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
