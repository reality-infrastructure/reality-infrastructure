#!/usr/bin/env python3
"""THE CHANNEL'S PARTS (PREREG A17.8 R109 / R110 / S96). An arena page file
(`pages_fills_<address>.jsonl`, `pages_funding_<address>.jsonl`; one HTTP response body per
line, append-only, R93) is published as line-complete parts of at most LIMIT bytes:

    <name>.part000, <name>.part001, ...   (three digits, greedy in file order)

A part holds whole lines only; a single line longer than LIMIT is a part by itself, never
broken. Because the source is append-only, every part but the last is byte-identical from one
publish to the next, so git stores it once and GitHub's 100 MB file limit is never reached.

`split_file` (the VPS publisher) streams the source once and rewrites only the parts whose
size changed (earlier parts are immutable; the last part grows). `join` (the record's reader)
returns the identical bytes: the raw file if present, else the parts in order; a broken part
set refuses (S96): a part other than the last not ending in a newline, a number missing from
000..N, or a raw file AND parts both present.

No network, no clock, no reasoning as input (R96). Pure functions of the files.

    python3 -I arena_parts.py split SRC_FILE DST_DIR      # the publisher
    python3 -I arena_parts.py join  DIR NAME > out        # anyone's check
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

LIMIT = 8 * 1024 * 1024          # 8 MiB = 8 388 608 bytes (R109)
PART_RE = re.compile(r"^(?P<name>.+\.jsonl)\.part(?P<n>\d{3})$")
PAGE_FILE_RE = re.compile(r"^pages_(fills|funding)_0x[0-9a-f]{40}\.jsonl$")


class PartsError(Exception):
    """S96: the part set is not what R109 writes."""


def is_page_file(name: str) -> bool:
    return bool(PAGE_FILE_RE.match(name))


def part_name(name: str, n: int) -> str:
    return f"{name}.part{n:03d}"


def plan(src: Path, limit: int = LIMIT):
    """Yield (index, bytes) for each part, streaming the source once; greedy whole lines."""
    cur: list[bytes] = []
    cur_len = 0
    n = 0
    with src.open("rb") as f:
        for line in f:
            if cur_len and cur_len + len(line) > limit:
                yield n, b"".join(cur)
                n += 1
                cur, cur_len = [], 0
            cur.append(line)
            cur_len += len(line)
    yield n, b"".join(cur)       # the last part (an empty file gives one empty part 000)


def split_file(src: Path, dst_dir: Path, limit: int = LIMIT) -> list[Path]:
    """Write/refresh the parts of `src` in `dst_dir`; remove stale higher-numbered parts.
    Returns the part paths in order. Only a part whose size differs from the file on disk is
    rewritten (R109: earlier parts are immutable, the last part grows)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    last_n = -1
    for n, data in plan(src, limit):
        p = dst_dir / part_name(src.name, n)
        if not (p.exists() and p.stat().st_size == len(data)):
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, p)
        written.append(p)
        last_n = n
    for stale in dst_dir.glob(part_name(src.name, 0)[:-3] + "[0-9][0-9][0-9]"):
        m = PART_RE.match(stale.name)
        if m and int(m.group("n")) > last_n:
            stale.unlink()
    return written


def list_parts(d: Path, name: str) -> list[Path]:
    out = []
    for p in d.glob(name + ".part[0-9][0-9][0-9]"):
        m = PART_RE.match(p.name)
        if m and m.group("name") == name:
            out.append((int(m.group("n")), p))
    return [p for _, p in sorted(out)]


def join(d: Path, name: str) -> bytes | None:
    """The page file's bytes: the raw file if present, else the joined parts (R110).
    None when neither exists. S96 refusals raise PartsError."""
    raw = d / name
    parts = list_parts(d, name)
    if raw.exists() and parts:
        raise PartsError(f"S96: {name}: a raw file and {len(parts)} parts are both present")
    if raw.exists():
        return raw.read_bytes()
    if not parts:
        return None
    numbers = [int(PART_RE.match(p.name).group("n")) for p in parts]
    if numbers != list(range(len(parts))):
        raise PartsError(f"S96: {name}: part numbers {numbers} are not 000..{len(parts) - 1:03d}")
    chunks = []
    for i, p in enumerate(parts):
        data = p.read_bytes()
        if i < len(parts) - 1 and not data.endswith(b"\n"):
            raise PartsError(f"S96: {name}: {p.name} is not line-complete (does not end in a newline) and is not the last part")
        chunks.append(data)
    return b"".join(chunks)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 3 and argv[0] == "split":
        parts = split_file(Path(argv[1]), Path(argv[2]))
        print(f"{Path(argv[1]).name}: {len(parts)} parts, largest {max(p.stat().st_size for p in parts)} bytes")
        return 0
    if len(argv) == 3 and argv[0] == "join":
        try:
            data = join(Path(argv[1]), argv[2])
        except PartsError as exc:
            print(f"REFUSED {exc}", file=sys.stderr)
            return 2
        if data is None:
            print(f"REFUSED {argv[2]}: no raw file and no parts", file=sys.stderr)
            return 2
        sys.stdout.buffer.write(data)
        return 0
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
