"""THE ARENA ON SOLANA — the grader (PREREG A48, R223-R230, S131-S134; SETTLED_SOLANA.md).

A pure function of the cohort's pinned files: the capture, its sampled blocks and header, and the
days the reader pinned. No network, no clock. It re-derives the sample, the universe and the draw
from the pinned bytes before it grades a row (S131, S132), and refuses a file that is not its
manifest's.

    python -m rights_events.sol_arena verify --cohort-dir DIR
    python -m rights_events.sol_arena grade  --cohort-dir DIR --as-of YYYY-MM-DD [--out-dir DIR]

A day D is graded when the reader has pinned it (it reads D after D ends); a wallet's window is
complete when all seven days are pinned for it and the as-of is after the window's last day.
Coverage is PARTIAL for a wallet when any pinned day did not reach the day's start in the reader's
pages or carries a refusal (R227); UNDECIDED is that wallet's word, never a verdict.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from rights_events.adapters.common import AdapterError
from rights_events.adapters.sol_arena import (
    MODULUS, VENUES, check_draw, grade_wallet, residue, sampled_slots, sha256_hex, sol, status_for,
    universe_from_blocks,
)

SETTLED_SOLANA = Path(__file__).resolve().parents[1] / "contracts" / "agent_record" / "SETTLED_SOLANA.md"
COHORT_DIR = Path(__file__).parent / "fixtures" / "agent_record" / "arena_sol"
KIND = "proof_of_outcome_arena_solana"


def settled_sha(path: Path = SETTLED_SOLANA) -> str:
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))


def _manifest_check(base: Path, manifest: dict, what: str) -> None:
    for name, m in sorted(manifest["files"].items()):
        f = base / name
        if not f.exists():
            raise AdapterError(f"S131: {what}: {name} is missing")
        b = f.read_bytes()
        if len(b) != m["bytes"] or sha256_hex(b) != m["sha256"]:
            raise AdapterError(f"S131: {what}: {name} is not the manifest's bytes")


def load_capture(cdir: Path) -> tuple[dict, dict]:
    caps = sorted(cdir.glob("capture_SOL_*.json"))
    if len(caps) != 1:
        raise AdapterError(f"S131: expected one capture_SOL_*.json in {cdir}, found {len(caps)}")
    cap = json.loads(caps[0].read_text(encoding="utf-8"))
    man = json.loads((cdir / f"MANIFEST_SOL_{cap['cohort']}.json").read_text(encoding="utf-8"))
    return cap, man


def _blocks(cdir: Path, sampled: list[dict]):
    for s in sampled:
        if s["status"] != "pinned":
            continue
        raw = gzip.decompress((cdir / s["file"]).read_bytes())
        if sha256_hex(raw) != s["raw_sha256"]:
            raise AdapterError(f"S131: block {s['slot']} is not its pinned bytes")
        yield json.loads(raw)["result"]


def blocks_present(cdir: Path, cap: dict) -> bool:
    pinned = [s for s in cap["sampled"] if s["status"] == "pinned"]
    have = [s for s in pinned if (cdir / s["file"]).exists()]
    if have and len(have) != len(pinned):
        raise AdapterError(f"S131: {len(pinned) - len(have)} of {len(pinned)} pinned blocks are missing here")
    return bool(have) or not pinned


def verify_capture(cdir: Path, settled: Path = SETTLED_SOLANA, require_blocks: bool = True) -> dict:
    """S131/S132: every pinned byte is the manifest's; the residue, the sample, the universe and the
    draw are what R223-R225 derive from those bytes. Returns the capture, with
    `universe_rederived` True when the blocks were here and re-derived it.

    The blocks (~220 MB a day, A48.1) live where they were captured, not on the branch. Without them
    (require_blocks False) everything else is still checked and `universe_rederived` is False: the
    draw is re-derived from the published universe, the universe itself is not."""
    cap, man = load_capture(cdir)
    _manifest_check(cdir, man, "capture")
    if cap.get("settled_solana_sha256") != settled_sha(settled):
        raise AdapterError("S131: the capture is not graded under the ratified SETTLED_SOLANA.md")
    if cap.get("venues") != dict(VENUES) or cap.get("modulus") != MODULUS:
        raise AdapterError("S131: the capture's venues or modulus are not R223-R224's")
    header = json.loads((cdir / cap["header_file"]).read_bytes())
    if header["result"]["blockhash"] != cap["first_blockhash"]:
        raise AdapterError("S131: the first blockhash is not the pinned header's")
    r = residue(cap["first_blockhash"])
    if r != cap["residue"]:
        raise AdapterError("S131: the residue is not R223's")
    slots = sampled_slots(cap["first_slot"], cap["last_slot"], r)
    if [s["slot"] for s in cap["sampled"]] != slots:
        raise AdapterError("S131: the sampled slots are not R223's")
    if len(cap["universe"]) != cap["universe_count"] or sorted(set(cap["universe"])) != cap["universe"]:
        raise AdapterError("S131: the published universe is not sorted, unique and of its stated count")
    rederived = blocks_present(cdir, cap)
    if rederived:
        universe = universe_from_blocks(_blocks(cdir, cap["sampled"]), cap.get("excluded") or {})
        if universe != cap["universe"]:
            raise AdapterError("S131: the universe is not what the pinned blocks derive")
    elif require_blocks:
        raise AdapterError("S131: the pinned blocks are not here; run where they were captured, or pass --without-blocks")
    check_draw(cap["universe"], cap["graded"], cap["b"], cap.get("draw_tag", "S1"))
    return {**cap, "universe_rederived": rederived}


def _days(cap: dict) -> list[str]:
    d0 = date.fromisoformat(cap["window"]["t0_date"])
    return [(d0 + timedelta(days=i)).isoformat() for i in range(cap["window"]["k"])]


def grade(cdir: Path, as_of: str, settled: Path = SETTLED_SOLANA, require_blocks: bool = True) -> dict:
    cap = verify_capture(cdir, settled, require_blocks)
    days = [d for d in _days(cap) if d < as_of]
    pinned_days, day_roots = [], {}
    for d in days:
        ddir = cdir / "days" / d
        if not (ddir / "MANIFEST.json").exists():
            continue
        man = json.loads((ddir / "MANIFEST.json").read_text(encoding="utf-8"))
        _manifest_check(ddir, man, f"day {d}")
        pinned_days.append(d)
        day_roots[d] = sha256_hex((ddir / "MANIFEST.json").read_bytes())
    t0, t1 = cap["window"]["t0"], cap["window"]["t1"]
    rows = []
    for w in cap["graded"]:
        txs, read, partial_reasons = [], [], []
        for d in pinned_days:
            f = cdir / "days" / d / f"{w}.json.gz"
            if not f.exists():
                continue
            rec = json.loads(gzip.decompress(f.read_bytes()))
            if rec.get("address") != w or rec.get("day") != d:
                raise AdapterError(f"S131: {f.name} on {d} is not that wallet's day")
            read.append(d)
            if not rec["reached_start"]:
                partial_reasons.append(f"{d}: {rec['pages']} pages did not reach the day's start; first served {rec['first_served_signature']}")
            if rec["refused"]:
                partial_reasons.append(f"{d}: {len(rec['refused'])} call(s) refused by the node")
            txs += rec["transactions"]
        g = grade_wallet(w, txs, t0, t1)
        complete = len(read) == cap["window"]["k"] and as_of > cap["window"]["t1_date"]
        coverage = "PARTIAL" if partial_reasons else "FULL"
        g.update(status=status_for(complete, coverage, g["net_lamports"]), coverage=coverage,
                 coverage_reasons=partial_reasons, days_read=read, complete=complete,
                 solscan=f"https://solscan.io/account/{w}")
        rows.append(g)
    order = {"KEEP": 0, "DROP": 1, "UNDECIDED": 2, "OPEN": 3}
    rows.sort(key=lambda r: (order[r["status"]], -r["net_lamports"], r["address"]))
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in order}
    return {"kind": KIND, "prereg": "A48", "cohort": cap["cohort"], "as_of": as_of,
            "settled_solana_sha256": cap["settled_solana_sha256"], "unit": "SOL", "class": "SOLANA",
            "observation_day": cap["observation_day"], "window": cap["window"],
            "universe_count": cap["universe_count"], "universe_rederived": cap["universe_rederived"], "graded_count": len(cap["graded"]), "b": cap["b"],
            "days_pinned": pinned_days, "day_manifest_sha256": day_roots,
            "capture_sha256": sha256_hex(next(cdir.glob("capture_SOL_*.json")).read_bytes()),
            "counts": counts, "rows": rows,
            "what_is_not_claimed": "A settled net in SOL over round trips opened and closed in the window, not a finding "
                                   "about skill and not a forecast; held tokens are counted, never valued; the rest of "
                                   "the universe is UNIVERSE, NOT GRADED, never DROP."}


def render_md(a: dict) -> str:
    w = a["window"]
    out = [f"# The arena on Solana, cohort {a['cohort']}, as of {a['as_of']}", "",
           f"Universe: every fee payer that signed a successful swap on the named venues in the sampled blocks of "
           f"{a['observation_day']}: {a['universe_count']} addresses"
           + ("" if a["universe_rederived"] else " (not re-derived here: the blocks were not present)") + f"; graded: R225's draw of {a['b']}. "
           f"Window {w['t0_date']} … {w['t1_date']} (block times, k = {w['k']}). Days pinned: "
           f"{', '.join(a['days_pinned']) or 'none'}. Unit SOL, never converted.", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in a["counts"].items()) + ".", "",
           "| status | address | net (SOL) | round trips | win rate | fees (SOL) | held at t1 | listed, not netted | coverage |",
           "|---|---|---:|---:|---|---:|---:|---:|---|"]
    for r in a["rows"]:
        out.append(f"| {r['status']} | [`{r['address']}`]({r['solscan']}) | {r['net_sol']} | {r['round_trips']} | "
                   f"{r['win_rate'] or '-'} | {r['fees_sol']} | {len(r['held_at_t1'])} | {len(r['listed_not_netted'])} | "
                   f"{r['coverage']} |")
    out += ["", a["what_is_not_claimed"], ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sol_arena")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--cohort-dir", default=str(COHORT_DIR / "S1"))
    v.add_argument("--without-blocks", action="store_true")
    g = sub.add_parser("grade")
    g.add_argument("--cohort-dir", default=str(COHORT_DIR / "S1"))
    g.add_argument("--as-of", required=True)
    g.add_argument("--out-dir")
    g.add_argument("--without-blocks", action="store_true")
    a = p.parse_args(argv)
    cdir = Path(a.cohort_dir)
    try:
        if a.cmd == "verify":
            cap = verify_capture(cdir, require_blocks=not a.without_blocks)
            print(f"VERIFIED {cap['cohort']}: {sum(1 for s in cap['sampled'] if s['status'] == 'pinned')} blocks, "
                  f"universe {cap['universe_count']} " + ("re-derived from the blocks" if cap["universe_rederived"] else "NOT re-derived (blocks not here)")
                  + f", draw {len(cap['graded'])} re-derived")
            return 0
        res = grade(cdir, a.as_of, require_blocks=not a.without_blocks)
        out = Path(a.out_dir) if a.out_dir else cdir
        stem = f"arena_sol_{res['cohort']}_{a.as_of}"
        (out / f"{stem}.json").write_bytes((json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        (out / f"{stem}.md").write_bytes(render_md(res).encode("utf-8"))
        print(f"{stem}: " + ", ".join(f"{k} {v}" for k, v in res["counts"].items()) + f"; days pinned {len(res['days_pinned'])}")
        return 0
    except AdapterError as exc:
        print(f"REFUSED {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
