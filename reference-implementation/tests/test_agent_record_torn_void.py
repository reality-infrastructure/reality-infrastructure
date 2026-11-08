"""A26 / P21 gates: the reader and the ledger read torn lines and void days by rule.

R115  a day-file line is a row, the row-suffix of a glued torn line (fragment counted, its row lost,
      never reconstructed) or an in-flight tail; anything else refuses the file (S98), nothing computed
R116  a day whose marks carry the marker's own void mark (S72) is disclosed and counted for nothing:
      the reader removes it from the pass line's days; the ledger removes it from `days` for ledgers
      as of 2026-11-08 and later, and not before (a ledger's points never move, A23)
R117  a pin `_as_read_<date>` dated >= 2026-11-08 is read by the ledgers as of <date> and later only;
      earlier pins keep A23's cutoff; the ledger as of 2026-11-07 renders byte-for-byte A17.10's
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from rights_events import agent_ledger as led
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_READER = _FIX / "ops" / "poo_forward_read.py"
LEDGER = _FIX / "ledger"


def _load():
    spec = importlib.util.spec_from_file_location("poo_forward_read_t", _READER)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _row(fork, day_ms, net, reason="stop"):
    fam, coin = fork.split(":")
    return {"fork": fork, "family": fam, "coin": coin, "direction": 1, "entry_ms": day_ms + 3_600_000,
            "entry_px": 100.0, "exit_ms": day_ms + 7_200_000, "exit_px": 101.0, "exit_reason": reason,
            "gross_bps": net + 18.64, "cost_bps": 18.64, "funding_bps": 0.0, "net_bps": net, "in_sample": False,
            "spread_bps_per_leg": 0.5, "spread_source": "l2Book:ab", "signal": {"leader": "0xabc"}}


def _void(day, ms):
    return {"type": "void", "day": day, "ms": ms, "reason": "S72 tape stale > 6 min"}


def _day_ms(day):
    y, m, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _dumps(r):
    return json.dumps(r, separators=(",", ":"), sort_keys=True)


def _tree(tmp_path: Path, marks_text_by_day: dict[str, str], signals_text: str = '{"type":"F4_signal"}\n') -> Path:
    d = tmp_path / "tree"
    (d / "marker").mkdir(parents=True)
    for day, text in marks_text_by_day.items():
        (d / "marker" / f"marks_{day}.jsonl").write_text(text, encoding="utf-8")
    (d / "marker" / f"signals_{max(marks_text_by_day)}.jsonl").write_text(signals_text, encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"generated_at": "2026-11-08T00:07:00Z", "poo_tape": "active",
                                                 "poo_marker": "active", "tape_newest_mtime": "2026-11-08T00:06:30Z"}))
    (d / "marker" / "marker_state.json").write_text(json.dumps({"void_days": []}))
    return d


DAYS = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]


# --- R115 ----------------------------------------------------------------------------------------

def test_r115_glued_line_recovers_the_trailing_row_verbatim_and_counts_the_fragment(tmp_path):
    rd = _load()
    day = DAYS[0]
    whole = _row("F4:ETH", _day_ms(day), -60.19)
    lost_head = _dumps(_row("F4:BTC", _day_ms(day), 5.0))[:88]          # cut mid-write, as the full disk did
    text = _dumps(_row("F4:SOL", _day_ms(day), 3.0)) + "\n" + lost_head + _dumps(whole) + "\n"
    p = tmp_path / "marks_x.jsonl"
    p.write_text(text, encoding="utf-8")
    rows, voids, al = rd.read_day_lines(p, "marks")
    assert [r["fork"] for r in rows] == ["F4:SOL", "F4:ETH"] and rows[1] == whole and voids == []
    assert al["torn_fragments"] == [{"line": 2, "head": lost_head[:60]}] and al["lost_rows"] == 1 and al["in_flight"] == 0
    assert al["lines"] == 2 and al["rows"] == 2
    # the recovered row is the suffix from the LEFTMOST `{` that parses: the inner `{` of `signal` is not chosen
    assert "signal" in rows[1]


def test_r115_in_flight_tail_is_dropped_and_counted_but_not_elsewhere(tmp_path):
    rd = _load()
    day = DAYS[0]
    good = _dumps(_row("F4:ETH", _day_ms(day), -1.0))
    p = tmp_path / "marks_y.jsonl"
    p.write_text(good + "\n" + good[:40] + "\n", encoding="utf-8")
    rows, voids, al = rd.read_day_lines(p, "marks")
    assert len(rows) == 1 and al["in_flight"] == 1 and al["torn_fragments"] == []
    # the same torn line NOT last → S98, nothing computed
    p.write_text(good[:40] + "\n" + good + "\n", encoding="utf-8")
    with pytest.raises(rd.Refused, match="S98") as ei:
        rd.read_day_lines(p, "marks")
    assert "line 1" in str(ei.value)


def test_r115_marks_object_that_is_neither_episode_nor_void_mark_refuses(tmp_path):
    rd = _load()
    p = tmp_path / "marks_z.jsonl"
    p.write_text('{"type":"something_else","ms":1}\n', encoding="utf-8")
    with pytest.raises(rd.Refused, match="S98"):
        rd.read_day_lines(p, "marks")
    # a signals file takes any object
    q = tmp_path / "signals_z.jsonl"
    q.write_text('{"type":"something_else","ms":1}\n', encoding="utf-8")
    rows, voids, al = rd.read_day_lines(q, "signals")
    assert len(rows) == 1 and al["rows"] == 1


def test_r115_the_cli_prints_refused_and_exits_1_writing_nothing(tmp_path, capsys):
    rd = _load()
    day = DAYS[0]
    good = _dumps(_row("F4:ETH", _day_ms(day), -1.0))
    d = _tree(tmp_path, {day: good[:30] + "\n" + good + "\n"})
    rc = rd.main(["--dir", str(d), "--day", day, "--days", day, "--n-alive", "6"])
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith("REFUSED S98") and f"marks_{day}.jsonl line 1" in out
    assert "Pins" not in out


def test_r115_void_rows_no_longer_stop_the_reader_and_the_file_is_pinned_as_served(tmp_path):
    rd = _load()
    day = DAYS[0]
    text = _dumps(_void(day, 1)) + "\n" + _dumps(_row("F4:ETH", _day_ms(day), -1.0)) + "\n"
    d = _tree(tmp_path, {day: text})
    r = rd.read(d, day, [day], 6)
    assert r["episodes"] == 1 and r["alignment"][f"marks_{day}.jsonl"]["void_marks"] == 1
    import hashlib
    assert r["pins"][f"marks_{day}.jsonl"] == hashlib.sha256((d / "marker" / f"marks_{day}.jsonl").read_bytes()).hexdigest()


# --- R116, the reader -----------------------------------------------------------------------------

def _five_days_text(void_day: str | None):
    texts = {}
    for d in DAYS:
        rows = [_row("F4:BTC", _day_ms(d), 10.0), _row("F4:BTC", _day_ms(d), 12.0), _row("C1:BTC", _day_ms(d), -40.0)]
        lines = [_dumps(r) for r in rows]
        if d == void_day:
            lines.insert(1, _dumps(_void(d, _day_ms(d) + 1000)))
        texts[d] = "\n".join(lines) + "\n"
    return texts


def test_r116_reader_removes_a_voided_day_from_the_pass_line_and_discloses_it(tmp_path):
    rd = _load()
    full = rd.read(_tree(tmp_path / "a", _five_days_text(None)), DAYS[-1], DAYS, 6)
    assert full["pass_line"]["F4:BTC"]["run_days"] == 5 and full["pass_line"]["F4:BTC"]["candidate"] is True
    assert full["void_days_by_row"] == [] and full["pass_line_days"] == DAYS
    voided = rd.read(_tree(tmp_path / "b", _five_days_text(DAYS[2])), DAYS[-1], DAYS, 6)
    assert voided["void_days_by_row"] == [DAYS[2]] and voided["pass_line_days"] == [d for d in DAYS if d != DAYS[2]]
    p = voided["pass_line"]["F4:BTC"]
    assert p["run_days"] == 4 and p["candidate"] is False and p["n_episodes"] == 8       # the void day's 2 rows count for nothing
    disc = voided["void_day_disclosure"][DAYS[2]]
    assert disc["episodes"] == 3 and disc["forks"]["F4:BTC"] == {"n": 2, "sum_net_bps": 22.0}
    assert voided["void_marks"][DAYS[2]][0]["reason"] == "S72 tape stale > 6 min"
    # the day read itself void: the fork table is still disclosed, health says so by row, the markdown names it
    v2 = rd.read(_tree(tmp_path / "c", _five_days_text(DAYS[-1])), DAYS[-1], DAYS, 6)
    assert v2["episodes"] == 3 and v2["health"]["day_void"] is True and v2["health"]["day_void_by_row"] is True
    assert v2["health"]["day_void_by_state"] is False
    md = rd.markdown(v2)
    assert "VOID by the marker's own mark" in md and "counted for nothing" in md and "Alignment (R115)" in md


# --- R116 / R117, the ledger --------------------------------------------------------------------

def _vps(tmp_path: Path, texts: dict[str, str]) -> Path:
    vps = tmp_path / "vps"
    vps.mkdir()
    for name, text in texts.items():
        (vps / name).write_text(text, encoding="utf-8")
    return vps


def test_r116_ledger_excludes_a_voided_day_from_2026_11_08_on_and_not_before(tmp_path):
    texts = {f"marks_{d}.jsonl": t for d, t in _five_days_text(DAYS[2]).items()}
    vps = _vps(tmp_path, texts)
    none = tmp_path / "none.json"
    before = led.ledger("2026-11-07", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert before["days"] == DAYS and "void_days_excluded" not in before
    assert "Void days" not in led.render_markdown(before)
    after = led.ledger("2026-11-08", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert after["days"] == [d for d in DAYS if d != DAYS[2]]
    assert after["void_days_excluded"] == {DAYS[2]: {"void_marks": 1, "episodes_not_counted": 3}}
    btc = next(r for r in after["forks"] if r["fork"] == "F4:BTC")
    assert btc["days_alive"] == 4 and btc["episodes"] == 8 and btc["run_days"] == 4
    assert f"Void days (R116" in led.render_markdown(after) and DAYS[2] in led.render_markdown(after)
    # the readings and pins still list the voided day's file: it was read, disclosed, counted for nothing
    assert DAYS[2] in after["readings"]


def test_r115_ledger_refuses_on_s98(tmp_path):
    texts = {f"marks_{d}.jsonl": t for d, t in _five_days_text(None).items()}
    good = texts[f"marks_{DAYS[1]}.jsonl"]
    texts[f"marks_{DAYS[1]}.jsonl"] = good.splitlines()[0][:25] + "\n" + good
    vps = _vps(tmp_path, texts)
    with pytest.raises(AdapterError, match="S98"):
        led.ledger("2026-11-08", vps_dir=vps, promotions_path=tmp_path / "none.json", coins=["BTC"], first_day=DAYS[0])


def test_r117_a_pin_dated_2026_11_08_enters_only_the_ledgers_from_its_date(tmp_path):
    texts = {f"marks_{d}.jsonl": t for d, t in _five_days_text(None).items()}
    vps = _vps(tmp_path, texts)
    none = tmp_path / "none.json"
    # a re-pin of day 1 dated 11-08 with a worse book
    worse = "\n".join(_dumps(r) for r in [_row("F4:BTC", _day_ms(DAYS[0]), -500.0), _row("C1:BTC", _day_ms(DAYS[0]), -40.0)]) + "\n"
    (vps / f"marks_{DAYS[0]}_as_read_2026-11-08.jsonl").write_text(worse, encoding="utf-8")
    m07 = led.ledger("2026-11-07", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert m07["readings"][DAYS[0]] == f"marks_{DAYS[0]}.jsonl"                      # not admitted (R117)
    m08 = led.ledger("2026-11-08", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert m08["readings"][DAYS[0]] == f"marks_{DAYS[0]}_as_read_2026-11-08.jsonl"   # admitted from its date
    # a pin dated before 2026-11-08 keeps A23's admission (as-read <= as-of + 1)
    (vps / f"marks_{DAYS[0]}_as_read_2026-11-08.jsonl").rename(vps / f"marks_{DAYS[0]}_as_read_2026-11-05.jsonl")
    m04 = led.ledger("2026-11-04", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert m04["readings"][DAYS[0]] == f"marks_{DAYS[0]}_as_read_2026-11-05.jsonl"
    m03 = led.ledger("2026-11-03", vps_dir=vps, promotions_path=none, coins=["BTC"], first_day=DAYS[0])
    assert m03["readings"][DAYS[0]] == f"marks_{DAYS[0]}.jsonl"


def test_r117_the_ledger_as_of_2026_11_07_renders_a17_10s_markdown_byte_for_byte():
    """A ledger's points never move (A23): after A26's pins the as-of-11-07 ledger is A17.10's."""
    m = led.ledger("2026-11-07")
    md = (LEDGER / "ledger_2026-11-07.md").read_bytes().replace(b"\r\n", b"\n")
    assert led.render_markdown(m).encode("utf-8") == md
    assert "void_days_excluded" not in m and m["days"] == ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-07"]
