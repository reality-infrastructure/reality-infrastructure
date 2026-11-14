"""Put one operator event on the ledger, or prove one is still there.

    python -m packs.ri_operator.record append <type> --entity-type T --entity-id ID
                                              --payload JSON|@file --source SRC [--db DSN]
    python -m packs.ri_operator.record verify <event_id> [--db DSN]

``<type>`` is the event name without the pack prefix (``constraint_named``).
``append`` goes through engine.events.EventLog, so an undeclared type or a payload
that fails its schema is refused before anything is written.  ``verify`` re-derives
the ledger entry from the stored row and checks its inclusion proof.

Exit codes: 0 done, 2 refused or mismatch, 1 usage or engine error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.errors import CitationError, EngineError, EventError
from engine.events import EventLog
from engine.packs import load_pack
from engine.store import Engine

PACK = "ri_operator"


def _payload(spec: str) -> dict:
    text = Path(spec[1:]).read_text(encoding="utf-8") if spec.startswith("@") else spec
    data = json.loads(text)
    if not isinstance(data, dict):
        raise EventError("--payload must be a JSON object")
    return data


def append(engine: Engine, event_type: str, *, entity_type: str, entity_id: str,
           payload: dict, source: str) -> dict:
    log = EventLog(engine, load_pack(PACK))
    return log.append(entity_type=entity_type, entity_id=entity_id,
                      event_type=f"{PACK}.{event_type}", payload=payload, source=source)


def verify(engine: Engine, event_id: str) -> dict:
    row = engine.store.get_event(event_id)
    if row is None:
        raise EngineError(f"no event {event_id!r}")
    engine.ledger.verify_row(row)
    return row


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m packs.ri_operator.record")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("event_type")
    a.add_argument("--entity-type", required=True)
    a.add_argument("--entity-id", required=True)
    a.add_argument("--payload", required=True)
    a.add_argument("--source", required=True)
    a.add_argument("--db")
    v = sub.add_parser("verify")
    v.add_argument("event_id")
    v.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        if args.cmd == "append":
            row = append(engine, args.event_type, entity_type=args.entity_type,
                         entity_id=args.entity_id, payload=_payload(args.payload),
                         source=args.source)
            print(f"event_id={row['event_id']} type={row['event_type']} "
                  f"ledger_index={row['ledger_index']} leaf={row['leaf_hash']} "
                  f"root={engine.ledger.root()}")
            return 0
        row = verify(engine, args.event_id)
        print(f"OK event={row['event_id']} type={row['event_type']} "
              f"ledger_index={row['ledger_index']} root={engine.ledger.root()}")
        return 0
    except (EventError, CitationError) as e:
        print(f"REFUSED: {e}")
        return 2
    except (EngineError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        engine.close()


if __name__ == "__main__":
    sys.exit(main())
