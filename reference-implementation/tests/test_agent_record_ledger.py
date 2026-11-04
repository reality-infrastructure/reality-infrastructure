"""PREREG A21 gates (P17): THE POPULATION LEDGER. Statuses by rule over the pinned marks
files (newest reading per day), the frozen marker and the promotions file; retirement after
seven days below both controls, sticky; promotion only from promotions.json (S95); the
as-of 11-03 ledger pinned and its known answer (six ALIVE, zero candidate, zero retired,
runs BTC 1 / SOL 1). Offline; no network, no clock.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rights_events import agent_ledger as led
from rights_events.adapters.common import AdapterError

LEDGER = led.LEDGER_DIR
PINS = {
    "ledger_2026-11-03.json": "bd3d23c87686e61f0f49a963e77a30c45ebbba4f4a3b2b33eb0f5dd057c29427",
    "ledger_2026-11-03.md": "ee2a77ba4a139ecda0a37b248af66b06f1cbef481314510d81e74acc8b712f0e",
}
DAYS = [f"2026-11-0{i}" for i in range(1, 9)]


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_ledger_outputs_pinned(name, sha):
    assert _lf_sha(LEDGER / name) == sha


def test_known_answer_as_of_2026_11_03():
    m = led.ledger("2026-11-03")
    assert m["days"] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert m["readings"]["2026-11-02"] == "marks_2026-11-02_as_read_2026-11-04.jsonl"   # the newest reading
    assert m["readings"]["2026-11-01"] == "marks_2026-11-01_as_read_2026-11-03.jsonl"
    assert m["n_alive_now"] == 6 and m["k"] == 5
    assert m["counts"] == {"ALIVE": 6, "CANDIDATE": 0, "PROMOTED": 0, "RETIRED": 0}
    runs = {r["fork"]: r["run_days"] for r in m["forks"]}
    assert runs == {"F4:BTC": 1, "F4:ETH": 0, "F4:HYPE": 0, "F4:ZEC": 0, "F4:SOL": 1, "F4:NEAR": 0}
    assert all(r["days_alive"] == 3 and r["rung"] == 0 and r["retired"] is None for r in m["forks"])
    assert m["pins"]["marker.py"].startswith("acf754f9")
    assert led.ledger_json(m).encode("utf-8") == (LEDGER / "ledger_2026-11-03.json").read_bytes().replace(b"\r\n", b"\n")
    assert led.render_markdown(m).encode("utf-8") == (LEDGER / "ledger_2026-11-03.md").read_bytes().replace(b"\r\n", b"\n")


def _row(fork: str, net: float, in_sample=False) -> str:
    fam, coin = fork.split(":", 1)
    return json.dumps({"fork": fork, "family": fam, "coin": coin, "net_bps": net, "gross_bps": net + 20,
                       "exit_reason": "gate", "in_sample": in_sample})


def _synthetic(tmp: Path, days=DAYS) -> Path:
    """Two forks: F4:AAA loses 50 bps on every episode (C1:AAA +1); F4:BBB makes 28/30/32 a
    day (C1:BBB -5). F3 and in-sample rows must be ignored."""
    vps = tmp / "vps"
    vps.mkdir()
    for d in days:
        lines = [_row("F4:AAA", -50.0), _row("F4:AAA", -50.0), _row("F4:AAA", -50.0), _row("C1:AAA", 1.0),
                 _row("F4:BBB", 28.0), _row("F4:BBB", 30.0), _row("F4:BBB", 32.0), _row("C1:BBB", -5.0),
                 _row("F4:AAA", 500.0, in_sample=True), json.dumps({"fork": "F3:AAA", "family": "F3", "coin": "AAA", "net_bps": 999.0})]
        (vps / f"marks_{d}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return vps


def test_synthetic_candidate_retirement_stickiness_and_k(tmp_path):
    vps = _synthetic(tmp_path)
    promo = tmp_path / "promotions.json"
    promo.write_text("[]", encoding="utf-8")
    # day 3: k_for(2) = 3; BBB's run is 3 and its mean clears 2σ/√n -> CANDIDATE; AAA alive (days < 7)
    m3 = led.ledger("2026-11-03", vps, promo, coins=["AAA", "BBB"])
    by = {r["fork"]: r for r in m3["forks"]}
    assert m3["k"] == 3 and by["F4:BBB"]["status"] == "CANDIDATE" and by["F4:BBB"]["run_days"] == 3
    assert by["F4:AAA"]["status"] == "ALIVE" and by["F4:AAA"]["episodes"] == 9      # in-sample and F3 ignored
    # day 6: still alive (6 < 7)
    m6 = led.ledger("2026-11-06", vps, promo, coins=["AAA", "BBB"])
    assert {r["fork"]: r["status"] for r in m6["forks"]}["F4:AAA"] == "ALIVE"
    # day 7: AAA retired (mean -50 + 0 < min(0, +1)); n_alive drops to 1 for the next day
    m7 = led.ledger("2026-11-07", vps, promo, coins=["AAA", "BBB"])
    a7 = {r["fork"]: r for r in m7["forks"]}["F4:AAA"]
    assert a7["status"] == "RETIRED" and a7["retired"]["day"] == "2026-11-07" and "R106" in a7["retired"]["reason"]
    assert m7["counts"] == {"ALIVE": 0, "CANDIDATE": 1, "PROMOTED": 0, "RETIRED": 1}
    assert m7["n_alive_now"] == 1
    # day 8: sticky; AAA's rows of day 8 are not read; k_for(1) = 2 for day 8
    m8 = led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"])
    a8 = {r["fork"]: r for r in m8["forks"]}["F4:AAA"]
    assert a8["status"] == "RETIRED" and a8["days_alive"] == 7 and a8["episodes"] == 18
    assert m8["k"] == 2 and m8["history"][-1]["n_alive_at_start"] == 1
    assert {r["fork"]: r for r in m8["forks"]}["F4:BBB"]["run_days"] == 8


def test_newest_reading_per_day_is_taken(tmp_path):
    vps = _synthetic(tmp_path, days=DAYS[:3])
    (vps / "marks_2026-11-02_as_read_2026-11-05.jsonl").write_text(
        (vps / "marks_2026-11-02.jsonl").read_text(encoding="utf-8") + _row("F4:BBB", 40.0) + "\n", encoding="utf-8")
    (vps / "marks_2026-11-02_as_read_2026-11-04.jsonl").write_text(
        (vps / "marks_2026-11-02.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    promo = tmp_path / "promotions.json"
    promo.write_text("[]", encoding="utf-8")
    m = led.ledger("2026-11-03", vps, promo, coins=["AAA", "BBB"])
    assert m["readings"]["2026-11-02"] == "marks_2026-11-02_as_read_2026-11-05.jsonl"
    assert {r["fork"]: r for r in m["forks"]}["F4:BBB"]["episodes"] == 10


def test_promotion_only_from_the_file_and_s95(tmp_path):
    vps = _synthetic(tmp_path)
    promo = tmp_path / "promotions.json"
    promo.write_text(json.dumps([{"fork": "F4:BBB", "rung": 1, "amendment": "A99", "date": "2026-11-04"}]), encoding="utf-8")
    m = led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"])
    b = {r["fork"]: r for r in m["forks"]}["F4:BBB"]
    assert b["status"] == "PROMOTED" and b["rung"] == 1 and b["promotion"]["amendment"] == "A99"
    # a promotion dated before the fork was ever CANDIDATE
    promo.write_text(json.dumps([{"fork": "F4:BBB", "rung": 1, "amendment": "A99", "date": "2026-11-02"}]), encoding="utf-8")
    with pytest.raises(AdapterError, match=r"S95: F4:BBB promoted on 2026-11-02 without being CANDIDATE"):
        led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"])
    # a promotion of a retired fork
    promo.write_text(json.dumps([{"fork": "F4:AAA", "rung": 1, "amendment": "A99", "date": "2026-11-08"}]), encoding="utf-8")
    with pytest.raises(AdapterError, match=r"S95: F4:AAA promoted on 2026-11-08 but RETIRED on 2026-11-07"):
        led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"])
    # a promotion dated after as_of is not yet in force
    promo.write_text(json.dumps([{"fork": "F4:BBB", "rung": 1, "amendment": "A99", "date": "2026-11-09"}]), encoding="utf-8")
    m = led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"])
    assert {r["fork"]: r for r in m["forks"]}["F4:BBB"]["status"] == "CANDIDATE"


def test_deterministic_reads_no_clock_and_the_cli(tmp_path, capsys):
    vps = _synthetic(tmp_path)
    promo = tmp_path / "promotions.json"
    promo.write_text("[]", encoding="utf-8")
    a = led.ledger_json(led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"]))
    b = led.ledger_json(led.ledger("2026-11-08", vps, promo, coins=["AAA", "BBB"]))
    assert a == b
    src = Path(led.__file__).read_text(encoding="utf-8")
    for banned in ("time.time(", "datetime.now(", "utcnow(", "import urllib", "import random",
                   "import socket", "import subprocess"):
        assert banned not in src
    rc = led.main(["--as-of", "2026-11-03", "--out-prefix", str(tmp_path / "ledger_x")])
    assert rc == 0 and (tmp_path / "ledger_x.json").exists() and (tmp_path / "ledger_x.md").exists()
    assert "n_alive 6, k 5" in capsys.readouterr().out
    rc = led.main(["--as-of", "11/03", "--out-prefix", str(tmp_path / "ledger_y")])
    assert rc == 1 and "LEDGER REFUSED" in capsys.readouterr().out
