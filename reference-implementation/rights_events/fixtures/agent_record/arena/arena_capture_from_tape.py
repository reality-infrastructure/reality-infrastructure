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
from arena_parts import PartsError, join as join_parts  # noqa: E402  (R110: the channel's parts; R113: alignment below)


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


class AlignError(Exception):
    """S97 (A24): a page file's lines cannot be aligned with its index entries."""


def _index(src: Path) -> dict[str, list[dict]]:
    """pages_index.jsonl entries per page file, in append order."""
    out: dict[str, list[dict]] = {}
    p = src / "pages_index.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out.setdefault(e["file"], []).append(e)
    return out


def _align(name: str, lines: list[bytes], entries: list[dict]) -> tuple[list[tuple[bytes, dict, bool]], int]:
    """R113: pair page lines with index entries in order. A line whose sha is the entry's is the
    page; a line whose SUFFIX of the entry's `bytes` hashes to the entry's sha is a torn fragment
    glued to a whole page — the suffix is the page, recovered verbatim. Lines beyond the entries
    at the end (a page in flight at publish time) are dropped and counted. Fewer lines than
    entries, or a line that matches neither way, refuses the file (S97)."""
    if len(lines) < len(entries):
        raise AlignError(f"S97: {name}: {len(lines)} lines on disk, {len(entries)} index entries")
    out = []
    for i, (ln, e) in enumerate(zip(lines, entries)):
        if _sha(ln) == e["sha256"]:
            out.append((ln, e, False))
            continue
        n = int(e["bytes"])
        tail = ln[-n:] if 0 < n <= len(ln) else None
        if tail is not None and _sha(tail) == e["sha256"]:
            out.append((tail, e, True))
            continue
        raise AlignError(f"S97: {name}: line {i} matches its index entry neither whole nor as a suffix "
                         f"(line {len(ln)} bytes, entry {n} bytes, fetched {e.get('fetched')})")
    return out, len(lines) - len(entries)


def _raw_lines(src_dir: Path, name: str) -> list[bytes]:
    """Every line of the page file as bytes, torn or not (R113 aligns them with the index)."""
    data = join_parts(src_dir, name)
    if not data:
        return []
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def _pins(pages: list[tuple[bytes, dict, bool]]) -> list[dict]:
    pins = []
    for i, (raw, e, recovered) in enumerate(pages):
        items = json.loads(raw.decode("utf-8"))
        times = [int(it["time"]) for it in items if isinstance(it, dict) and "time" in it]
        pin = {"line": i, "sha256": _sha(raw), "bytes": len(raw), "items": len(items),
               "first_time_ms": min(times) if times else None,
               "last_time_ms": max(times) if times else None}
        if e is not None:
            pin["fetched"] = e["fetched"]
            pin["recovered"] = recovered
        pins.append(pin)
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
    staged: list[tuple[Path, bytes]] = []       # S96/S97: nothing lands in out_dir until every page file is read
    index = _index(src)
    alignment = {"files": 0, "pages": 0, "recovered_pages": 0, "dropped_trailing_lines": 0, "files_without_index": 0}

    def _aligned(name: str) -> list[tuple[bytes, dict, bool]]:
        entries = index.get(name)
        if entries is None:                       # no index for this file: the pages as JSON lines (pre-A24 captures)
            lines = _pages(src, name)
            if lines:
                alignment["files_without_index"] += 1
            return [(ln, None, False) for ln in lines]
        pages, dropped = _align(name, _raw_lines(src, name), entries)      # R113 aligns RAW lines (a glued line is not JSON)
        alignment["files"] += 1
        alignment["pages"] += len(pages)
        alignment["recovered_pages"] += sum(1 for _, _, r in pages if r)
        alignment["dropped_trailing_lines"] += dropped
        return pages

    try:
        for addr in targets:
            al = addr.lower()
            fills = _aligned(f"pages_fills_{al}.jsonl")
            funding = _aligned(f"pages_funding_{al}.jsonl")
            fills_name = f"hl_fills_{al}.jsonl.gz"
            fund_name = f"hl_funding_{al}.jsonl.gz"
            staged.append((out_dir / fills_name, _gz([b for b, _, _ in fills])))
            staged.append((out_dir / fund_name, _gz([b for b, _, _ in funding])))
            rows.append({"address": addr, "fills_file": fills_name, "fills_pages": _pins(fills),
                         "funding_file": fund_name, "funding_pages": _pins(funding),
                         "pages_recovered": sum(1 for _, _, r in fills + funding if r),
                         "source": "vps fills tape via the channel branch vps/poo-files"})
    except (PartsError, AlignError) as exc:
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
                  "tape_index_sha256": index_sha,
                  "alignment": alignment},
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
          f"pages {sum(len(r['fills_pages']) for r in rows)} fills / {sum(len(r['funding_pages']) for r in rows)} funding  "
          f"alignment {alignment}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
