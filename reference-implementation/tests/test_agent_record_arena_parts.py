"""PREREG A17.8 gates (R109 / R110 / S96): the channel's parts. The splitter is greedy and
line-complete; appending to an append-only page file leaves every earlier part byte-identical;
the join returns the raw bytes; a broken part set refuses; the arena tape reader builds a
byte-identical capture from parts and from the raw file, and writes nothing on a refusal.
Offline; synthetic files only; nothing here reads the network or the clock.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "rights_events" / "fixtures" / "agent_record"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


parts = _load("arena_parts_under_test", FIXTURES / "ops" / "arena_parts.py")
reader = _load("arena_capture_from_tape_under_test", FIXTURES / "arena" / "arena_capture_from_tape.py")

NAME = "pages_fills_0x1111111111111111111111111111111111111111.jsonl"
LIMIT = 8 * 1024 * 1024


def _line(n_bytes: int, tag: str) -> bytes:
    # a JSON list that is exactly n_bytes long including its newline (a page is one JSON line)
    body = b'[{"tag":"' + tag.encode() + b'","pad":"'
    tail = b'"}]\n'
    return body + b"x" * (n_bytes - len(body) - len(tail)) + tail


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_src(tmp: Path, n_lines: int) -> Path:
    src = tmp / "src" / NAME
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"".join(_line(5_000_000, f"p{i}") for i in range(n_lines)))
    return src


def test_r109_split_is_greedy_and_line_complete(tmp_path):
    src = _write_src(tmp_path, 4)
    dst = tmp_path / "dst"
    out = parts.split_file(src, dst)
    assert [p.name for p in out] == [f"{NAME}.part00{i}" for i in range(4)]     # 5 MB lines: one per part at 8 MiB
    for p in out:
        data = p.read_bytes()
        assert data.endswith(b"\n") and len(data) == 5_000_000 and len(data) <= LIMIT
    assert parts.LIMIT == 8_388_608


def test_r109_two_small_lines_share_a_part_and_a_long_line_is_never_broken(tmp_path):
    src = tmp_path / NAME
    src.write_bytes(_line(3_000_000, "a") + _line(3_000_000, "b") + _line(9_000_000, "c") + _line(100, "d"))
    out = parts.split_file(src, tmp_path / "dst")
    sizes = [p.stat().st_size for p in out]
    assert sizes == [6_000_000, 9_000_000, 100]          # a+b fit; c alone (over the limit, whole); d alone


def test_r109_appending_leaves_earlier_parts_byte_identical(tmp_path):
    src = _write_src(tmp_path, 4)
    dst = tmp_path / "dst"
    first = {p.name: _sha(p.read_bytes()) for p in parts.split_file(src, dst)}
    with src.open("ab") as f:
        f.write(_line(5_000_000, "p4"))
    second = {p.name: _sha(p.read_bytes()) for p in parts.split_file(src, dst)}
    assert len(second) == 5 and all(second[k] == v for k, v in first.items())
    # a stale higher-numbered part is removed when the source shrinks (never happens on the tape; the rule still holds)
    src.write_bytes(_line(5_000_000, "only"))
    third = parts.split_file(src, dst)
    assert [p.name for p in third] == [f"{NAME}.part000"] and not (dst / f"{NAME}.part004").exists()


def test_r110_join_returns_the_raw_bytes(tmp_path):
    src = _write_src(tmp_path, 3)
    raw = src.read_bytes()
    dst = tmp_path / "dst"
    parts.split_file(src, dst)
    assert parts.join(dst, NAME) == raw and _sha(parts.join(dst, NAME)) == _sha(raw)
    assert parts.join(src.parent, NAME) == raw                      # the raw file wins when it is alone
    assert parts.join(tmp_path / "empty", NAME) is None             # neither raw nor parts


def test_s96_refusals(tmp_path):
    src = _write_src(tmp_path, 3)
    dst = tmp_path / "dst"
    parts.split_file(src, dst)
    # a part other than the last loses its newline
    p1 = dst / f"{NAME}.part001"
    good = p1.read_bytes()
    p1.write_bytes(good[:-1])
    with pytest.raises(parts.PartsError, match="not line-complete"):
        parts.join(dst, NAME)
    p1.write_bytes(good)
    # a number missing from the sequence
    p1.unlink()
    with pytest.raises(parts.PartsError, match="not 000"):
        parts.join(dst, NAME)
    p1.write_bytes(good)
    # raw and parts both present
    (dst / NAME).write_bytes(src.read_bytes())
    with pytest.raises(parts.PartsError, match="both present"):
        parts.join(dst, NAME)


# --- the reader (R110): a byte-identical capture from parts and from the raw file ----------------

A = "0x1111111111111111111111111111111111111111"
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
T0, T1 = 1793750400000, 1794355199999      # cohort 2026-11-03's window


def _cohort_capture(tmp: Path) -> Path:
    doc = {"kind": "agent_record_arena_capture", "synthetic": True, "note": "A17.8 gate",
           "actor": {"actor_id": ACTOR},
           "cohort": {"cohort_date": "2026-11-03", "observed_ms": 1793688589648, "payload_file": "x.json",
                      "payload_sha256": "0" * 64, "addresses": [{"address": A, "first_window": "week", "first_rank": 1}]},
           "window": {"t0_ms": T0, "t1_ms": T1, "days": 7, "started": True, "complete": False}}
    p = tmp / "capture_ARENA_2026-11-03_2026-11-03.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _page(items) -> bytes:
    return json.dumps(items, separators=(",", ":")).encode("utf-8")


def _channel(tmp: Path, as_parts: bool) -> Path:
    ch = tmp / ("parts" if as_parts else "raw")
    d = ch / "arena" / "2026-11-03"
    d.mkdir(parents=True)
    fills = [_page([{"time": T0 + 1000 * i, "tid": i, "coin": "BTC"} for i in range(50)]),
             _page([{"time": T0 + 90_000, "tid": 99, "coin": "BTC"}])]
    raw = b"".join(pg + b"\n" for pg in fills)
    (d / "pages_index.jsonl").write_bytes(b'{"file":"x"}\n')
    for who in (A, ACTOR):
        if as_parts:
            src = tmp / f"src_{who}" / f"pages_fills_{who}.jsonl"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_bytes(raw)
            parts.split_file(src, d, limit=len(fills[0]) + 1)     # forces one page per part
            assert len(parts.list_parts(d, src.name)) == 2
            fsrc = src.with_name(f"pages_funding_{who}.jsonl")
            fsrc.write_bytes(_page([]) + b"\n")
            parts.split_file(fsrc, d)
        else:
            (d / f"pages_fills_{who}.jsonl").write_bytes(raw)
            (d / f"pages_funding_{who}.jsonl").write_bytes(_page([]) + b"\n")
    return ch


def test_r110_capture_from_parts_equals_capture_from_raw(tmp_path):
    base = _cohort_capture(tmp_path)
    outs = {}
    for as_parts in (False, True):
        ch = _channel(tmp_path, as_parts)
        out = tmp_path / ("out_parts" if as_parts else "out_raw")
        rc = reader.main(["--channel-dir", str(ch), "--cohort-capture", str(base), "--as-of-date", "2026-11-06",
                          "--now-ms", "1794100000000", "--out-dir", str(out)])
        assert rc == 0
        outs[as_parts] = {p.name: p.read_bytes() for p in out.iterdir()}
    assert outs[False].keys() == outs[True].keys() and len(outs[False]) == 6
    for name in outs[False]:
        assert outs[False][name] == outs[True][name], name
    cap = json.loads(outs[True]["capture_ARENA_2026-11-03_2026-11-06.json"])
    assert [p["items"] for p in cap["rows"][0]["fills_pages"]] == [50, 1]


def test_s96_reader_refuses_and_writes_nothing(tmp_path, capsys):
    base = _cohort_capture(tmp_path)
    ch = _channel(tmp_path, True)
    d = ch / "arena" / "2026-11-03"
    (d / f"pages_fills_{A}.jsonl.part000").unlink()               # 001 without 000
    out = tmp_path / "out"
    rc = reader.main(["--channel-dir", str(ch), "--cohort-capture", str(base), "--as-of-date", "2026-11-06",
                      "--now-ms", "1794100000000", "--out-dir", str(out)])
    assert rc == 2 and "REFUSED S96" in capsys.readouterr().out
    assert not any(p.name.startswith(("capture_", "MANIFEST_", "hl_")) for p in out.iterdir())


def test_publish_script_names_the_parts_rule():
    sh = (FIXTURES / "ops" / "poo_publish_vps.sh").read_text(encoding="utf-8")
    assert "PARTS=/root/poo/arena_parts.py" in sh and "$PARTS split" in sh
    assert 'rm -f "$dst"/pages_fills_*.jsonl "$dst"/pages_funding_*.jsonl' in sh and "git gc --auto -q" in sh
