"""Parcel runner: real Cook County records end to end (Contract 2, P3).

Usage:
    python -m rights_events.parcels [--out RUN_FILE]

Runs the second domain through the layer Contract 1 shipped, unchanged:
adapters/cook_parcels.py parses the checked-in real fixtures
(fixtures/parcels/, provenance in MANIFEST.json); the pipeline submits
every event through the engine (EP typing, signatures, Merkle event
log); one belief object per parcel is folded and committed for the
ownership_shares question; the run file is written in the same format
song_x writes, consumable by the existing replay CLI with no new flags.

as_of is the maximum event ltime in the data — derived from the
records, never from a clock, so two runs are byte-identical.

In-process checks (exit 0 only if all pass):
  B1. at least two parcels render competing singleton hypotheses
      (two or more entities with positive mass);
  B2. every belief object names the ignorance set and reports
      conflict mass explicitly;
  B3. every contributing event has a verifiable inclusion proof
      against the recorded event-log root, and its logged payload
      carries a resolving source_url and observed_date.

Every contest printed here is a statement that RECORDS DISAGREE and
requires verification against the underlying instruments; nothing in
this output characterizes any person or entity (privacy ruling R1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ri_core.log import leaf_hash, verify_inclusion
from ri_core.serialization import decode

from rights_events.adapters.cook_parcels import parse_all
from rights_events.pipeline import RightsPipeline
from rights_events.policy import ltime_for

QUESTION = "ownership_shares"
_FIXTURES = Path(__file__).parent / "fixtures" / "parcels"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.parcels",
        description="Run the real Cook County parcel records end to "
                    "end and write a run file.")
    parser.add_argument("--out", default="parcels_run.ri",
                        help="run file to write (default: parcels_run.ri)")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("COOK COUNTY PARCELS -- SECOND DOMAIN, SAME LAYER (Contract 2)")
    print("Real public records; names verbatim as recorded; every")
    print("contest below means RECORDS DISAGREE, nothing more.")
    print("=" * 70)
    print()

    events = parse_all(_read("deeds.json"), _read("assessor_owners.json"),
                       _read("tax_sale_forfeitures.json"))
    pipeline = RightsPipeline()
    pipeline.ingest(events)
    as_of = max(ltime_for(e.observed_date) for e in events)

    pins = sorted({e.subject_ids[0].removeprefix("parcel:")
                   for e in events})
    print(f"{len(events)} events for {len(pins)} parcels submitted "
          f"through the engine; as_of {as_of} (max record ltime).")
    print()

    beliefs = {}
    for pin in pins:
        belief, index = pipeline.commit(f"parcel:{pin}", QUESTION, as_of)
        beliefs[pin] = (belief, index)

    run_bytes = pipeline.save(args.out)

    competing = 0
    for pin in pins:
        belief, index = beliefs[pin]
        singletons = [(hyp, belief["mass"][hyp]) for hyp in belief["frame"]]
        positive = [s for s in singletons if s[1] > 0]
        if len(positive) >= 2:
            competing += 1
        print(f"parcel:{pin}  (belief-log entry {index}, frame "
              f"{len(belief['frame'])})")
        for hyp, mass in sorted(singletons):
            print(f"    m[{hyp}] = {mass}")
        print(f"    conflict (empty set) = {belief['conflict_mass']}")
        print(f"    unresolved (Omega)   = {belief['unresolved_mass']}")
        print()

    checks = []
    checks.append((f"B1 competing singleton hypotheses on {competing} "
                   f"parcels (need >= 2)", competing >= 2))

    named = all(
        b["unresolved_set"] == ",".join(sorted(b["frame"]))
        and b["conflict_mass"] == b["mass"][""]
        for b, _ in beliefs.values())
    checks.append(("B2 every belief names Omega and reports conflict "
                   "explicitly", named))

    proofs_ok = True
    provenance_ok = True
    for pin in pins:
        belief, _ = beliefs[pin]
        for c in belief["contributing_events"]:
            entry = pipeline.event_log.entry(c["log_index"])
            proof = pipeline.event_log.inclusion_proof(
                c["log_index"], belief["event_log_size"])
            proofs_ok = proofs_ok and verify_inclusion(
                leaf_hash(entry), proof.index, proof.tree_size,
                proof.hashes, proof.root_hash
            ) and proof.root_hash == belief["event_log_root"]
            obs = decode(entry)
            event = obs["payload"]["event"]
            provenance_ok = provenance_ok and (
                event["source_url"].startswith("https://")
                and len(event["observed_date"]) == 10)
    checks.append(("B3 inclusion proofs verify and every contributing "
                   "event carries source_url + observed_date",
                   proofs_ok and provenance_ok))

    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    print()
    print(f"Event log root: {pipeline.event_log.root().hex()}")
    print(f"Run file:       {args.out} ({len(run_bytes)} bytes)")
    print()
    print("Verify any parcel with the unchanged replay CLI, e.g.:")
    print(f"  python -m rights_events.replay --run {args.out} "
          f"--subject parcel:{pins[0]}")
    print()
    print(f"PARCELS END-TO-END: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
