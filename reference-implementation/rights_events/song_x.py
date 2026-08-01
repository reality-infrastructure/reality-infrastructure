"""End-to-end Song X acceptance case (Contract 1, P5).

SYNTHETIC: the Song X conflict is a synthetic fixture modeled on the
standard PRO split-conflict pattern (fixtures/pro_conflict/
song_x_SYNTHETIC.json and its MANIFEST.json).  No real work, writer,
society, or registration appears anywhere in this case.

Usage:
    python -m rights_events.song_x [--out RUN_FILE]

Runs the full layer end to end: adapter (d) parses the fixture into
four events (two conflicting share registrations, the dispute record,
B's revocation); the pipeline submits them through the engine (EP
typing, signatures, Merkle event log); two belief objects are folded
and committed to the belief log — pre-revocation (as_of 2026-06-09)
and post-revocation (as_of 2026-07-01); the run file is written; and
the acceptance properties are checked in-process:

  A1. the pre-revocation frame carries both hypotheses (A-majority
      60/40, B-equal 50/50) and the ignorance set is named;
  A2. m(unresolved) exceeds the mass on every singleton hypothesis;
  A3. every contributing event has a verifiable inclusion proof
      against the recorded event-log root;
  A4. the revocation changes the fused belief (pre != post masses).

Exit 0 with all checks passed, 1 otherwise.  Verify the written run
file independently with:

    python -m rights_events.replay --run RUN_FILE --subject work:song-x

Deterministic: same fixture in, byte-identical run file out, on any
machine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ri_core.log import leaf_hash, verify_inclusion

from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.pipeline import RightsPipeline
from rights_events.policy import ltime_for

SUBJECT = "work:song-x"
QUESTION = "ownership_shares"
HYP_A_MAJORITY = "shares:writer-a=60;writer-b=40"
HYP_B_EQUAL = "shares:writer-a=50;writer-b=50"
PRE_AS_OF = ltime_for("2026-06-09")     # after both registrations
POST_AS_OF = ltime_for("2026-07-01")    # after B's revocation

_FIXTURE = (Path(__file__).parent / "fixtures" / "pro_conflict"
            / "song_x_SYNTHETIC.json")


def _print_masses(belief: dict) -> None:
    labels = {
        HYP_A_MAJORITY: "A-majority (60/40)",
        HYP_B_EQUAL: "B-equal (50/50)",
        "": "conflict (empty set)",
        belief["unresolved_set"]: "unresolved (ignorance set Omega)",
    }
    for key in sorted(belief["mass"]):
        label = labels.get(key, key)
        print(f"    m[{label}] = {belief['mass'][key]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.song_x",
        description="Run the SYNTHETIC Song X split-conflict case end "
                    "to end and write its run file.")
    parser.add_argument("--out", default="song_x_run.ri",
                        help="run file to write (default: song_x_run.ri)")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("SONG X SPLIT-SHEET CONFLICT -- END TO END (Contract 1)")
    print("SYNTHETIC fixture: modeled on the standard PRO split-conflict")
    print("pattern; no real work, writer, society, or registration.")
    print("=" * 70)
    print()

    events = parse_registrations(_FIXTURE.read_text(encoding="utf-8"))
    pipeline = RightsPipeline()
    indices = pipeline.ingest(events)

    print("Events submitted through the engine (EP-typed, signed, logged):")
    for event in events:
        print(f"  [{indices[event.event_id]}] {event.event_id}")
        print(f"      {event.event_type.value}, {event.ep_type.value}, "
              f"observed {event.observed_date}, claimant {event.claimant}")
    print()

    pre, pre_idx = pipeline.commit(SUBJECT, QUESTION, PRE_AS_OF)
    post, post_idx = pipeline.commit(SUBJECT, QUESTION, POST_AS_OF)
    run_bytes = pipeline.save(args.out)

    print(f"Pre-revocation belief (as_of {PRE_AS_OF}, belief-log entry "
          f"{pre_idx}):")
    _print_masses(pre)
    print()
    print(f"Post-revocation belief (as_of {POST_AS_OF}, belief-log entry "
          f"{post_idx}):")
    _print_masses(post)
    print()

    checks: list[tuple[str, bool]] = []

    frame_ok = sorted([HYP_A_MAJORITY, HYP_B_EQUAL]) == pre["frame"]
    omega_named = (pre["unresolved_set"] == ",".join(sorted(pre["frame"]))
                   and pre["unresolved_mass"] == pre["mass"][
                       pre["unresolved_set"]])
    checks.append(("A1 frame carries A-majority and B-equal; "
                   "ignorance set named", frame_ok and omega_named))

    dominance = all(
        pre["unresolved_mass"] > pre["mass"][hyp] for hyp in pre["frame"])
    checks.append(("A2 m(unresolved) exceeds every singleton "
                   "(pre-revocation)", dominance))

    proofs_ok = True
    for c in post["contributing_events"]:
        entry = pipeline.event_log.entry(c["log_index"])
        proof = pipeline.event_log.inclusion_proof(
            c["log_index"], post["event_log_size"])
        proofs_ok = proofs_ok and verify_inclusion(
            leaf_hash(entry), proof.index, proof.tree_size, proof.hashes,
            proof.root_hash) and proof.root_hash == post["event_log_root"]
    checks.append(
        (f"A3 inclusion proofs verify for all "
         f"{len(post['contributing_events'])} contributing events",
         proofs_ok))

    checks.append(("A4 revocation changes the fused belief",
                   pre["mass"] != post["mass"]))

    print("Acceptance checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        all_ok = all_ok and ok
    print()
    print(f"Event log root: {pipeline.event_log.root().hex()}")
    print(f"Run file:       {args.out} ({len(run_bytes)} bytes)")
    print()
    print("Verify independently (byte-identity + inclusion proofs):")
    print(f"  python -m rights_events.replay --run {args.out} "
          f"--subject {SUBJECT}")
    print()
    print(f"SONG X END-TO-END: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
