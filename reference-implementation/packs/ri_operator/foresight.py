"""The forecast journal: what was expected, written before the window opened, scored
against what happened, and the beliefs behind it revised only when the record says to.

    python -m packs.ri_operator.foresight belief   --key K --statement S --because B --conf 0.6 [--lesson L] [--force EVIDENCE]
    python -m packs.ri_operator.foresight forecast --subject S --sheet SH --metric M --start ISO --end ISO
                                                   (--q=lo,mid,hi | --p 0.3 --op ">=" --x 1)
                                                   [--author desk] [--beliefs k1,k2] [--why W] [--premortem P]
    python -m packs.ri_operator.foresight persist  --subject S --sheet SH --metric M --start ISO --end ISO
    python -m packs.ri_operator.foresight settle   --fid FID --actual N --evidence "command or file the number was read from"
    python -m packs.ri_operator.foresight review   --sheet SH --cause C --lesson L [--force EVIDENCE]
    python -m packs.ri_operator.foresight report   [--subject S]

Every write is one event on the pack's ledger; nothing here keeps state of its own.
The journal's state is derived from the events each time, in ledger order.

Exit codes: 0 done, 2 refused (a rule of the journal, or the event schema), 1 usage or engine error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from engine.errors import EngineError, EventError
from engine.events import EventLog
from engine.packs import load_pack
from engine.runtime import iso, parse_iso
from engine.store import Engine

PACK = "ri_operator"
ALPHA = 0.2                  # 80 percent intervals; a miss outside costs 2 / ALPHA per unit
Z80 = 2.5631031              # width of an 80 percent interval, in standard deviations
MIN_PERSIST = 5              # like windows on the record before the record is a rival
CAUSES = ("variance", "model", "overfit", "execution", "ops", "regime", "data")
MECHANICAL = ("baseline", "persistence")   # built only from records that end before the window
OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
TYPES = ("belief_stated", "forecast_written", "forecast_settled", "sheet_reviewed")


class Refused(EventError):
    """A rule of the journal said no.  Nothing was written."""


# ------------------------------------------------------------------ pure ---

def score(f: dict, actual: float) -> dict:
    """The outcome of one forecast.  Pure: the same forecast and actual give the same score."""
    out = {"held": None, "error": None, "bias": None, "interval_score": None, "event": None, "brier": None}
    if f.get("p") is not None:
        hit = 1.0 if OPS[f["op"]](actual, f["x"]) else 0.0
        out.update(event=hit, brier=(f["p"] - hit) ** 2)
        return out
    lo, mid, hi = f["lo"], f["mid"], f["hi"]
    out["error"] = actual - mid
    if lo is None or hi is None:     # a point stated without a range earns only its error
        return out
    width = hi - lo
    out["held"] = bool(lo <= actual <= hi)
    out["bias"] = (actual - mid) / (width / Z80) if width > 0 else 0.0
    out["interval_score"] = width + (2 / ALPHA) * max(lo - actual, 0.0) + (2 / ALPHA) * max(actual - hi, 0.0)
    return out


def quantile(values: list[float], q: float) -> float:
    """Linear interpolation between order statistics."""
    xs = sorted(values)
    if not xs:
        raise ValueError("quantile of nothing")
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def state(events: list[dict]) -> dict:
    """Beliefs, forecasts with their outcomes, and reviews, from events in ledger order."""
    st = {"beliefs": {}, "forecasts": {}, "reviews": {}}
    for e in events:
        kind, body = e["event_type"].split(".", 1)[1], e["payload"]
        if kind == "belief_stated":
            st["beliefs"].setdefault(body["key"], []).append(body)
        elif kind == "forecast_written":
            st["forecasts"][body["fid"]] = dict(body, written_at=e["observed_at"])
        elif kind == "forecast_settled" and body["fid"] in st["forecasts"]:
            st["forecasts"][body["fid"]]["outcome"] = body
        elif kind == "sheet_reviewed":
            st["reviews"].setdefault(body["sheet"], []).append(body)
    return st


def _scored(st: dict, *, author: str | None = None, hindsight: bool = False) -> list[dict]:
    return [f for f in st["forecasts"].values() if "outcome" in f and f["hindsight"] == hindsight
            and (author is None or f["author"] == author)]


def belief_record(st: dict) -> dict:
    """Each belief's record over the scored foresight forecasts that cited it, any human author."""
    rec: dict[str, dict] = {}
    for f in _scored(st):
        if f["author"] in MECHANICAL:
            continue
        o = f["outcome"]
        for cited in f["beliefs"]:
            r = rec.setdefault(cited.split("@")[0], {"n": 0, "held": 0, "bias": 0.0, "cited": 0})
            r["cited"] += 1
            if o["held"] is not None:
                r["n"] += 1
                r["held"] += int(o["held"])
                r["bias"] += o["bias"]
    for r in rec.values():
        r["flag"] = ("REVISE" if r["n"] >= 3 and abs(r["bias"] / r["n"]) > 1.0
                     else "TOO NARROW" if r["n"] >= 5 and r["held"] / r["n"] < 0.5 else "")
    return rec


def calibration(forecasts: list[dict]) -> dict:
    iv = [f["outcome"] for f in forecasts if f["outcome"]["held"] is not None]
    pr = [f["outcome"] for f in forecasts if f["outcome"]["brier"] is not None]
    return {"intervals": len(iv),
            "coverage": sum(o["held"] for o in iv) / len(iv) if iv else None,
            "bias": sum(o["bias"] for o in iv) / len(iv) if iv else None,
            "probabilities": len(pr),
            "brier": sum(o["brier"] for o in pr) / len(pr) if pr else None}


def skill(st: dict, author: str, rival: str) -> tuple[float | None, int]:
    """1 - the author's mean interval score over the rival's, on forecasts both made.
    Positive: the author's interval was the better one."""
    ratios = []
    for f in _scored(st, author=author):
        r = st["forecasts"].get(f["fid"].replace(f"/{author}/", f"/{rival}/"))
        a = f["outcome"]["interval_score"]
        b = (r or {}).get("outcome", {}).get("interval_score")
        if a is not None and b:
            ratios.append(a / b)
    return (1 - sum(ratios) / len(ratios) if ratios else None), len(ratios)


def sheet_outside(st: dict, sheet: str) -> tuple[list[dict], list[str]]:
    """A sheet's scored forecasts by human authors, and the metrics that fell outside."""
    fs = [f for f in st["forecasts"].values()
          if f["sheet"] == sheet and f["author"] not in MECHANICAL and "outcome" in f]
    outside = [f["metric"] for f in fs
               if f["outcome"]["held"] is False or (f["outcome"]["brier"] is not None and f["outcome"]["brier"] > 0.25)]
    return fs, outside


def owed(st: dict, now: datetime) -> list[str]:
    out = []
    sheets: dict[str, list[dict]] = {}
    for f in st["forecasts"].values():
        if f["author"] not in MECHANICAL:
            sheets.setdefault(f["sheet"], []).append(f)
    for name, fs in sorted(sheets.items()):
        due = [f for f in fs if "outcome" not in f and parse_iso(f["window_end"]) <= now]
        if due:
            out.append(f"SETTLEMENT OWED: sheet {name}: " + ", ".join(sorted(f["metric"] for f in due)))
        elif all("outcome" in f for f in fs) and name not in st["reviews"]:
            out.append(f"REVIEW OWED: sheet {name} is scored and has no lesson")
    for key, r in sorted(belief_record(st).items()):
        if r["flag"]:
            out.append(f"BELIEF {r['flag']}: {key} (n={r['n']}, held {r['held']}, mean bias {r['bias'] / r['n']:+.2f})")
    return out


# ------------------------------------------------------------- the journal ---

class Journal:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.log = EventLog(engine, load_pack(PACK))

    def events(self) -> list[dict]:
        rows = []
        for t in TYPES:
            rows += self.log.query(event_type=f"{PACK}.{t}", limit=1_000_000, ascending=True)
        return sorted(rows, key=lambda r: r["ledger_index"])

    def state(self) -> dict:
        return state(self.events())

    def _append(self, kind: str, subject: str, payload: dict, source: str) -> dict:
        return self.log.append(entity_type="system", entity_id=subject, event_type=f"{PACK}.{kind}",
                               payload=payload, source=source)

    # -- beliefs --------------------------------------------------------------

    def belief(self, *, key: str, statement: str, because: str, conf: float, lesson: str = "",
               force: str | None = None, subject: str = "journal", source: str = "agent:ri-foresight") -> dict:
        st = self.state()
        prior = st["beliefs"].get(key, [])
        if prior:
            if not lesson:
                raise Refused(f"{key} exists at v{len(prior)}; a revision carries the lesson that caused it")
            r = belief_record(st).get(key, {"n": 0, "flag": ""})
            if not r["flag"] and not force:
                raise Refused(
                    f"{key} is not flagged by its own record (n={r['n']} scored interval forecasts; REVISE needs 3 "
                    "leaning one way, TOO NARROW needs 5 with under half held). A belief is not revised on one "
                    "sheet. Pass --force with evidence from outside the record, or wait.")
        return self._append("belief_stated", subject, {
            "key": key, "version": len(prior) + 1, "statement": statement, "because": because,
            "confidence": conf, "lesson": lesson, "forced": bool(force), "force_evidence": force or None}, source)

    # -- forecasts ------------------------------------------------------------

    def forecast(self, *, subject: str, sheet: str, metric: str, start: str, end: str, author: str = "desk",
                 q: tuple | None = None, p: float | None = None, op: str | None = None, x: float | None = None,
                 beliefs: tuple = (), why: str = "", premortem: str = "",
                 source: str = "agent:ri-foresight") -> dict:
        now = self.engine.clock.now()
        t0, t1 = parse_iso(start), parse_iso(end)
        if not t0 < t1:
            raise Refused("a window ends after it starts")
        if (q is None) == (p is None):
            raise Refused("a forecast is an interval (q) or a probability (p, op, x), one of them")
        if q is not None and None not in q and not q[0] <= q[1] <= q[2]:
            raise Refused(f"{metric}: quantiles out of order: {list(q)}")
        if p is not None and (op not in OPS or x is None or not 0.0 <= p <= 1.0):
            raise Refused("a probability needs op, x and 0 <= p <= 1")
        human = author not in MECHANICAL
        hindsight = now >= t1
        if human and not hindsight and not (why and premortem and beliefs):
            raise Refused("a forecast names the beliefs it rests on, its reason, and the way it fails")
        st = self.state()
        cited = []
        for k in beliefs:
            if k not in st["beliefs"]:
                raise Refused(f"no belief {k!r}; write it first")
            cited.append(f"{k}@{len(st['beliefs'][k])}")
        # The pen is put down when the window opens.  A mechanical author uses only records that end
        # before the window; anyone else writing inside it has seen part of the answer.
        if t0 <= now < t1 and human:
            raise Refused(f"the window of {sheet}/{metric} opened {iso(t0)}; {author!r} writes before it opens, "
                          "or after it closes as an entry made in hindsight")
        fid = f"{sheet}/{author}/{metric}" + (f"{op}{x:g}" if p is not None else "")
        if fid in st["forecasts"]:
            raise Refused(f"{fid} is already written; a forecast is not rewritten")
        lo, mid, hi = q if q is not None else (None, None, None)
        return self._append("forecast_written", subject, {
            "fid": fid, "sheet": sheet, "subject": subject, "author": author, "metric": metric,
            "window_start": iso(t0), "window_end": iso(t1), "lo": lo, "mid": mid, "hi": hi,
            "p": p, "op": op, "x": x, "beliefs": cited, "why": why, "premortem": premortem,
            "hindsight": hindsight}, source)

    def persist(self, *, subject: str, sheet: str, metric: str, start: str, end: str) -> dict | None:
        """The record as a forecaster: the 10 / 50 / 90 of this metric's settled actuals over earlier
        windows of the same length.  None until MIN_PERSIST of them exist."""
        t0, t1 = parse_iso(start), parse_iso(end)
        span, seen = t1 - t0, {}
        for f in self.state()["forecasts"].values():
            if (f["subject"], f["metric"]) != (subject, metric) or "outcome" not in f:
                continue
            w0, w1 = parse_iso(f["window_start"]), parse_iso(f["window_end"])
            if w1 <= t0 and w1 - w0 == span:
                seen[(w0, w1)] = f["outcome"]["actual"]
        if len(seen) < MIN_PERSIST:
            return None
        vals = list(seen.values())
        return self.forecast(subject=subject, sheet=sheet, metric=metric, start=start, end=end,
                             author="persistence", q=(quantile(vals, 0.1), quantile(vals, 0.5), quantile(vals, 0.9)),
                             source="pipeline:persistence")

    def like_windows(self, subject: str, metric: str, start: str, end: str) -> int:
        t0, t1 = parse_iso(start), parse_iso(end)
        return len({(f["window_start"], f["window_end"]) for f in self.state()["forecasts"].values()
                    if (f["subject"], f["metric"]) == (subject, metric) and "outcome" in f
                    and parse_iso(f["window_end"]) <= t0
                    and parse_iso(f["window_end"]) - parse_iso(f["window_start"]) == t1 - t0})

    # -- outcomes -------------------------------------------------------------

    def settle(self, *, fid: str, actual: float, evidence: str, source: str = "agent:ri-foresight") -> dict:
        f = self.state()["forecasts"].get(fid)
        if f is None:
            raise Refused(f"no forecast {fid!r}")
        if "outcome" in f:
            raise Refused(f"{fid} is already scored; an outcome is not rewritten")
        if not evidence or not evidence.strip():
            raise Refused("an outcome says where the number was read")
        if self.engine.clock.now() < parse_iso(f["window_end"]):
            raise Refused(f"the window of {fid} closes {f['window_end']}; nothing is scored before it closes")
        return self._append("forecast_settled", f["subject"],
                            dict(score(f, actual), fid=fid, actual=actual, evidence=evidence.strip()), source)

    def review(self, *, sheet: str, cause: str, lesson: str, force: str | None = None,
               source: str = "agent:ri-foresight") -> dict:
        if cause not in CAUSES:
            raise Refused(f"cause is one of {', '.join(CAUSES)}")
        st = self.state()
        fs, outside = sheet_outside(st, sheet)
        if not fs:
            raise Refused(f"sheet {sheet!r} has no scored forecast to review")
        live = [f for f in fs if not f["hindsight"]]
        if live and not outside and cause != "variance" and not force:
            raise Refused("every forecast on this sheet held. That is the model working; a lesson drawn from it is "
                          "judging by the result. Review it as `variance`, or pass --force with what other evidence there is.")
        return self._append("sheet_reviewed", fs[0]["subject"], {
            "sheet": sheet, "cause": cause, "lesson": lesson, "outside": sorted(outside),
            "forced": bool(force), "force_evidence": force or None}, source)

    # -- reading --------------------------------------------------------------

    def report(self, subject: str | None = None) -> str:
        st = self.state()
        if subject:
            st["forecasts"] = {k: f for k, f in st["forecasts"].items() if f["subject"] == subject}
        now = self.engine.clock.now()
        lines = [f"FORESIGHT at {iso(now)}" + (f"  subject {subject}" if subject else "")]
        o = owed(st, now)
        lines += ["OWED"] + [f"  {x}" for x in o] if o else ["OWED: nothing"]
        open_ = sorted((f for f in st["forecasts"].values() if "outcome" not in f), key=lambda f: f["window_end"])
        lines.append(f"OPEN: {len(open_)}")
        for f in open_:
            what = (f"P({f['metric']} {f['op']} {f['x']:g}) = {f['p']:g}" if f["p"] is not None
                    else f"{f['metric']} {f['lo']} / {f['mid']} / {f['hi']}")
            lines.append(f"  {f['fid']}: {what}  closes {f['window_end'][:16]}")
        human = [f for f in _scored(st) if f["author"] not in MECHANICAL]
        c = calibration(human)
        lines.append(f"SCORED: {len(human)} forecasts written ahead"
                     + (f"; intervals {c['intervals']}, held {c['coverage']:.0%} (aim 80%), mean bias {c['bias']:+.2f}"
                        if c["intervals"] else "")
                     + (f"; probabilities {c['probabilities']}, Brier {c['brier']:.3f}" if c["probabilities"] else ""))
        for author in sorted({f["author"] for f in human}):
            s, n = skill(st, author, "persistence")
            lines.append(f"SKILL of {author} against the record: "
                         + (f"{s:+.2f} on {n} pairs" if s is not None else "no pair yet; the record is a rival after "
                            f"{MIN_PERSIST} like windows"))
        lines.append("THE MODEL")
        rec = belief_record(st)
        for key, versions in sorted(st["beliefs"].items()):
            b, r = versions[-1], rec.get(key)
            lines.append(f"  {key} v{b['version']} ({b['confidence']:g}): {b['statement']}"
                         + (f"  [n={r['n']}, held {r['held']}" + (f", {r['flag']}" if r["flag"] else "") + "]" if r else "  [not yet tested]"))
        return "\n".join(lines)


# -------------------------------------------------------------------- CLI ---

def _triple(text: str) -> tuple:
    parts = [None if s.strip() in ("", "-") else float(s) for s in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("--q=lo,mid,hi (use - for a missing bound)")
    return tuple(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m packs.ri_operator.foresight")
    p.add_argument("--db")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("belief")
    for a in ("--key", "--statement", "--because"):
        b.add_argument(a, required=True)
    b.add_argument("--conf", type=float, required=True)
    b.add_argument("--lesson", default="")
    b.add_argument("--force")
    for name in ("forecast", "persist"):
        f = sub.add_parser(name)
        for a in ("--subject", "--sheet", "--metric", "--start", "--end"):
            f.add_argument(a, required=True)
        if name == "forecast":
            f.add_argument("--author", default="desk")
            f.add_argument("--q", type=_triple)
            f.add_argument("--p", type=float)
            f.add_argument("--op")
            f.add_argument("--x", type=float)
            f.add_argument("--beliefs", default="")
            f.add_argument("--why", default="")
            f.add_argument("--premortem", default="")
    s = sub.add_parser("settle")
    s.add_argument("--fid", required=True)
    s.add_argument("--actual", type=float, required=True)
    s.add_argument("--evidence", required=True)
    r = sub.add_parser("review")
    r.add_argument("--sheet", required=True)
    r.add_argument("--cause", required=True)
    r.add_argument("--lesson", required=True)
    r.add_argument("--force")
    rp = sub.add_parser("report")
    rp.add_argument("--subject")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        j = Journal(engine)
        if args.cmd == "report":
            print(j.report(args.subject))
            return 0
        if args.cmd == "belief":
            row = j.belief(key=args.key, statement=args.statement, because=args.because, conf=args.conf,
                           lesson=args.lesson, force=args.force)
        elif args.cmd == "forecast":
            row = j.forecast(subject=args.subject, sheet=args.sheet, metric=args.metric, start=args.start,
                             end=args.end, author=args.author, q=args.q, p=args.p, op=args.op, x=args.x,
                             beliefs=tuple(k for k in args.beliefs.split(",") if k), why=args.why,
                             premortem=args.premortem)
        elif args.cmd == "persist":
            row = j.persist(subject=args.subject, sheet=args.sheet, metric=args.metric, start=args.start, end=args.end)
            if row is None:
                n = j.like_windows(args.subject, args.metric, args.start, args.end)
                print(f"no rival yet: {n} of {MIN_PERSIST} like windows are settled")
                return 0
        elif args.cmd == "settle":
            row = j.settle(fid=args.fid, actual=args.actual, evidence=args.evidence)
        else:
            row = j.review(sheet=args.sheet, cause=args.cause, lesson=args.lesson, force=args.force)
        print(f"event_id={row['event_id']} type={row['event_type']} ledger_index={row['ledger_index']} "
              + json.dumps({k: row["payload"][k] for k in ("fid", "key", "version", "sheet", "held", "interval_score",
                                                           "brier", "cause") if k in row["payload"]}, sort_keys=True))
        return 0
    except EventError as e:
        print(f"REFUSED: {e}")
        return 2
    except (EngineError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        engine.close()


if __name__ == "__main__":
    sys.exit(main())
