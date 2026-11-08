"""A28 / P22 gates: THE COPIER'S GRADE (the feed).

R118  a pure function of the newest pinned arena and screen outputs per cohort; S99 refusals; no network / clock
R119  KEEP / DROP / UNDECIDED on completed windows, OPEN otherwise, Decimal on the arena's strings
R120  the run across listings: KEEP +1, DROP 0, UNDECIDED unchanged; completed windows only
R121  displayed pnl at listing beside verified net; screen verdict and letters; paper rows never appear
R122  feed_latest.json byte-equal to the newest dated file (S100)
Known answers on the real pins: cohort 2026-10-25 KEEP 6 / DROP 51 / UNDECIDED 23 (+ the record row KEEP),
cohort 2026-11-03 all OPEN, 51 addresses in both, runs 1 for the six KEEP addresses.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rights_events import arena_feed as af
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_FEED_SRC = _ROOT / "rights_events" / "arena_feed.py"


def _arena(cohort, as_of, t0, t1, complete, rows, record=None, paper=None, root="ab" * 32):
    return {"kind": "proof_of_outcome_arena", "cohort_date": cohort, "as_of": as_of,
            "window": {"t0_date": t0, "t1_date": t1, "complete": complete, "started": True},
            "venue": {"name": "test boards"}, "counts": {}, "rows": rows, "record_row": record, "paper_rows": paper or [],
            "settled_rule": "SETTLED.md: test", "arena_run": {"file": f"run_ARENA_{cohort}_{as_of}.ri", "root": root}}


def _row(addr, coverage, net, fills=3, displayed="1000.5", rank=None, record=False):
    r = {"status": "RECORD" if record else coverage, "rank": rank, "address": addr,
         "displayed_at_observation": {"week": {"rank": 1, "pnl": displayed}} if displayed is not None else {},
         "fills": fills, "fills_served": fills, "realized_ex_funding": net, "funding": "0", "net_with_funding": net,
         "open_at_window_end": {"BTC": "1.0"} if fills else {}, "first_tx": "0x1", "last_tx": "0x2",
         "coverage_reason": f"{coverage} reason"}
    if record:
        r["coverage"] = coverage
    return r


def _screen(cohort, as_of, arena_path: Path, rows):
    return {"kind": "screen", "cohort_date": cohort, "as_of": as_of, "arena_file": arena_path.name,
            "arena_sha256": hashlib.sha256(arena_path.read_bytes()).hexdigest(), "counts": {}, "rows": rows}


def _write(tmp: Path, cohort: str, arena: dict, screen_rows=None) -> Path:
    d = tmp / "arena" / cohort
    d.mkdir(parents=True, exist_ok=True)
    ap = d / f"arena_{cohort}_{arena['as_of']}.json"
    ap.write_text(json.dumps(arena), encoding="utf-8")
    if screen_rows is not None:
        (d / f"screen_{cohort}_{arena['as_of']}.json").write_text(json.dumps(_screen(cohort, arena["as_of"], ap, screen_rows)), encoding="utf-8")
    return ap


def _settled(tmp: Path) -> Path:
    p = tmp / "SETTLED.md"
    p.write_text("# settled\n", encoding="utf-8")
    return p


def test_r119_statuses_on_a_complete_and_an_open_window(tmp_path):
    rows = [_row("0xa", "FULL", "12.5"), _row("0xb", "FULL", "0"), _row("0xc", "NONE", "0", fills=0),
            _row("0xd", "PARTIAL", "99.0"), _row("0xe", "FULL", "-3.25")]
    _write(tmp_path, "2026-10-01", _arena("2026-10-01", "2026-10-10", "2026-10-02", "2026-10-09", True, rows,
                                           record=_row("0xrec", "FULL", "0.07", fills=4, record=True),
                                           paper=[{"status": "PAPER", "fork": "C1:BTC"}]))
    _write(tmp_path, "2026-10-11", _arena("2026-10-11", "2026-10-15", "2026-10-12", "2026-10-19", False,
                                           [_row("0xa", "FULL", "5"), _row("0xf", "NONE", "0", fills=0)]))
    m = af.feed("2026-10-15", tmp_path / "arena", _settled(tmp_path))
    st = {(r["cohort_date"], r["address"]): r["status"] for r in m["rows"]}
    assert st[("2026-10-01", "0xa")] == "KEEP" and st[("2026-10-01", "0xb")] == "DROP" and st[("2026-10-01", "0xc")] == "DROP"
    assert st[("2026-10-01", "0xd")] == "UNDECIDED" and st[("2026-10-01", "0xe")] == "DROP" and st[("2026-10-01", "0xrec")] == "KEEP"
    assert st[("2026-10-11", "0xa")] == "OPEN" and st[("2026-10-11", "0xf")] == "OPEN"
    c1, c2 = m["cohorts"]
    assert c1["counts"] == {"KEEP": 2, "DROP": 3, "UNDECIDED": 1, "OPEN": 0} and c2["counts"]["OPEN"] == 2
    rec = next(r for r in m["rows"] if r["record"])
    assert rec["address"] == "0xrec" and rec["coverage"] == "FULL"
    assert not any(r.get("address") is None for r in m["rows"])          # paper rows never appear
    # R121: what stands beside the grade
    a = next(r for r in m["rows"] if r["address"] == "0xa" and r["cohort_date"] == "2026-10-01")
    assert a["displayed_pnl_at_listing"] == "1000.5" and a["displayed_window"] == "week" and a["verified_net"] == "12.5"
    assert a["fills"] == 3 and a["first_tx"] == "0x1" and a["open_positions_at_window_end"] == 1
    assert a["screen_verdict"] == "not screened"
    b = next(r for r in m["rows"] if r["address"] == "0xa" and r["cohort_date"] == "2026-10-11")
    assert b["screen_verdict"] == "not screened (window open until 2026-10-19)"


def test_r120_run_across_listings(tmp_path):
    cohorts = [("2026-09-01", "2026-09-09", "KEEP"), ("2026-09-11", "2026-09-19", "UNDECIDED"), ("2026-09-21", "2026-09-29", "KEEP"),
               ("2026-10-01", "2026-10-09", "DROP"), ("2026-10-11", "2026-10-19", "KEEP"), ("2026-10-21", "2026-10-29", "OPEN")]
    for c, t1, want in cohorts:
        cov, net = {"KEEP": ("FULL", "1"), "UNDECIDED": ("PARTIAL", "1"), "DROP": ("NONE", "0"), "OPEN": ("FULL", "1")}[want]
        _write(tmp_path, c, _arena(c, "2026-10-30", c, t1, want != "OPEN", [_row("0xa", cov, net, fills=0 if cov == "NONE" else 2)]))
    m = af.feed("2026-10-30", tmp_path / "arena", _settled(tmp_path))
    r = m["runs"]["0xa"]
    assert r["cohorts_listed"] == 6 and r["cohorts_completed"] == 5
    assert r["run"] == 1                                   # KEEP, UNDECIDED(=), KEEP -> 2; DROP -> 0; KEEP -> 1; OPEN ignored
    assert [r["statuses"][c] for c, _, _ in cohorts] == ["KEEP", "UNDECIDED", "KEEP", "DROP", "KEEP", "OPEN"]
    # the first three alone -> 2
    for c, _, _ in cohorts[3:]:
        for p in (tmp_path / "arena" / c).iterdir():
            p.unlink()
        (tmp_path / "arena" / c).rmdir()
    m2 = af.feed("2026-10-30", tmp_path / "arena", _settled(tmp_path))
    assert m2["runs"]["0xa"]["run"] == 2


def test_s99_refusals_and_nothing_written(tmp_path, capsys):
    rows = [_row("0xa", "FULL", "1")]
    ap = _write(tmp_path, "2026-10-01", _arena("2026-10-01", "2026-10-10", "2026-10-02", "2026-10-09", True, rows), screen_rows=[{"address": "0xa", "verdict": "REFUSED", "fails": ["D"]}])
    s = _settled(tmp_path)
    ok = af.feed("2026-10-10", tmp_path / "arena", s)
    assert ok["rows"][0]["screen_verdict"] == "REFUSED" and ok["rows"][0]["screen_fails"] == ["D"]
    # the feed's as-of earlier than the arena's -> S99
    with pytest.raises(AdapterError, match="S99"):
        af.feed("2026-10-09", tmp_path / "arena", s)
    # a screen whose arena sha mismatches -> S99 (the arena file is re-written with a space)
    ap.write_text(ap.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(AdapterError, match="S99"):
        af.feed("2026-10-10", tmp_path / "arena", s)
    # the CLI: REFUSED, exit 1, nothing written
    out = tmp_path / "feed_out"
    rc = af.main(["--as-of", "2026-10-10", "--arena-dir", str(tmp_path / "arena"), "--out-dir", str(out), "--settled", str(s)])
    assert rc == 1 and "FEED REFUSED" in capsys.readouterr().out and not out.exists()
    # no settled_rule -> S99
    a = json.loads(ap.read_text(encoding="utf-8").strip())
    a.pop("settled_rule")
    ap.write_text(json.dumps(a), encoding="utf-8")
    (tmp_path / "arena" / "2026-10-01" / "screen_2026-10-01_2026-10-10.json").unlink()
    with pytest.raises(AdapterError, match="settled_rule"):
        af.feed("2026-10-10", tmp_path / "arena", s)


def test_r122_write_latest_and_s100(tmp_path, capsys):
    _write(tmp_path, "2026-10-01", _arena("2026-10-01", "2026-10-10", "2026-10-02", "2026-10-09", True, [_row("0xa", "FULL", "1")]))
    s = _settled(tmp_path)
    out = tmp_path / "feed"
    rc = af.main(["--as-of", "2026-10-10", "--arena-dir", str(tmp_path / "arena"), "--out-dir", str(out), "--settled", str(s)])
    assert rc == 0 and "COPIER'S GRADE as of 2026-10-10" in capsys.readouterr().out
    assert (out / "feed_2026-10-10.json").read_bytes() == (out / "feed_latest.json").read_bytes()
    assert af.check_latest(out) == "feed_2026-10-10.json"
    md = (out / "feed_2026-10-10.md").read_text(encoding="utf-8")
    assert "KEEP 1 / DROP 0 / UNDECIDED 0 / OPEN 0" in md and "`0xa`" in md
    (out / "feed_latest.json").write_bytes(b"{}\n")
    with pytest.raises(AdapterError, match="S100"):
        af.check_latest(out)
    html = af.render_html_section(json.loads((out / "feed_2026-10-10.json").read_text(encoding="utf-8")))
    assert 'id="copiers-grade"' in html and "0xa" in html and "<script" not in html


def test_r118_no_network_clock_or_randomness():
    src = _FEED_SRC.read_text(encoding="utf-8")
    for banned in ("urllib", "socket", "requests", "http.client", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert banned not in src, banned


# --- the real pins -------------------------------------------------------------------------------

def test_known_answers_on_the_pinned_arena_outputs():
    m = af.feed("2026-11-07")
    assert m["settled_sha256"] == "c6b590de2289de698053a203e22941bafd55e558f0d5947ac8a4b40274042878"
    by = {c["cohort_date"]: c for c in m["cohorts"]}
    c1 = by["2026-10-25"]
    assert c1["arena_file"] == "arena_2026-10-25_2026-11-03.json" and c1["window"]["complete"] is True
    assert c1["coverage_counts"] == {"FULL": 8, "PARTIAL": 23, "NONE": 49, "REFUSED": 0}
    assert c1["counts"] == {"KEEP": 7, "DROP": 51, "UNDECIDED": 23, "OPEN": 0}        # 6 listed + the record row
    assert c1["screen"]["file"] == "screen_2026-10-25_2026-11-03.json"
    keep = sorted(r["address"][:10] for r in m["rows"] if r["cohort_date"] == "2026-10-25" and r["status"] == "KEEP" and not r["record"])
    assert keep == sorted(["0x4c6d679e", "0xfc667adb", "0xf818fa41", "0x856c3503", "0x484bc160", "0x9794bbbc"])
    rec = next(r for r in m["rows"] if r["cohort_date"] == "2026-10-25" and r["record"])
    assert rec["address"] == "0x9f976123e7c48952be487664b8130aad144b7f23" and rec["status"] == "KEEP" and rec["verified_net"] == "0.073533" and rec["fills"] == 4
    top = next(r for r in m["rows"] if r["address"].startswith("0x9794bbbc") and r["cohort_date"] == "2026-10-25")
    assert top["displayed_pnl_at_listing"] == "144136485.6583960056" and top["verified_net"] == "7.87137595" and top["fills"] == 1
    first = next(r for r in m["rows"] if r["address"].startswith("0x4c6d679e") and r["cohort_date"] == "2026-10-25")
    assert first["screen_verdict"] == "REFUSED" and first["screen_fails"] == ["D", "G", "H"] and first["run"] == 1
    drops = [r for r in m["rows"] if r["cohort_date"] == "2026-10-25" and r["status"] == "DROP"]
    assert sum(1 for r in drops if r["coverage"] == "FULL") == 2 and sum(1 for r in drops if r["coverage"] == "NONE") == 49
    c2 = by["2026-11-03"]
    assert c2["window"]["complete"] is False and c2["counts"]["OPEN"] == c2["rows"] == 70 and c2["screen"] is None
    assert c2["coverage_counts"] == {"FULL": 27, "PARTIAL": 1, "NONE": 41, "REFUSED": 0}
    open_row = next(r for r in m["rows"] if r["cohort_date"] == "2026-11-03" and not r["record"])
    assert open_row["screen_verdict"] == "not screened (window open until 2026-11-10)"
    both = {a for a, v in m["runs"].items() if v["cohorts_listed"] == 2}
    assert len(both) == 51 + (1 if m["runs"]["0x9f976123e7c48952be487664b8130aad144b7f23"]["cohorts_listed"] == 2 else 0)
    assert all(v["run"] == (1 if v["statuses"].get("2026-10-25") == "KEEP" else 0) for v in m["runs"].values())
    assert sum(1 for v in m["runs"].values() if v["run"] == 1) == 7


def test_feed_latest_is_the_newest_dated_pin():
    """R122 / S100 on the committed feed directory (present from A28.1 on)."""
    if not af.FEED_DIR.exists():
        pytest.skip("no feed committed yet")
    name = af.check_latest(af.FEED_DIR)
    m = json.loads((af.FEED_DIR / name).read_text(encoding="utf-8"))
    assert m["kind"] == af.FEED_KIND and af.feed_json(af.feed(m["as_of"])) == (af.FEED_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
