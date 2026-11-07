"""Offline builder (NOT part of ri_core, NOT a test): turn a cohort's pages from the VPS
fills tape (PREREG A18 R93; published on the channel branch `vps/poo-files` under `arena/`)
into the pinned capture the arena runner grades — the same `agent_record_arena_capture`
schema `capture_arena_from_hl.py` writes, without touching the network.

Inputs: the extracted channel directory (`--channel-dir`, holding `arena/<cohort>/
pages_fills_<address>.jsonl`, `pages_funding_<address>.jsonl` — raw, or as the channel's
line-complete parts `<name>.partNNN` joined back into the identical bytes (A17.8 R109/R110;
a broken part set refuses the build, S96) — and `pages_index.jsonl`) and the
cohort's own capture of its observation (`--cohort-capture`, the `capture_ARENA_<cohort>_
<cohort>.json` written when the boards were observed: it carries the addresses verbatim, the
payload sha and the window). Every raw page line is carried byte-for-byte into
`hl_fills_<address>.jsonl.gz` / `hl_funding_<address>.jsonl.gz` (gzip, mtime 0) under
`arena/<cohort>/` and pinned by sha256 in `capture_ARENA_<cohort>_<as_of>.json`.

    python arena_capture_from_tape.py --channel-dir /tmp/poo --cohort-capture
        rights_events/fixtures/agent_record/arena/2026-11-03/capture_ARENA_2026-11-03_2026-11-03.json
        --as-of-date 2026-11-05 [--paper-marks vps/marks_2026-11-04.jsonl ...]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
sys.path.insert(0, str(FIXTURES / "ops"))
from arena_parts import PartsError, join as join_parts  # noqa: E402  (R110: the channel's parts)


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _gz(lines: list[bytes]) -> bytes:
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g:
        for line in lines:
            g.write(line + b"\n")
    return bio.getvalue()


def _write_lf(path: Path, text: str) -> bytes:
    data = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def _pages(src_dir: Path, name: str) -> list[bytes]:
    """The page lines of `name` in `src_dir`: from the raw file, or from its parts joined
    (R110). Raises PartsError (S96) on a broken part set."""
    data = join_parts(src_dir, name)
    if not data:
        return []
    if not data.endswith(b"\n"):
        data += b"\n"          # a page being appended at publish time: the last line is whole JSON or dropped below
    lines = data[:-1].split(b"\n")
    out = []
    for line in lines:
        try:
            json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue           # a torn last line is not a page; it is re-fetched by the tape
        out.append(line)
    return out


def _pins(lines: list[bytes]) -> list[dict]:
    pins = []
    for i, raw in enumerate(lines):
        items = json.loads(raw.decode("utf-8"))
        times = [int(it["time"]) for it in items if isinstance(it, dict) and "time" in it]
        pins.append({"line": i, "sha256": _sha(raw), "bytes": len(raw), "items": len(items),
                     "first_time_ms": min(times) if times else None,
                     "last_time_ms": max(times) if times else None})
    return pins


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--channel-dir", type=Path, required=True)
    p.add_argument("--cohort-capture", type=Path, required=True)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--now-ms", type=int, required=True, help="the clock at the read (from the caller; this tool reads no clock)")
    p.add_argument("--paper-marks", action="append", default=[])
    p.add_argument("--out-dir", type=Path, default=None, help="where the capture lands (default: this directory / <cohort>)")
    a = p.parse_args(argv)

    base = json.loads(a.cohort_capture.read_text(encoding="utf-8"))
    cohort_date = base["cohort"]["cohort_date"]
    t0, t1 = int(base["window"]["t0_ms"]), int(base["window"]["t1_ms"])
    src = a.channel_dir / "arena" / cohort_date
    out_dir = (a.out_dir if a.out_dir is not None else HERE / cohort_date)
    out_dir.mkdir(parents=True, exist_ok=True)
    actor = base["actor"]["actor_id"]
    targets = [x["address"] for x in base["cohort"]["addresses"]]
    if actor.lower() not in {t.lower() for t in targets}:
        targets.append(actor)
    index_sha = _sha((src / "pages_index.jsonl").read_bytes()) if (src / "pages_index.jsonl").exists() else None
    rows = []
    staged: list[tuple[Path, bytes]] = []       # S96: nothing lands in out_dir until every page file joined
    try:
        for addr in targets:
            al = addr.lower()
            fills = _pages(src, f"pages_fills_{al}.jsonl")
            funding = _pages(src, f"pages_funding_{al}.jsonl")
            fills_name = f"hl_fills_{al}.jsonl.gz"
            fund_name = f"hl_funding_{al}.jsonl.gz"
            staged.append((out_dir / fills_name, _gz(fills)))
            staged.append((out_dir / fund_name, _gz(funding)))
            rows.append({"address": addr, "fills_file": fills_name, "fills_pages": _pins(fills),
                         "funding_file": fund_name, "funding_pages": _pins(funding),
                         "source": "vps fills tape via the channel branch vps/poo-files"})
    except PartsError as exc:
        print(f"REFUSED {exc}; no capture written")
        return 2
    for path, data in staged:
        path.write_bytes(data)
    paper_files = [{"file": rel, "sha256": _sha((FIXTURES / rel).read_bytes())} for rel in a.paper_marks]
    capture = {
        **{k: base[k] for k in ("kind", "synthetic", "note", "actor", "cohort")},
        # R99 (A19): the flags are functions of the as-of date, as the grader recomputes them
        "window": {**base["window"], "started": a.as_of_date >= _day(t0), "complete": a.as_of_date > _day(t1)},
        "as_of": {"as_of_date": a.as_of_date, "fetched_ms": a.now_ms,
                  "api": "https://api.hyperliquid.xyz/info",
                  "pagination": ("pages fetched hourly by the VPS fills tape (R93) with the same "
                                 "pagination as the HL capture tool; carried here byte-for-byte"),
                  "tape_index_sha256": index_sha},
        "paper": {"files": paper_files},
        "rows": rows,
    }
    cap_name = f"capture_ARENA_{cohort_date}_{a.as_of_date}.json"
    cap_bytes = _write_lf(out_dir / cap_name, json.dumps(capture, indent=2) + "\n")
    files = sorted(p.name for p in out_dir.iterdir() if p.is_file() and not p.name.startswith("MANIFEST_ARENA_"))
    manifest = {"fixture": cap_name, "status": "ARENA", "bytes": len(cap_bytes), "sha256": _sha(cap_bytes),
                "generator": "arena/arena_capture_from_tape.py", "cohort_date": cohort_date,
                "as_of_date": a.as_of_date, "window": capture["window"],
                "addresses": len(base["cohort"]["addresses"]), "rows_with_pages": len(rows),
                "tape_index_sha256": index_sha,
                "files": [{"name": n, "bytes": (out_dir / n).stat().st_size, "sha256": _sha((out_dir / n).read_bytes())} for n in files]}
    _write_lf(out_dir / f"MANIFEST_ARENA_{cohort_date}_{a.as_of_date}.json", json.dumps(manifest, indent=2) + "\n")
    print(f"capture: {out_dir / cap_name}  sha256 {manifest['sha256']}  rows {len(rows)}  "
          f"pages {sum(len(r['fills_pages']) for r in rows)} fills / {sum(len(r['funding_pages']) for r in rows)} funding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
