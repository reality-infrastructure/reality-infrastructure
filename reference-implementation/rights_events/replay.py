"""Replay CLI: reconstruct a logged belief and verify byte-identity.

Usage:
    python -m rights_events.replay --run RUN_FILE --subject SUBJECT
        [--question QUESTION] [--belief-index N] [--expected-root HEX]

Procedure (all checks must pass for exit code 0):
1. Rebuild both logs from the run file.  Every event observation is
   re-submitted through the engine, so every signature re-verifies and
   a tampered event entry fails here.
2. Select the belief entry: --belief-index if given, else the latest
   belief-log entry matching (subject, question).
3. Re-fold the belief from the logged events at the belief's recorded
   as_of and event_log_size, and byte-compare the canonical encoding
   against the stored belief-log entry.  IDENTICAL or FAIL.
4. Verify the recorded event_log_root against the rebuilt log, and
   --expected-root against it if given.
5. Verify the Merkle inclusion proof of the belief entry in the belief
   log and of every contributing event in the event log (RFC 9162
   verification, engine code).

Exit codes: 0 all checks passed; 1 byte-identity or proof verification
failed; 2 usage or data errors (unreadable run, unknown subject or
question, bad index or root).

Output is deterministic: no timestamps, sorted mass listing.
"""

from __future__ import annotations

import argparse
import sys

from ri_core.log import leaf_hash, verify_inclusion
from ri_core.serialization import decode, encode

from rights_events.pipeline import PipelineError, RightsPipeline

_DEFAULT_QUESTION = "ownership_shares"


def _select_belief(pipeline: RightsPipeline, subject: str, question: str,
                   belief_index: int | None) -> tuple[int, bytes, dict]:
    """Return (index, entry_bytes, belief_dict) or raise PipelineError."""
    total = len(pipeline.belief_log)
    if belief_index is not None:
        if belief_index < 0 or belief_index >= total:
            raise PipelineError(
                f"--belief-index {belief_index} out of range [0, {total})")
        entry = pipeline.belief_log.entry(belief_index)
        belief = decode(entry)
        if (belief.get("subject") != subject
                or belief.get("question") != question):
            raise PipelineError(
                f"Belief entry {belief_index} is for "
                f"({belief.get('subject')!r}, {belief.get('question')!r}), "
                f"not ({subject!r}, {question!r})")
        return belief_index, entry, belief

    for idx in range(total - 1, -1, -1):
        entry = pipeline.belief_log.entry(idx)
        belief = decode(entry)
        if (isinstance(belief, dict)
                and belief.get("kind") == "rights_belief"
                and belief.get("subject") == subject
                and belief.get("question") == question):
            return idx, entry, belief
    raise PipelineError(
        f"No belief entry for subject {subject!r} question {question!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.replay",
        description="Reconstruct a logged belief object and verify "
                    "byte-identity and inclusion proofs.")
    parser.add_argument("--run", required=True,
                        help="run file written by RightsPipeline.save()")
    parser.add_argument("--subject", required=True,
                        help="subject identifier the belief is about")
    parser.add_argument("--question", default=_DEFAULT_QUESTION,
                        help=f"contested question "
                             f"(default: {_DEFAULT_QUESTION})")
    parser.add_argument("--belief-index", type=int, default=None,
                        help="belief-log index (default: latest match)")
    parser.add_argument("--expected-root", default=None,
                        help="expected event-log root, hex")
    args = parser.parse_args(argv)

    # 1. Rebuild logs; signatures re-verify at intake.
    try:
        pipeline = RightsPipeline.load(args.run)
    except PipelineError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"run file:            {args.run}")
    print(f"event log:           {len(pipeline.event_log)} entries, "
          f"all signatures verified at intake")
    print(f"belief log:          {len(pipeline.belief_log)} entries")

    # 2. Select the stored belief entry.
    try:
        index, stored_entry, belief = _select_belief(
            pipeline, args.subject, args.question, args.belief_index)
    except PipelineError as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"belief entry:        index {index}, subject "
          f"{belief['subject']!r}, question {belief['question']!r}, "
          f"as_of {belief['as_of']}")
    print(f"policy version:      {belief['policy_version']}")
    print()
    print("mass assignments (stored belief):")
    for key in sorted(belief["mass"]):
        label = key if key else "(conflict: empty set)"
        if key == belief["unresolved_set"]:
            label = f"{key}  <- unresolved (ignorance set Omega)"
        print(f"  m({label}) = {belief['mass'][key]}")
    print(f"  unresolved_mass = {belief['unresolved_mass']}")
    print(f"  conflict_mass   = {belief['conflict_mass']}")
    print()

    failed = False

    # 3. Re-fold and byte-compare.
    try:
        refolded = pipeline.fold(
            args.subject, args.question, belief["as_of"],
            at_size=belief["event_log_size"])
        replay_identical = encode(refolded) == stored_entry
    except PipelineError as exc:
        print(f"ERROR: re-fold failed: {exc}")
        return 2
    print(f"byte-identity:       "
          f"{'IDENTICAL' if replay_identical else 'FAIL'} "
          f"(reconstructed belief vs stored belief-log entry)")
    failed = failed or not replay_identical

    # 4. Event-log root checks.
    rebuilt_root = pipeline.event_log.root(belief["event_log_size"])
    root_ok = rebuilt_root == belief["event_log_root"]
    print(f"event log root:      "
          f"{'MATCH' if root_ok else 'FAIL'} "
          f"(recorded {belief['event_log_root'].hex()})")
    failed = failed or not root_ok
    if args.expected_root is not None:
        expected_ok = args.expected_root.lower() == rebuilt_root.hex()
        print(f"--expected-root:     "
              f"{'MATCH' if expected_ok else 'FAIL'}")
        failed = failed or not expected_ok

    # 5. Inclusion proofs.
    proof = pipeline.belief_inclusion_proof(index)
    belief_proof_ok = verify_inclusion(
        leaf_hash(stored_entry), proof.index, proof.tree_size,
        proof.hashes, proof.root_hash)
    print(f"belief inclusion:    "
          f"{'VERIFIED' if belief_proof_ok else 'FAIL'} "
          f"(index {index}, tree size {proof.tree_size})")
    failed = failed or not belief_proof_ok

    events_ok = 0
    for c in belief["contributing_events"]:
        entry = pipeline.event_log.entry(c["log_index"])
        eproof = pipeline.event_log.inclusion_proof(
            c["log_index"], belief["event_log_size"])
        ok = (verify_inclusion(
                leaf_hash(entry), eproof.index, eproof.tree_size,
                eproof.hashes, eproof.root_hash)
              and eproof.root_hash == belief["event_log_root"])
        if ok:
            events_ok += 1
        else:
            print(f"event inclusion:     FAIL for {c['event_id']!r}")
            failed = True
    total_events = len(belief["contributing_events"])
    print(f"event inclusions:    {events_ok}/{total_events} verified "
          f"against the recorded root")

    print()
    print(f"REPLAY: {'OK' if not failed else 'FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
