"""Capture tool (NOT part of ri_core, NOT a test): cohort S1's universe from the day's blocks
(PREREG A48 R223-R225). Network: the public node only, through rpc.Node. No ranked list of any kind
and no indexer is read (S133).

    python capture_sol_universe.py --cohort S1 --day 2026-11-19 [--b 100] [--out-dir DIR]

Steps: find the day's first slot (block time >= 00:00:00Z) and the first slot after it by
getBlockTime; pin the first slot's header (getBlock, transactionDetails none) for its blockhash; the
residue and the sample by R223; pin every sampled block verbatim (getBlock full, json, version 1,
no rewards) as gzip; derive the universe and the draw with the pure adapter (the grader re-derives
both, S131/S132); write

    <out>/blocks/<slot>.json.gz        each sampled block's response bytes, gzip (mtime 0)
    <out>/header_<slot>.json           the first slot's header response bytes
    <out>/capture_SOL_<cohort>.json    the sample, the universe, the draw, the window
    <out>/calls_universe.jsonl         every call: method, bytes, seconds, status
    <out>/MANIFEST_SOL_<cohort>.json   every file's bytes and sha256
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))                 # the reference-implementation root
sys.path.insert(0, str(HERE))
from rights_events.adapters.sol_arena import (  # noqa: E402
    MODULUS, VENUES, draw, payers_in_block, residue, sampled_slots, sha256_hex, universe_from_payers,
)
from rpc import Node, Refused  # noqa: E402

SETTLED_SOLANA = HERE.parents[3] / "contracts" / "agent_record" / "SETTLED_SOLANA.md"
BLOCK_OPTS = {"maxSupportedTransactionVersion": 1, "transactionDetails": "full", "encoding": "json", "rewards": False}
SKIPPED_CODES = (-32007, -32009, -32004)
SLOTS_PER_S = 4.65                                        # measured on 2026-11-17's pinned blocks (A48.1)


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def _block_time(node: Node, slot: int) -> int | None:
    doc, _ = node.call("getBlockTime", [slot])
    return doc.get("result") if not doc.get("error") else None


def _produced_time(node: Node, slot: int, step: int = 1, tries: int = 12) -> tuple[int, int]:
    for _ in range(tries):
        t = _block_time(node, slot)
        if t is not None:
            return slot, t
        slot += step
    raise Refused(f"no produced block within {tries} slots of {slot}")


def first_slot_at_or_after(node: Node, t: int, head: int) -> tuple[int, int]:
    """The lowest produced slot whose block time is >= t (block times are non-decreasing).

    Invariant: lo is produced with time < t; hi is produced with time >= t; no produced slot in
    (lo, top) has been seen yet, and every slot in [top, hi) is known skipped or not yet needed."""
    hi, thi = _produced_time(node, head, -1)
    if thi < t:
        raise Refused(f"the node's newest block ({thi}) is before {t}: the day is not over")
    lo, tlo = _produced_time(node, max(0, hi - int((thi - t) * SLOTS_PER_S) - 20_000), 1)
    while tlo >= t:
        lo, tlo = _produced_time(node, max(0, lo - 50_000), 1)
    top = hi
    while top - lo > 1:
        mid = (lo + top) // 2
        s, tm = mid, None
        while s < top:
            tm = _block_time(node, s)
            if tm is not None:
                break
            s += 1
        if s >= top:                                      # [mid, top) all skipped
            top = mid
        elif tm >= t:
            hi, thi, top = s, tm, mid
        else:
            lo = s
    return hi, thi


def _write(path: Path, data: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": sha256_hex(data)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", default="S1")
    p.add_argument("--day", required=True)
    p.add_argument("--b", type=int, default=100)
    p.add_argument("--out-dir")
    a = p.parse_args(argv)
    day = date.fromisoformat(a.day)
    out = Path(a.out_dir) if a.out_dir else HERE / a.cohort
    node = Node()
    t0, t_next = _ts(day), _ts(day + timedelta(days=1))
    head, _ = node.call("getSlot", [{"commitment": "finalized"}])
    first, first_t = first_slot_at_or_after(node, t0, head["result"])
    boundary, boundary_t = first_slot_at_or_after(node, t_next, head["result"])
    last = boundary - 1
    hdoc, hraw = node.call("getBlock", [first, {**BLOCK_OPTS, "transactionDetails": "none"}])
    blockhash = hdoc["result"]["blockhash"]
    files = {f"header_{first}.json": _write(out / f"header_{first}.json", hraw)}
    r = residue(blockhash)
    slots = sampled_slots(first, last, r)
    print(f"{a.cohort} {a.day}: slots {first} .. {last} ({last - first + 1}), residue {r} from {blockhash}, sampled {len(slots)}", flush=True)
    sampled, payer_sets = [], []
    for i, s in enumerate(slots):
        try:
            doc, raw = node.call("getBlock", [s, BLOCK_OPTS])
        except Refused as exc:
            sampled.append({"slot": s, "status": "refused", "reason": str(exc)})
            continue
        err = doc.get("error")
        if err:
            st = "skipped" if err.get("code") in SKIPPED_CODES else "refused"
            sampled.append({"slot": s, "status": st, "reason": err.get("message")})
            continue
        name = f"blocks/{s}.json.gz"
        # the block's sha is in `sampled`, not the manifest: the blocks stay off the branch (A48.1)
        meta = _write(out / name, gzip.compress(raw, 9, mtime=0))
        sampled.append({"slot": s, "status": "pinned", "file": name, **meta, "raw_sha256": sha256_hex(raw)})
        payer_sets.append(payers_in_block(doc["result"]))
        del doc, raw
        if i % 25 == 0:
            print(f"  {i + 1}/{len(slots)} slot {s}", flush=True)
    universe = universe_from_payers(payer_sets, {})
    graded = draw(universe, a.b)
    w0, w1 = day + timedelta(days=1), day + timedelta(days=7)
    settled_sha = sha256_hex(SETTLED_SOLANA.read_bytes().replace(b"\r\n", b"\n"))
    cap = {
        "kind": "proof_of_outcome_arena_solana_capture", "prereg": "A48", "cohort": a.cohort,
        "settled_solana_sha256": settled_sha, "source": node.url,
        "observation_day": a.day, "day_t0": t0, "day_t1": t_next - 1,
        "first_slot": first, "first_slot_block_time": first_t, "first_blockhash": blockhash,
        "header_file": f"header_{first}.json",
        "boundary_slot": boundary, "boundary_slot_block_time": boundary_t, "last_slot": last,
        "modulus": MODULUS, "residue": r, "sampled": sampled,
        "venues": dict(VENUES), "excluded": {},
        "universe_count": len(universe), "universe": universe,
        "b": a.b, "draw_tag": "S1", "graded": graded,
        "window": {"t0_date": w0.isoformat(), "t1_date": w1.isoformat(), "t0": _ts(w0), "t1": _ts(w1 + timedelta(days=1)) - 1, "k": 7},
        "calls": {"total": len(node.log), "bytes": sum(c["bytes"] for c in node.log)},
    }
    text = json.dumps(cap, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    files[f"capture_SOL_{a.cohort}.json"] = _write(out / f"capture_SOL_{a.cohort}.json", text.encode("utf-8"))
    calls = "".join(json.dumps(c, sort_keys=True) + "\n" for c in node.log).encode("utf-8")
    files["calls_universe.jsonl"] = _write(out / "calls_universe.jsonl", calls)
    man = json.dumps({"cohort": a.cohort, "files": files}, indent=1, sort_keys=True) + "\n"
    (out / f"MANIFEST_SOL_{a.cohort}.json").write_bytes(man.encode("utf-8"))
    pinned = sum(1 for x in sampled if x["status"] == "pinned")
    print(f"{a.cohort}: pinned {pinned} of {len(slots)} sampled blocks; universe {len(universe)}; graded {len(graded)}; "
          f"calls {cap['calls']['total']}, {cap['calls']['bytes']} bytes", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
