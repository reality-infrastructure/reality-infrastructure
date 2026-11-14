"""RI-OPERATOR-3: the forecast journal's rules, and the five pre-registered known
answers (contracts/ri_operator/PREREG-3.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engine.errors import EventError
from engine.store import Engine
from packs.ri_operator import foresight as F

UTC = timezone.utc
D0 = datetime(2026, 1, 5, tzinfo=UTC)


class Clock:
    """A clock the test moves by hand; each read is one millisecond later, so order holds."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        self.at += timedelta(milliseconds=1)
        return self.at


def day(n: int) -> str:
    return (D0 + timedelta(days=n)).isoformat()


@pytest.fixture()
def j():
    clock = Clock(D0 - timedelta(days=1))
    engine = Engine.open("sqlite://:memory:", clock=clock)
    journal = F.Journal(engine)
    journal.clock = clock
    yield journal
    engine.close()


def _belief(j, key="pace"):
    return j.belief(key=key, statement="about 40 a day", because="last month's count", conf=0.6)


def _forecast(j, sheet="w1", metric="resolved", start=0, end=7, q=(30.0, 40.0, 50.0), **kw):
    kw.setdefault("beliefs", ("pace",))
    kw.setdefault("why", "same staffing as last month")
    kw.setdefault("premortem", "a holiday backlog doubles intake")
    return j.forecast(subject="desk-a", sheet=sheet, metric=metric, start=day(start), end=day(end), q=q, **kw)


def _week(j, n: int, actual: float, q=(30.0, 40.0, 50.0)):
    """Write week n's sheet before it opens, then settle it after it closes."""
    j.clock.at = D0 + timedelta(days=7 * n - 1)
    row = _forecast(j, sheet=f"w{n}", start=7 * n, end=7 * n + 7, q=q)
    j.clock.at = D0 + timedelta(days=7 * n + 7, hours=1)
    j.settle(fid=row["payload"]["fid"], actual=actual, evidence="python count.py")
    return row["payload"]["fid"]


# ---------------------------------------------------------------- known answers

def test_known_answer_1_a_forecast_written_inside_its_window_is_refused(j):
    _belief(j)
    j.clock.at = D0 + timedelta(days=2)
    with pytest.raises(EventError, match="opened"):
        _forecast(j)
    assert j.state()["forecasts"] == {}


def test_known_answer_2_a_sheet_where_everything_held_is_variance(j):
    _belief(j)
    fid = _week(j, 0, actual=41.0)
    assert j.state()["forecasts"][fid]["outcome"]["held"] is True
    with pytest.raises(EventError, match="held"):
        j.review(sheet="w0", cause="model", lesson="staffing matters")
    assert j.review(sheet="w0", cause="variance", lesson="nothing to change")["payload"]["outside"] == []


def test_known_answer_2_force_needs_evidence_and_is_recorded(j):
    _belief(j)
    _week(j, 0, actual=41.0)
    row = j.review(sheet="w0", cause="ops", lesson="the count ran late", force="scheduler log of 2026-01-12")
    assert row["payload"]["forced"] is True and row["payload"]["force_evidence"].startswith("scheduler")


def test_known_answer_3_a_belief_is_not_revised_on_one_sheet(j):
    _belief(j)
    _week(j, 0, actual=90.0)
    with pytest.raises(EventError, match="not flagged"):
        j.belief(key="pace", statement="about 90 a day", because="last week", conf=0.6, lesson="it doubled")
    _week(j, 1, actual=88.0)
    with pytest.raises(EventError, match="not flagged"):
        j.belief(key="pace", statement="about 90 a day", because="two weeks", conf=0.6, lesson="it doubled")
    _week(j, 2, actual=92.0)
    assert F.belief_record(j.state())["pace"]["flag"] == "REVISE"
    row = j.belief(key="pace", statement="about 90 a day", because="three weeks high", conf=0.6, lesson="it doubled")
    assert row["payload"]["version"] == 2 and row["payload"]["forced"] is False


def test_a_revision_always_carries_its_lesson(j):
    _belief(j)
    with pytest.raises(EventError, match="lesson"):
        j.belief(key="pace", statement="x", because="y", conf=0.5)


def test_known_answer_4_a_forecast_is_not_rewritten(j):
    _belief(j)
    _forecast(j)
    with pytest.raises(EventError, match="already written"):
        _forecast(j, q=(10.0, 20.0, 30.0))


def test_known_answer_5_the_score_of_10_20_30_against_35():
    s = F.score({"p": None, "lo": 10.0, "mid": 20.0, "hi": 30.0}, 35.0)
    assert s["held"] is False and s["error"] == 15.0
    assert s["interval_score"] == pytest.approx(70.0)
    assert round(s["bias"], 4) == 1.9223
    assert s["brier"] is None


# ---------------------------------------------------------------- the other rules

def test_probability_forecast_scores_by_brier(j):
    _belief(j)
    j.clock.at = D0 - timedelta(days=1)
    row = j.forecast(subject="desk-a", sheet="w1", metric="signed", start=day(0), end=day(7), p=0.2, op=">=", x=1.0,
                     beliefs=("pace",), why="one call booked", premortem="the call slips a week")
    j.clock.at = D0 + timedelta(days=8)
    out = j.settle(fid=row["payload"]["fid"], actual=0.0, evidence="ls clients")["payload"]
    assert out["event"] == 0.0 and out["brier"] == pytest.approx(0.04) and out["held"] is None


def test_interval_or_probability_never_both_never_neither(j):
    _belief(j)
    with pytest.raises(EventError, match="one of them"):
        j.forecast(subject="s", sheet="w1", metric="m", start=day(0), end=day(7), beliefs=("pace",), why="w", premortem="p")
    with pytest.raises(EventError, match="one of them"):
        j.forecast(subject="s", sheet="w1", metric="m", start=day(0), end=day(7), q=(1.0, 2.0, 3.0), p=0.5, op=">", x=1.0,
                   beliefs=("pace",), why="w", premortem="p")
    with pytest.raises(EventError, match="out of order"):
        _forecast(j, q=(50.0, 40.0, 30.0))


def test_a_forecast_names_beliefs_reason_and_failure(j):
    _belief(j)
    with pytest.raises(EventError, match="names the beliefs"):
        _forecast(j, premortem="")
    with pytest.raises(EventError, match="no belief"):
        _forecast(j, beliefs=("never-written",))


def test_written_after_the_window_closed_is_hindsight_and_never_counts(j):
    _belief(j)
    j.clock.at = D0 + timedelta(days=9)
    row = _forecast(j)
    assert row["payload"]["hindsight"] is True
    j.settle(fid=row["payload"]["fid"], actual=90.0, evidence="python count.py")
    assert F.calibration(F._scored(j.state()))["intervals"] == 0
    assert "pace" not in F.belief_record(j.state())


def test_nothing_is_settled_before_its_window_closes_or_twice_or_without_evidence(j):
    _belief(j)
    fid = _forecast(j)["payload"]["fid"]
    j.clock.at = D0 + timedelta(days=3)
    with pytest.raises(EventError, match="before it closes"):
        j.settle(fid=fid, actual=40.0, evidence="python count.py")
    j.clock.at = D0 + timedelta(days=8)
    with pytest.raises(EventError, match="where the number was read"):
        j.settle(fid=fid, actual=40.0, evidence="  ")
    j.settle(fid=fid, actual=40.0, evidence="python count.py")
    with pytest.raises(EventError, match="already scored"):
        j.settle(fid=fid, actual=41.0, evidence="python count.py")


def test_the_record_becomes_a_rival_after_five_like_windows(j):
    _belief(j)
    for n, actual in enumerate([38.0, 44.0, 41.0, 47.0]):
        _week(j, n, actual)
    args = dict(subject="desk-a", sheet="w5", metric="resolved", start=day(35), end=day(42))
    assert j.persist(**args) is None and j.like_windows("desk-a", "resolved", day(35), day(42)) == 4
    _week(j, 4, 40.0)
    row = j.persist(**args)["payload"]
    assert row["author"] == "persistence" and (row["lo"], row["mid"], row["hi"]) == (38.8, 41.0, 45.8)


def test_skill_compares_the_author_with_the_record_on_the_same_window(j):
    _belief(j)
    for n, actual in enumerate([38.0, 44.0, 41.0, 47.0, 40.0]):
        _week(j, n, actual)
    j.clock.at = D0 + timedelta(days=34)
    j.persist(subject="desk-a", sheet="w5", metric="resolved", start=day(35), end=day(42))
    wide = _forecast(j, sheet="w5", start=35, end=42, q=(10.0, 40.0, 70.0))["payload"]["fid"]
    j.clock.at = D0 + timedelta(days=43)
    for fid in (wide, "w5/persistence/resolved"):
        j.settle(fid=fid, actual=42.0, evidence="python count.py")
    s, n = F.skill(j.state(), "desk", "persistence")
    assert n == 1 and s == pytest.approx(1 - 60.0 / 7.0)


def test_report_lists_what_is_owed(j):
    _belief(j)
    fid = _forecast(j)["payload"]["fid"]
    j.clock.at = D0 + timedelta(days=8)
    assert "SETTLEMENT OWED: sheet w1: resolved" in j.report()
    j.settle(fid=fid, actual=75.0, evidence="python count.py")
    text = j.report("desk-a")
    assert "REVIEW OWED: sheet w1" in text and "held 0%" in text and "pace v1" in text
    j.review(sheet="w1", cause="regime", lesson="intake doubled after the launch of 2026-01-07")
    assert "OWED: nothing" in j.report()


def test_every_journal_event_is_on_the_ledger_and_verifies(j):
    _belief(j)
    _week(j, 0, 90.0)
    j.review(sheet="w0", cause="model", lesson="pace was wrong")
    events = j.events()
    assert [e["event_type"].split(".")[1] for e in events] == [
        "belief_stated", "forecast_written", "forecast_settled", "sheet_reviewed"]
    for e in events:
        j.engine.ledger.verify_row(e)


def test_cli_refuses_with_exit_2_and_writes_nothing(tmp_path, capsys):
    db = f"sqlite:///{(tmp_path / 'f.sqlite3').as_posix()}"
    assert F.main(["--db", db, "belief", "--key", "pace", "--statement", "s", "--because", "b", "--conf", "0.5"]) == 0
    assert F.main(["--db", db, "forecast", "--subject", "s", "--sheet", "w1", "--metric", "m",
                   "--start", "2000-01-01T00:00:00+00:00", "--end", "2100-01-01T00:00:00+00:00",
                   "--q=-5,0,5", "--beliefs", "pace", "--why", "w", "--premortem", "p"]) == 2
    assert "REFUSED" in capsys.readouterr().out
    assert F.main(["--db", db, "report"]) == 0
    assert "OPEN: 0" in capsys.readouterr().out
