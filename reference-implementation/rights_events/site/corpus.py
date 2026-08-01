"""Disclosure-corpus builder (Contract 3, plan-gate ruling (i)).

RUNNER-PATTERN COMPOSITION, WALL UNTOUCHED: this module composes
existing fixtures through the UNCHANGED Contract 1 pipeline exactly
the way the frozen runners do — it adds no parser, no policy, no
schema, and modifies nothing outside rights_events/site/. It exists
so the derived-disclosure view can generate its reservation-handling
section from real captured signals instead of an empty line.

Corpus composition (stated verbatim on the disclosure page, per the
ruling): the SYNTHETIC Song X split-conflict fixture
(fixtures/pro_conflict/song_x_SYNTHETIC.json) plus the REAL captured
reservation signals (fixtures/tdmrep/nytimes_robots.txt, a verbatim
2026-08-01 capture, and fixtures/tdmrep/tdmrep_example.json, the W3C
TDMRep Final CG Report example) — provenance in each fixture
directory's MANIFEST.json.

Usage:
    python -m rights_events.site.corpus [--out CORPUS_FILE]

Commits: the Song X ownership beliefs pre- and post-revocation, and
one use_reservation belief per web subject. as_of values are derived
from the record dates, never a clock. The artifact verifies with the
same replay commands as every other run file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.adapters.tdmrep import parse_robots_txt, parse_tdmrep_json
from rights_events.pipeline import RightsPipeline
from rights_events.policy import ltime_for
from rights_events.song_x import POST_AS_OF, PRE_AS_OF
from rights_events.song_x import SUBJECT as SONG_X_SUBJECT

_FIXTURES = Path(__file__).parents[1] / "fixtures"


def build_events():
    """The corpus events, from the existing fixtures verbatim."""
    events = list(parse_registrations(
        (_FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
            encoding="utf-8")))
    meta = json.loads((_FIXTURES / "tdmrep" / "MANIFEST.json").read_text(
        encoding="utf-8"))["files"]
    robots_meta = meta["nytimes_robots.txt"]
    events += parse_robots_txt(
        (_FIXTURES / "tdmrep" / "nytimes_robots.txt").read_text(
            encoding="utf-8"),
        site_host="www.nytimes.com",
        source_url=robots_meta["source_url"],
        observed_date=robots_meta["observed_date"])
    tdm_meta = meta["tdmrep_example.json"]
    events += parse_tdmrep_json(
        (_FIXTURES / "tdmrep" / "tdmrep_example.json").read_text(
            encoding="utf-8"),
        site_host="provider.example",
        source_url=tdm_meta["source_url"],
        observed_date=tdm_meta["observed_date"])
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rights_events.site.corpus",
        description="Build the disclosure-corpus run artifact.")
    parser.add_argument("--out", default="corpus_run.ri",
                        help="run file to write (default: corpus_run.ri)")
    args = parser.parse_args(argv)

    events = build_events()
    pipeline = RightsPipeline()
    pipeline.ingest(events)
    as_of = max(ltime_for(e.observed_date) for e in events)

    pipeline.commit(SONG_X_SUBJECT, "ownership_shares", PRE_AS_OF)
    pipeline.commit(SONG_X_SUBJECT, "ownership_shares", POST_AS_OF)
    for host in ("provider.example", "www.nytimes.com"):
        pipeline.commit(f"web:{host}", "use_reservation", as_of)

    data = pipeline.save(args.out)
    print(f"corpus artifact: {args.out} ({len(data)} bytes, "
          f"{len(pipeline.event_log)} events, "
          f"{len(pipeline.belief_log)} beliefs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
