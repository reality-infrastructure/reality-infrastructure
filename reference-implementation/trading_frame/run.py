"""net_pnl_bucket belief run (PATH B) — ingest, fold, log, save, re-verify.

Built directly on ri_core (the same move rights_events.pipeline made), this
ingests a trader_record capture's events as signed observations into a Merkle
evidence log, folds them into a net_pnl_bucket belief (trading_frame.fold), and
appends that belief to a belief log. The run file bundles both logs.

The verifier is the stranger's check: it reloads the run (signatures re-verify
at intake, so a tampered fill fails), re-verifies every inclusion proof, and
RE-FOLDS the reloaded events — proving the conflict mass is a reproducible
function of the signed inputs, not a stored constant.

Usage:
    python -m trading_frame.run [--capture CAPTURE] [--out RUN_FILE]
    python -m trading_frame.run --verify --run RUN_FILE
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog, leaf_hash, verify_inclusion
from ri_core.project import submit
from ri_core.provenance import ProvenanceGraph
from ri_core.serialization import decode, encode

from rights_events.adapters.trader_record import parse_events
from rights_events.policy import ltime_for, uncertainty_type
from rights_events.schema import RightsEvent

from trading_frame.fold import QUESTION, fold_net_pnl_bucket

_ANCHOR_ID = "trading-frame"
_ANCHOR_SEED = b"trading-frame-domain-v1"
_RUN_KIND = "trading_frame_run"
_RECORD_LABEL = "recorded"

_SYNTHETIC = (Path(__file__).resolve().parent.parent / "rights_events"
              / "fixtures" / "trader_record" / "capture_SYNTHETIC.json")


class RunError(Exception):
    """Raised on malformed run files or intake failure on load."""


class TradingFrameRun:
    """One signed event log + one belief log, bundled to a canonical run file."""

    def __init__(self) -> None:
        self.authority = LocalAuthority(anchor_id=_ANCHOR_ID, seed=_ANCHOR_SEED)
        self.event_log = EvidenceLog()
        self.belief_log = EvidenceLog()
        self.graph = ProvenanceGraph()
        self._issued: set[str] = set()

    def _identity_for(self, claimant: str) -> Identity:
        if claimant not in self._issued:
            self.authority.issue_identity(claimant)
            self._issued.add(claimant)
        return Identity(identity_id=claimant, anchor_id=_ANCHOR_ID,
                        name=claimant)

    def _observation(self, event: RightsEvent) -> dict:
        subject = event.subject_ids[0]
        unsigned = {
            "kind": "observation",
            "id": event.event_id,
            "source_id": event.claimant,
            "proposition": f"{subject}|{QUESTION}",
            "payload": {
                "frame": [_RECORD_LABEL],
                "mass": {_RECORD_LABEL: Decimal(1)},
                "uncertaintyType": uncertainty_type(event.ep_type),
                "event": event.to_dict(),
                "question": QUESTION,
                "hypothesis": None,
            },
            "ltime": ltime_for(event.observed_date),
        }
        identity = self._identity_for(event.claimant)
        sig = self.authority.sign(identity, encode(unsigned))
        obs = dict(unsigned)
        obs["sig"] = sig
        return obs

    def ingest(self, events: list[RightsEvent]) -> None:
        ordered = sorted(
            events, key=lambda e: (ltime_for(e.observed_date), e.event_id))
        for event in ordered:
            self._identity_for(event.claimant)
            submit(self._observation(event), self.event_log, self.graph,
                   self.authority)

    def _events_from_log(self) -> list[RightsEvent]:
        events = []
        for idx in range(len(self.event_log)):
            obs = decode(self.event_log.entry(idx))
            events.append(RightsEvent.from_dict(obs["payload"]["event"]))
        return events

    def build_belief(self) -> dict:
        """Fold the ingested events and append the belief to the belief log."""
        size = len(self.event_log)
        belief = fold_net_pnl_bucket(self._events_from_log())
        belief["event_log_size"] = size
        belief["event_log_root"] = self.event_log.root(size)
        self.belief_log.append(belief)
        return belief

    def all_inclusions_verify(self) -> bool:
        size = len(self.event_log)
        root = self.event_log.root(size)
        for idx in range(size):
            entry = self.event_log.entry(idx)
            proof = self.event_log.inclusion_proof(idx, size)
            if not verify_inclusion(leaf_hash(entry), proof.index,
                                    proof.tree_size, proof.hashes,
                                    proof.root_hash):
                return False
            if proof.root_hash != root:
                return False
        return True

    def save(self, run_path: str | Path) -> bytes:
        run = {
            "kind": _RUN_KIND,
            "anchor_id": _ANCHOR_ID,
            "event_log": {"kind": "log_export",
                          "entries": [self.event_log.entry(i)
                                      for i in range(len(self.event_log))]},
            "belief_log": {"kind": "log_export",
                           "entries": [self.belief_log.entry(i)
                                       for i in range(len(self.belief_log))]},
        }
        data = encode(run)
        Path(run_path).write_bytes(data)
        return data

    @staticmethod
    def load(run_path: str | Path) -> "TradingFrameRun":
        try:
            run = decode(Path(run_path).read_bytes())
        except Exception as exc:
            raise RunError(f"Unreadable run file: {exc}") from exc
        if not isinstance(run, dict) or run.get("kind") != _RUN_KIND:
            raise RunError(f"Run file kind must be {_RUN_KIND!r}")
        rebuilt = TradingFrameRun()
        for i, entry in enumerate(run["event_log"]["entries"]):
            try:
                obs = decode(entry)
                event = RightsEvent.from_dict(obs["payload"]["event"])
                rebuilt._identity_for(event.claimant)
                submit(obs, rebuilt.event_log, rebuilt.graph, rebuilt.authority)
            except Exception as exc:
                raise RunError(
                    f"Event entry {i} failed intake on load: {exc}") from exc
            if rebuilt.event_log.entry(i) != entry:
                raise RunError(
                    f"Event entry {i} did not round-trip byte-identically")
        for i, entry in enumerate(run["belief_log"]["entries"]):
            rebuilt.belief_log.append(decode(entry))
        return rebuilt


def verify_run(run_path: str | Path) -> tuple[bool, str]:
    """Reload, re-verify signatures + inclusions, and re-fold byte-for-byte."""
    try:
        run = TradingFrameRun.load(run_path)
    except RunError as exc:
        return False, f"reload FAILED (tamper or corruption): {exc}"
    if not run.all_inclusions_verify():
        return False, "inclusion proofs FAILED against the rebuilt root"
    if len(run.belief_log) != 1:
        return False, f"expected one logged belief, found {len(run.belief_log)}"
    stored = run.belief_log.entry(0)
    size = len(run.event_log)
    refold = fold_net_pnl_bucket(run._events_from_log())
    refold["event_log_size"] = size
    refold["event_log_root"] = run.event_log.root(size)
    if encode(refold) != stored:
        return False, "re-fold did NOT reproduce the logged belief byte-for-byte"
    belief = decode(stored)
    return True, (
        f"reloaded {size} events, all signatures re-verified, all inclusion "
        f"proofs verified; belief re-folded byte-identically; conflict_mass "
        f"{belief['conflict_mass']}, root {run.event_log.root(size).hex()}")


def run_capture(capture_text: str) -> tuple[TradingFrameRun, dict]:
    run = TradingFrameRun()
    run.ingest(parse_events(capture_text))
    belief = run.build_belief()
    return run, belief


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m trading_frame.run",
        description="net_pnl_bucket conflict-mass belief run (PATH B): ingest a "
                    "capture, fold, log, save, and re-verify by re-folding.")
    parser.add_argument("--out", default="trading_frame_run.ri")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--run", default=None)
    parser.add_argument("--capture", default=None,
                        help="capture document (default: SYNTHETIC fixture)")
    args = parser.parse_args(argv)

    if args.verify:
        if not args.run:
            print("ERROR: --verify requires --run RUN_FILE")
            return 2
        ok, report = verify_run(args.run)
        print(f"VERIFY {args.run}: {report}")
        print(f"RESULT: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1

    capture_path = Path(args.capture) if args.capture else _SYNTHETIC
    run, belief = run_capture(capture_path.read_text(encoding="utf-8"))
    run.save(args.out)

    print("=" * 70)
    print("NET_PNL_BUCKET CONFLICT-MASS FOLD (PATH B) -- END TO END")
    print(f"Capture: {capture_path.name}")
    print("The fold the frozen rights_events.pipeline declined (Gate-0).")
    print("=" * 70)
    print()
    print(f"Subject:          {belief['subject']}")
    print(f"Frame:            {belief['frame']}")
    print(f"Displayed bucket: {belief['displayed_bucket']} "
          f"(self_asserted 0.30) -> mass {belief['displayed_mass']}")
    print(f"Chain bucket:     {belief['chain_bucket']} "
          f"(cryptographically_signed 0.55) -> mass {belief['chain_mass']}  "
          f"[realized net {belief['chain_net_pnl_usdc']}]")
    print(f"CONFLICT MASS:    {belief['conflict_mass']}   "
          f"(retained, never normalized away)")
    print(f"Unresolved (all): {belief['unresolved_mass']}")
    print()
    inclusions = run.all_inclusions_verify()
    ok_reload, report = verify_run(args.out)
    print("Checks:")
    print(f"  {'PASS' if inclusions else 'FAIL'}  C1 all "
          f"{len(run.event_log)} inclusion proofs verify against the root")
    print(f"  {'PASS' if ok_reload else 'FAIL'}  C2 reload + re-fold "
          f"reproduces the belief byte-for-byte")
    print()
    print(f"Belief-log root:  {run.belief_log.root(len(run.belief_log)).hex()}")
    print(f"Run file:         {args.out}")
    print()
    print("Verify independently:")
    print(f"  python -m trading_frame.run --verify --run {args.out}")
    all_ok = inclusions and ok_reload
    print()
    print(f"TRADING-FRAME RUN: {'OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
