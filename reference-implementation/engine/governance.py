"""Governance (JH-C11 wpD): what the loop may do without the operator, and what stops it.

    python -m engine.governance <pack> status [--db DSN]                  # leash, red flags, policies, holds
    python -m engine.governance <pack> ack --reason "..." [--db DSN]      # the operator reviewed the loop's changes

Each mechanism is a reading the loop records and a gate it obeys; the incident record that a halt opens lives in
engine.incidents.

  leash        (the panel, G-P5) adopted refinements, golden cases the loop added and planner batches since the
               operator's last ``<pack>.review``; past a cap the cycle still judges and reports but plans nothing
               and adopts nothing (``<pack>.review_required``) until the operator acknowledges
  red flags    (Brown, G-B10) every configured safety metric has a red threshold and a maximum age; one RED or
               UNKNOWN (no reading, a stale reading) holds refinement, golden growth and export, whatever the
               other metrics say (``<pack>.red_flag``), and heads the crank and autoloop reports
  policy       (Brown, G-B13) the autoloop thresholds, the judgement masses and every access.yaml carry
               ``reviewed_at``; one older than ``policy.max_age_days`` (or never reviewed) blocks the loop
               (``<pack>.policy_stale``); an eval matrix older than ``matrix_max_age_days`` or measured against
               another frontier admits no model (engine.manifest)
  integrity    (Naval, G-NAB9) a run that fabricated, cited what does not resolve or misstated a cited value,
               failed closed on access, or read an answer key and concealed it is an integrity breach, apart from
               quality failures; ``integrity_max`` unlifted breaches in the window halt the agent at once (the
               kill rule), whatever its pass rate; only a human verdict on each breaching run lifts it.  A
               honeypot the judge missed is the judge's breach and suspends it the same way
  eval vs live (Brown G-B9, the panel G-P2) per agent: golden score beside the live followed rate (human
               verdicts only), the trend of that rate while golden holds, and the distance between live and golden
               input buckets; a gap, a divergence or a distance above threshold holds refinement of that agent and
               names the overridden runs to grow golden from (``<pack>.eval_gap``)
  proxy        (Patel, G-D4) per agent: the share of certified runs the operator overrode (certified but wrong),
               the share of failed runs the operator accepted, and whether golden gains across adopted edits went
               with followed-rate gains; a certified-but-wrong share above threshold holds refinement of the agent
               and recommends a rung-2 check change to a human (``<pack>.proxy_validity``)
  sim gap      (Musk, G-M14) on a golden set whose cases are tagged simulated or real, the score on each; a gap
               above ``sim_gap.max`` flags the simulated cases as stale and an edit is adopted only on the real
               cases (``<pack>.sim_gap``)

Mechanism only: no domain nouns, no prompt text.  Times come from ``engine.clock``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from engine.config import CONFIG_DIR, load_yaml
from engine.errors import EngineError, GateError
from engine.events import EventLog
from engine.guardrails import JUDGEABLE_ROLES
from engine.runtime import parse_iso

_ALL = 1_000_000
REJECTING = ("overridden", "wrong")
_GUARDRAIL_RE = re.compile(r"guardrail ([A-Za-z0-9_]+):")
_MATRIX_RE = re.compile(r"^matrix-(\d{4}-\d{2}-\d{2})")
INTEGRITY_PREFIX = "integrity breach"


def cfg(engine) -> dict:
    return engine.config.governance


def _events(engine, pack, suffix: str) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{suffix}", limit=_ALL, ascending=True)


def _log(engine, pack, suffix: str, entity_id: str, payload: dict, source: str = "pipeline:governance",
         source_ref: str | None = None) -> dict:
    return EventLog(engine, pack).append(entity_type="agent_run", entity_id=entity_id, event_type=f"{pack.name}.{suffix}",
                                         payload=payload, source=source, source_ref=source_ref)


def _role(pack, name: str) -> str | None:
    return load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role")


def judgeable(pack) -> list[str]:
    return [n for n in sorted(pack.agent_names) if _role(pack, n) in JUDGEABLE_ROLES]


def dated_gates_apply(engine, pack) -> bool:
    """Red flags and policy staleness bind every real pack; a fixture pack only when ``governance.fixture_packs``."""
    return (not pack.fixture) or cfg(engine)["fixture_packs"]


def _as_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return date.fromisoformat(v)
    return None


# -- G-P5 the autonomy leash ----------------------------------------------------------------------------

def last_review(engine, pack) -> dict | None:
    evs = [e for e in _events(engine, pack, "review") if e["source"] == "human"]
    return evs[-1] if evs else None


def leash(engine, pack) -> dict:
    """Autonomous changes since the operator's last review, against the caps.  Order is the ledger's, so events
    recorded at one clock instant still count on the right side of the review."""
    c = cfg(engine)["leash"]
    rev = last_review(engine, pack)
    after = rev["ledger_index"] if rev else -1

    def since(suffix: str) -> list[dict]:
        return [e for e in _events(engine, pack, suffix) if e["ledger_index"] > after]

    adoptions = [e for e in since("refinement") if e["payload"]["adopted"]]
    grown = [e for e in since("golden_grown") if e["payload"]["kind"] != "regression"] + \
            [e for e in since("case_proposed") if e["payload"]["admitted"]]
    batches = [e for e in since("plan") if e["payload"]["batch"]]
    counts = {"adoptions": len(adoptions), "grown": len(grown), "batches": len(batches)}
    caps = {"adoptions": int(c["max_unreviewed_adoptions"]), "grown": int(c["max_unreviewed_grown"]),
            "batches": int(c["max_unreviewed_batches"])}
    reached = [k for k in caps if counts[k] >= caps[k]]
    return {**counts, "caps": caps, "reached": reached, "held": bool(reached),
            "since_event_id": rev["event_id"] if rev else None, "since_ledger_index": after,
            "why": (f"the operator has not reviewed the loop since {rev['event_id'] if rev else 'it started'}: "
                    + ", ".join(f"{counts[k]} {k} (cap {caps[k]})" for k in reached)
                    + "; nothing is planned or adopted until `python -m engine.governance <pack> ack`") if reached else None}


def leash_gate(engine, pack) -> dict:
    """The leash, recording ``<pack>.review_required`` once per unreviewed stretch when a cap is reached."""
    state = leash(engine, pack)
    if state["held"]:
        recorded = [e for e in _events(engine, pack, "review_required") if e["ledger_index"] > state["since_ledger_index"]]
        if not recorded:
            ev = _log(engine, pack, "review_required", pack.name,
                      {"since_event_id": state["since_event_id"], "adoptions": state["adoptions"], "grown": state["grown"],
                       "batches": state["batches"], "reached": state["reached"]})
            state["event_id"] = ev["event_id"]
    return state


def record_review(engine, pack, reason: str, *, source: str = "human") -> dict:
    """The operator's acknowledgement: the loop's changes so far were looked at; the counters start again."""
    if source != "human":
        raise EngineError("only the operator acknowledges a review (source human)")
    if not reason or not reason.strip():
        raise EngineError("a review needs a reason (what was looked at)")
    state = leash(engine, pack)
    return _log(engine, pack, "review", pack.name,
                {"reason": reason.strip(), "adoptions": state["adoptions"], "grown": state["grown"],
                 "batches": state["batches"], "previous_review_id": state["since_event_id"]}, source="human")


# -- G-B10 red flags: one concerning metric blocks, unknown is not green --------------------------------

def _field(payload: dict, dotted: str):
    node = payload
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def red_flags(engine, pack) -> list[dict]:
    """Every configured metric's latest reading: GREEN, RED (past its threshold) or UNKNOWN (never read, read
    longer ago than ``max_age_days``, or not a number)."""
    now = engine.clock.now()
    out = []
    for name, spec in sorted(cfg(engine)["red_flags"].items()):
        evs = _events(engine, pack, spec["event"])
        threshold = spec["above"] if spec["above"] is not None else spec["below"]
        side = "above" if spec["above"] is not None else "below"
        row = {"metric": name, "event": spec["event"], "field": spec["field"], "side": side, "threshold": threshold,
               "max_age_days": spec["max_age_days"], "value": None, "age_days": None, "reading_event_id": None}
        if not evs:
            out.append({**row, "status": "UNKNOWN", "why": f"no {spec['event']} reading has ever been recorded"})
            continue
        latest = evs[-1]
        age = round((now - parse_iso(latest["recorded_at"])).total_seconds() / 86400, 4)
        value = _field(latest["payload"], spec["field"])
        row.update(age_days=age, reading_event_id=latest["event_id"],
                   value=value if isinstance(value, (int, float)) and not isinstance(value, bool) else None)
        if age > spec["max_age_days"]:
            out.append({**row, "status": "UNKNOWN", "why": f"the latest reading is {age} days old (max {spec['max_age_days']})"})
        elif row["value"] is None:
            out.append({**row, "status": "UNKNOWN", "why": f"{spec['field']} is not a number on the latest reading"})
        elif (side == "above" and row["value"] > threshold) or (side == "below" and row["value"] < threshold):
            out.append({**row, "status": "RED", "why": f"{spec['field']} {row['value']} is {side} {threshold}"})
        else:
            out.append({**row, "status": "GREEN", "why": f"{spec['field']} {row['value']} within {threshold}"})
    return out


def red_flag_hold(flags: list[dict]) -> str | None:
    bad = [f for f in flags if f["status"] != "GREEN"]
    return None if not bad else "red flags: " + "; ".join(f"{f['metric']} {f['status']} ({f['why']})" for f in bad)


def red_flag_gate(engine, pack) -> dict:
    """Readings and, when the gate applies to this pack, one ``<pack>.red_flag`` per metric that is not green."""
    flags = red_flags(engine, pack)
    applies = dated_gates_apply(engine, pack)
    if applies:
        for f in flags:
            if f["status"] != "GREEN":
                _log(engine, pack, "red_flag", pack.name, {k: f[k] for k in ("metric", "status", "value", "threshold", "side",
                                                                             "age_days", "max_age_days", "reading_event_id", "why")})
    return {"flags": flags, "applies": applies, "hold": red_flag_hold(flags) if applies else None}


# -- G-B13 policy and evaluation staleness ----------------------------------------------------------------

def policy_dates(pack, config) -> list[dict]:
    """Every governed policy and the date it says it was last reviewed (None = never).  No clock: validate reports this."""
    out = [{"policy": "engine.yaml#autoloop", "path": str(CONFIG_DIR / "engine.yaml"),
            "reviewed_at": _as_date((config.engine.get("autoloop") or {}).get("reviewed_at"))},
           {"policy": "judgement.yaml", "path": str(CONFIG_DIR / "judgement.yaml"),
            "reviewed_at": _as_date(config.judgement.get("reviewed_at"))}]
    for name in sorted(pack.agent_names):
        p = pack.agent_dir(name) / "access.yaml"
        if p.is_file():
            out.append({"policy": f"agents/{name}/access.yaml", "path": str(p), "reviewed_at": _as_date(load_yaml(p).get("reviewed_at"))})
    return out


def latest_matrix(agent_dir: Path) -> tuple[str, dict] | None:
    files = sorted((agent_dir / "eval").glob("matrix-*.json"))
    return (files[-1].name, json.loads(files[-1].read_text(encoding="utf-8"))) if files else None


def matrix_problem(file_name: str, matrix: dict, config, now: datetime | None) -> str | None:
    """Why a parity matrix no longer admits a model: measured against another frontier than the one pinned now,
    or (when the caller has the engine clock) older than ``policy.matrix_max_age_days``."""
    pinned = config.frontier.model_string
    measured = matrix.get("frontier")
    if measured and measured != pinned:
        return f"{file_name} measured parity against {measured}; the frontier pin is now {pinned}: re-run engine.eval --models"
    m = _MATRIX_RE.match(file_name)
    if now is not None and m:
        age = (now.date() - date.fromisoformat(m.group(1))).days
        limit = int(config.governance["policy"]["matrix_max_age_days"])
        if age > limit:
            return f"{file_name} is {age} days old (max {limit}): parity that old says nothing about today's models"
    return None


def policy_status(engine, pack) -> list[dict]:
    now = engine.clock.now().date()
    limit = int(cfg(engine)["policy"]["max_age_days"])
    out = []
    for p in policy_dates(pack, engine.config):
        age = None if p["reviewed_at"] is None else (now - p["reviewed_at"]).days
        stale = age is None or age > limit
        out.append({"kind": "policy", "policy": p["policy"], "reviewed_at": None if p["reviewed_at"] is None else p["reviewed_at"].isoformat(),
                    "age_days": age, "max_age_days": limit, "stale": stale,
                    "why": ("never reviewed (no reviewed_at)" if age is None else f"reviewed {age} days ago (max {limit})") if stale else None})
    for name in sorted(pack.agent_names):
        found = latest_matrix(pack.agent_dir(name))
        if found:
            why = matrix_problem(found[0], found[1], engine.config, engine.clock.now())
            out.append({"kind": "matrix", "policy": f"agents/{name}/eval/{found[0]}", "reviewed_at": None, "age_days": None,
                        "max_age_days": int(cfg(engine)["policy"]["matrix_max_age_days"]), "stale": why is not None, "why": why})
    return out


def policy_gate(engine, pack) -> dict:
    """Stale policies block the loop (a stale matrix is refused where it would admit a model, in engine.manifest)."""
    status = policy_status(engine, pack)
    applies = dated_gates_apply(engine, pack)
    stale = [p for p in status if p["stale"] and p["kind"] == "policy"]
    if applies:
        for p in [p for p in status if p["stale"]]:
            _log(engine, pack, "policy_stale", pack.name, {"policy": p["policy"], "kind": p["kind"], "reviewed_at": p["reviewed_at"],
                                                            "age_days": p["age_days"], "max_age_days": p["max_age_days"], "why": p["why"]})
    hold = ("stale policy: " + "; ".join(f"{p['policy']} {p['why']}" for p in stale)) if (applies and stale) else None
    return {"policies": status, "applies": applies, "hold": hold}


# -- G-NAB9 the integrity tripwire -------------------------------------------------------------------------

def integrity_reasons(row: dict, tw: dict, concealed: set[str] | None = None) -> list[str]:
    """The integrity classes a run's failure falls in (empty = none, so any failure is a quality failure)."""
    out = set()
    if row["status"] == "access_denied" and tw["access_denied"]:
        out.add("access_denied")
    if row["status"] != "succeeded":
        for msg in row["failure_reasons"] or []:
            m = _GUARDRAIL_RE.search(msg)
            if m and m.group(1) in tw["guardrails"]:
                out.add(m.group(1))
    if concealed and row["run_id"] in concealed:
        out.add("concealed_trap")
    return sorted(out)


def _concealed_runs(engine, pack, tw: dict) -> set[str]:
    if not tw["concealed_traps"]:
        return set()
    return {e["payload"]["run_id"] for e in _events(engine, pack, "trap") if e["payload"]["read"] and not e["payload"]["disclosed"]}


def _record_breach(engine, pack, known: set[str], run_id: str, agent: str, classes: list[str], message: str) -> None:
    if run_id in known:
        return
    _log(engine, pack, "integrity_breach", run_id, {"run_id": run_id, "agent": agent, "guardrail": ",".join(classes),
                                                     "message": message[:1000]}, source_ref=run_id)
    known.add(run_id)


def integrity_halts(engine, pack) -> dict[str, str]:
    """{agent: why} for every judgeable agent with ``integrity_max`` or more breaching runs in its last
    ``window_runs`` that no human has given a verdict.  Each breach is recorded once (``<pack>.integrity_breach``)."""
    tw = cfg(engine)["integrity_tripwire"]
    concealed = _concealed_runs(engine, pack, tw)
    known = {e["payload"]["run_id"] for e in _events(engine, pack, "integrity_breach")}
    out: dict[str, str] = {}
    for name in judgeable(pack):
        rows = engine.store.list_runs(pack=pack.name, agent=name, limit=int(tw["window_runs"]), newest_first=True)
        unlifted = []
        for r in rows:
            classes = integrity_reasons(r, tw, concealed)
            if not classes:
                continue
            msg = next((m for m in r["failure_reasons"] or [] if any(c in m for c in classes)), None) or \
                ("read an answer key and did not disclose it" if "concealed_trap" in classes else r["status"])
            _record_breach(engine, pack, known, r["run_id"], name, classes, msg)
            if r.get("verdict_source") != "human":
                unlifted.append((r["run_id"], classes))
        if len(unlifted) >= int(tw["integrity_max"]):
            out[name] = (f"{INTEGRITY_PREFIX}: " + ", ".join(f"run {rid} ({'/'.join(c)})" for rid, c in unlifted[:5])
                         + f"; {len(unlifted)} unlifted in the last {len(rows)} runs (max {tw['integrity_max']}), halted whatever "
                           f"the pass rate until the operator gives each breaching run a verdict")
    return out


def judge_integrity(engine, pack) -> dict:
    """Honeypots the judge missed are its integrity breaches, always recorded (``<pack>.integrity_breach``, the
    crank's integrity column, the judge's incident).  With ``judge_honeypots`` on, ``integrity_max`` of them without a
    human verdict on the judge run suspend the judge at once; off, the judge's tripwire is the miss-rate gate
    (``autoloop.judge.max_missed`` after ``min_planted``), because graded honeypots are planted to find where the
    judge stops noticing and a miss at the hardest tier is that measurement."""
    tw = cfg(engine)["integrity_tripwire"]
    known = {e["payload"]["run_id"] for e in _events(engine, pack, "integrity_breach")}
    unlifted = []
    for e in _events(engine, pack, "honeypot"):
        if e["payload"]["hit"]:
            continue
        row = engine.store.get_run(e["payload"]["judge_run_id"])
        if row is None:
            continue
        _record_breach(engine, pack, known, row["run_id"], row["agent"], ["honeypot_missed"],
                       f"missed the altered {e['payload']['path']} on run {e['payload']['target_run_id']} (verdict {e['payload']['verdict']})")
        if row.get("verdict_source") != "human":
            unlifted.append(row["run_id"])
    halted = bool(tw["judge_honeypots"]) and len(unlifted) >= int(tw["integrity_max"])
    return {"halted": halted, "missed": unlifted,
            "why": (f"{INTEGRITY_PREFIX}: the judge missed honeypots in runs {unlifted[:5]} and no human has given those judge "
                    f"runs a verdict") if halted else None}


def failure_classes(runs: list[dict], tw: dict, concealed: set[str] | None = None) -> dict[str, dict]:
    """{agent: {integrity, quality}}: failed runs split by class (the crank shows them apart)."""
    out: dict[str, dict] = {}
    for r in runs:
        if r["role"] not in JUDGEABLE_ROLES:
            continue
        a = out.setdefault(r["agent"], {"integrity": 0, "quality": 0})
        classes = integrity_reasons(r, tw, concealed)
        if classes:
            a["integrity"] += 1
        elif r["status"] != "succeeded":
            a["quality"] += 1
    return out


# -- G-B9 / G-P2 eval vs live -----------------------------------------------------------------------------

def _human_rows(engine, pack, agent: str) -> list[dict]:
    rows = engine.store.list_runs(pack=pack.name, agent=agent, verdict_source="human")
    return [r for r in rows if r["human_verdict"] in ("followed",) + REJECTING]


def _followed_rate(rows: list[dict]) -> float | None:
    return round(sum(1 for r in rows if r["human_verdict"] == "followed") / len(rows), 4) if rows else None


def _golden_score(engine, pack, agent: str, since: str | None) -> float | None:
    """Golden score over the agent's recorded runs on golden/held-out inputs from ``since``; else the latest
    refinement's measured score for the version in force."""
    from engine.goldenview import golden_view
    runs = engine.store.list_runs(pack=pack.name, agent=agent, since=since)
    g = golden_view(engine, pack, agent, runs) if runs else None
    if g and g["counted"]:
        return float(g["score"])
    evs = [e for e in _events(engine, pack, "refinement") if e["payload"]["agent"] == agent]
    if evs:
        p = evs[-1]["payload"]
        return float(p["after_score"] if p["adopted"] else p["before_score"])
    return None


def _input_distance(pack, agent: str, live_inputs: list[dict]) -> float | None:
    """Total-variation distance between the live and golden input buckets (pack @featurize), None without buckets."""
    from engine.analytics import golden_inputs
    reg = getattr(pack, "featurize", None)
    if reg is None or not reg.ids():
        return None
    live = [b for b in (reg.bucket(agent, i) for i in live_inputs) if b is not None]
    gold = [b for b in (reg.bucket(agent, i) for i in golden_inputs(pack, agent)) if b is not None]
    if not live or not gold:
        return None
    keys = set(live) | set(gold)
    return round(0.5 * sum(abs(live.count(k) / len(live) - gold.count(k) / len(gold)) for k in keys), 4)


def eval_live_gap(engine, pack, agent: str) -> dict:
    c = cfg(engine)["eval_live"]
    n, need, gap_max = int(c["window_verdicts"]), int(c["min_verdicts"]), float(c["max_gap"])
    rows = _human_rows(engine, pack, agent)
    now_rows, prev_rows = rows[-n:], rows[-2 * n:-n] if len(rows) > n else []
    live = _followed_rate(now_rows)
    golden = _golden_score(engine, pack, agent, now_rows[0]["created_at"] if now_rows else None)
    golden_prev = _golden_score(engine, pack, agent, prev_rows[0]["created_at"]) if prev_rows else None
    live_prev = _followed_rate(prev_rows)
    gap = None if golden is None or live is None else round(golden - live, 4)
    enough = len(now_rows) >= need
    divergence = (enough and len(prev_rows) >= need and golden is not None and live_prev is not None
                  and live_prev - live > gap_max and (golden_prev is None or golden >= golden_prev))
    distance = _input_distance(pack, agent, [r["input"] for r in now_rows])
    reasons = []
    if enough and gap is not None and gap > gap_max:
        reasons.append(f"golden {golden} vs live followed rate {live} over {len(now_rows)} human verdicts: gap {gap} > {gap_max}")
    if divergence:
        reasons.append(f"live followed rate fell from {live_prev} to {live} while golden held at {golden}: benchmark divergence")
    if enough and distance is not None and distance > float(c["max_input_distance"]):
        reasons.append(f"live inputs sit {distance} (total variation) from the golden inputs (> {c['max_input_distance']})")
    overridden = [r["run_id"] for r in now_rows if r["human_verdict"] in REJECTING]
    return {"agent": agent, "golden_score": golden, "live_followed_rate": live, "verdicts": len(now_rows), "gap": gap,
            "previous_live_rate": live_prev, "previous_golden_score": golden_prev, "divergence": bool(divergence),
            "input_distance": distance, "held": bool(reasons), "why": "; ".join(reasons) or None,
            "grow_from": overridden if reasons else []}


# -- G-D4 proxy validity -----------------------------------------------------------------------------------

def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (vx * vy) ** 0.5, 4)


def proxy_validity(engine, pack, agent: str) -> dict:
    c = cfg(engine)["proxy"]
    rows = _human_rows(engine, pack, agent)[-int(c["window_verdicts"]):]
    certified = [r for r in rows if r["status"] == "succeeded"]
    failed = [r for r in rows if r["status"] != "succeeded"]
    wrong = [r for r in certified if r["human_verdict"] in REJECTING]
    accepted = [r for r in failed if r["human_verdict"] == "followed"]
    rate = round(len(wrong) / len(certified), 4) if certified else None
    held = len(certified) >= int(c["min_compared"]) and rate is not None and rate > float(c["max_proxy_gap"])
    all_rows = _human_rows(engine, pack, agent)
    k = int(c["min_compared"])
    pairs = []
    for e in _events(engine, pack, "refinement"):
        p = e["payload"]
        if p["agent"] != agent or not p["adopted"]:
            continue
        before = [r for r in all_rows if r["ledger_index"] < e["ledger_index"]][-k:]
        after = [r for r in all_rows if r["ledger_index"] > e["ledger_index"]][:k]
        if before and after:
            pairs.append((float(p["after_score"]) - float(p["before_score"]), _followed_rate(after) - _followed_rate(before)))
    corr = _pearson([x for x, _ in pairs], [y for _, y in pairs]) if len(pairs) >= int(c["min_edits"]) else None
    return {"agent": agent, "compared": len(certified), "certified_wrong": len(wrong), "rate": rate,
            "failed_compared": len(failed), "failed_accepted": len(accepted),
            "failed_accepted_rate": round(len(accepted) / len(failed), 4) if failed else None,
            "edits": len(pairs), "golden_followed_correlation": corr, "held": held,
            "why": (f"{len(wrong)} of {len(certified)} certified runs were overridden or wrong ({rate} > {c['max_proxy_gap']}): "
                    f"the checks certify what the operator rejects; a rung-2 guardrail, verifier or golden compare change is "
                    f"for a human") if held else None}


# -- G-M14 sim-to-real gap ---------------------------------------------------------------------------------

def sim_gap(eval_result: dict, sc: dict) -> dict:
    """Score on the cases tagged simulated vs those tagged real (``sim_gap.tag``), primary model's robust case pass."""
    tag = sc["tag"]
    sim = [c for c in eval_result["models"][0]["cases"] if c.get("counted", True) and str((c.get("tags") or {}).get(tag)) in sc["simulated"]]
    real = [c for c in eval_result["models"][0]["cases"] if c.get("counted", True) and str((c.get("tags") or {}).get(tag)) in sc["real"]]

    def score(cases):
        return round(sum(1 for c in cases if c["passed"]) / len(cases), 4) if cases else None

    s, r = score(sim), score(real)
    gap = None if s is None or r is None else round(s - r, 4)
    return {"sim_score": s, "real_score": r, "sim_cases": len(sim), "real_cases": len(real), "gap": gap,
            "flagged": gap is not None and gap > float(sc["max"])}


def adoption_refusals(engine, pack, agent: str, before: dict, after: dict) -> list[str]:
    """Recorded on every refinement: the sim-to-real gap of the version in force.  When it is above ``sim_gap.max``
    the simulated cases are stale and decide nothing: the real cases must hold."""
    sc = cfg(engine)["sim_gap"]
    b, a = sim_gap(before, sc), sim_gap(after, sc)
    if b["sim_cases"] == 0 and b["real_cases"] == 0:
        return []
    _log(engine, pack, "sim_gap", agent, {"agent": agent, **b, "max": float(sc["max"]),
                                          "after_real_score": a["real_score"], "after_sim_score": a["sim_score"]})
    if not b["flagged"]:
        return []
    if a["real_score"] is None or a["real_score"] < b["real_score"]:
        return [f"sim-to-real gap {b['gap']} > {sc['max']} (simulated {b['sim_score']}, real {b['real_score']}): the simulated "
                f"cases are stale and decide nothing; the real cases went {b['real_score']} -> {a['real_score']}"]
    return []


# -- the loop's hooks --------------------------------------------------------------------------------------

def agent_hold(engine, pack, agent: str) -> dict | None:
    """A per-agent hold on refinement: eval and live disagree, or the proxy does not track the operator."""
    g = eval_live_gap(engine, pack, agent)
    if g["held"]:
        return {"status": "eval_gap", "why": g["why"] + (f"; grow golden from the overridden runs {g['grow_from'][:5]} "
                                                         f"(engine.verdicts --expected)" if g["grow_from"] else "")}
    p = proxy_validity(engine, pack, agent)
    if p["held"]:
        return {"status": "proxy_invalid", "why": p["why"]}
    return None


def refine_hold(engine, pack, agent: str) -> dict | None:
    """Everything that holds an edit of ``agent``, first reason wins: the leash, a stale policy, a red flag, then
    the agent's own eval-live and proxy readings.  Pure (the cycle records the events)."""
    lsh = leash(engine, pack)
    if lsh["held"]:
        return {"status": "review_required", "why": lsh["why"]}
    if dated_gates_apply(engine, pack):
        stale = [p for p in policy_status(engine, pack) if p["stale"] and p["kind"] == "policy"]
        if stale:
            return {"status": "policy_stale", "why": "stale policy: " + "; ".join(f"{p['policy']} {p['why']}" for p in stale)}
        hold = red_flag_hold(red_flags(engine, pack))
        if hold:
            return {"status": "red_flag", "why": hold}
    return agent_hold(engine, pack, agent)


def before_plan(engine, pack) -> dict:
    """Leash and policy staleness, before the planner is asked: either holds the plan."""
    lsh = leash_gate(engine, pack)
    pol = policy_gate(engine, pack)
    if lsh["held"]:
        return {"hold": lsh["why"], "status": "review_required", "leash": lsh, "policy": pol}
    if pol["hold"]:
        return {"hold": pol["hold"], "status": "policy_stale", "leash": lsh, "policy": pol}
    return {"hold": None, "status": None, "leash": lsh, "policy": pol}


def before_change(engine, pack) -> dict:
    """Leash, stale policy and red flags, before anything is adopted or grown (refine, judge learning, curation,
    golden growth, regression cases).  Red flags are read here, after the cycle's own cheat-rate reading."""
    lsh = leash(engine, pack)
    pol_hold = None
    if dated_gates_apply(engine, pack):
        stale = [p for p in policy_status(engine, pack) if p["stale"] and p["kind"] == "policy"]
        pol_hold = ("stale policy: " + "; ".join(f"{p['policy']} {p['why']}" for p in stale)) if stale else None
    red = red_flag_gate(engine, pack)
    for status, why in (("review_required", lsh["why"]), ("policy_stale", pol_hold), ("red_flag", red["hold"])):
        if why:
            return {"hold": why, "status": status, "red_flags": red}
    return {"hold": None, "status": None, "red_flags": red}


def record_growth(engine, pack, grown: list[dict]) -> int:
    """Golden cases grown from operator-followed runs, recorded so the leash counts them."""
    n = 0
    for g in grown or []:
        for cid in g["ids"]:
            run_id = cid[len("run-"):] if cid.startswith("run-") else cid
            _log(engine, pack, "golden_grown", run_id, {"agent": g["agent"], "case_id": cid, "run_id": run_id, "kind": "followed"},
                 source="pipeline:autoloop")
            n += 1
    return n


def measure(engine, pack, week: str) -> dict:
    """Per judgeable agent: the eval-live reading and the proxy reading, each recorded when there is a verdict to read."""
    out = {"eval_gap": [], "proxy": []}
    for name in judgeable(pack):
        g = eval_live_gap(engine, pack, name)
        if g["verdicts"]:
            _log(engine, pack, "eval_gap", name, {"week": week, **{k: g[k] for k in (
                "agent", "golden_score", "live_followed_rate", "verdicts", "gap", "previous_live_rate", "divergence",
                "input_distance", "held", "grow_from")}, "why": g["why"]})
            out["eval_gap"].append(g)
        p = proxy_validity(engine, pack, name)
        if p["compared"] or p["failed_compared"]:
            _log(engine, pack, "proxy_validity", name, {"week": week, **{k: p[k] for k in (
                "agent", "compared", "certified_wrong", "rate", "failed_compared", "failed_accepted", "edits",
                "golden_followed_correlation", "held")}, "why": p["why"]})
            out["proxy"].append(p)
    return out


def after_cycle(engine, pack, week: str, result: dict) -> dict:
    """The cycle's governance record: growth the leash counts, incidents for concealed cheats and monitor flags,
    the eval-live and proxy readings."""
    from engine import incidents
    grown = record_growth(engine, pack, result.get("grow") or [])
    opened = incidents.from_cycle(engine, pack, traps=result.get("traps") or [], monitor=result.get("monitor") or [])
    return {"grown_recorded": grown, "incidents_opened": [i["event_id"] for i in opened], **measure(engine, pack, week),
            "open_incidents": [{k: i[k] for k in ("incident_id", "severity", "kind", "subject", "causes", "uninvestigated")}
                               for i in incidents.open_incidents(engine, pack)]}


def export_hold(engine, pack) -> None:
    """Export and distillation wait while an incident is open, a red flag is not green, or a policy is stale."""
    from engine import incidents
    if cfg(engine)["incidents"]["block_export"]:
        open_ = incidents.open_incidents(engine, pack)
        if open_:
            raise GateError(f"export refused: {len(open_)} open incident(s) {[i['incident_id'] for i in open_][:5]}; every cause needs "
                            f"an investigation with a fix (python -m engine.incidents {pack.name} investigate)")
    if dated_gates_apply(engine, pack):
        stale = [p for p in policy_status(engine, pack) if p["stale"] and p["kind"] == "policy"]
        if stale:
            raise GateError("export refused: stale policy " + ", ".join(p["policy"] for p in stale))
        hold = red_flag_hold(red_flags(engine, pack))
        if hold:
            raise GateError(f"export refused: {hold}")


# -- reports -------------------------------------------------------------------------------------------------

def crank_section(engine, pack, runs: list[dict]) -> dict:
    """Read-only: what the crank shows at its head and in its governance section."""
    from engine import incidents
    tw = cfg(engine)["integrity_tripwire"]
    sims = {}
    for e in _events(engine, pack, "sim_gap"):
        sims[e["payload"]["agent"]] = e["payload"]
    return {"red_flags": red_flags(engine, pack), "red_flags_apply": dated_gates_apply(engine, pack),
            "leash": leash(engine, pack), "policies": policy_status(engine, pack),
            "open_incidents": incidents.open_incidents(engine, pack),
            "failure_classes": failure_classes(runs, tw, _concealed_runs(engine, pack, tw)),
            "eval_live": [eval_live_gap(engine, pack, a) for a in judgeable(pack)],
            "proxy": [proxy_validity(engine, pack, a) for a in judgeable(pack)],
            "sim_gap": sims}


def render_top(section: dict | None) -> list[str]:
    """The head of a report: every metric that is not green, the leash and the open incidents, before anything else."""
    if not section:
        return []
    bad = [f for f in section.get("red_flags") or [] if f["status"] != "GREEN"]
    L = ["## Red flags (one is enough; unknown is not green)", ""]
    if bad:
        L += [f"- **{f['status']}** {f['metric']}: {f['why']}" for f in bad]
        if not section.get("red_flags_apply", True):
            L += ["- (a fixture pack: reported, not enforced; governance.fixture_packs)"]
    else:
        L += ["- all green: " + ", ".join(f"{f['metric']} {f['value']}" for f in section.get("red_flags") or [])]
    lsh = section.get("leash")
    if lsh:
        L += [f"- leash: {lsh['adoptions']}/{lsh['caps']['adoptions']} adoptions, {lsh['grown']}/{lsh['caps']['grown']} grown, "
              f"{lsh['batches']}/{lsh['caps']['batches']} batches since review {lsh['since_event_id']}"
              + (" -- REVIEW REQUIRED" if lsh["held"] else "")]
    stale = [p for p in section.get("policies") or [] if p["stale"]]
    if stale:
        L += [f"- STALE {p['policy']}: {p['why']}" for p in stale]
    inc = section.get("open_incidents") or []
    if inc:
        L += [f"- OPEN INCIDENT {i['incident_id']} ({i['severity']} {i['kind']} {i['subject']}): {len(i['uninvestigated'])} of "
              f"{len(i['causes'])} causes uninvestigated" for i in inc]
    return L + [""]


def render_section(section: dict | None) -> list[str]:
    if not section:
        return []
    L = ["", "## Governance", "", "| agent | integrity failures | quality failures |", "|---|---|---|"]
    L += [f"| {a} | {c['integrity']} | {c['quality']} |" for a, c in sorted(section["failure_classes"].items())] or ["| - | 0 | 0 |"]
    L += [""]
    for g in section["eval_live"]:
        if g["verdicts"]:
            L += [f"- eval vs live {g['agent']}: golden {g['golden_score']}, live followed {g['live_followed_rate']} over "
                  f"{g['verdicts']} human verdicts, gap {g['gap']}, input distance {g['input_distance']}"
                  + (f" -- HELD: {g['why']}; grow golden from {g['grow_from'][:5]}" if g["held"] else "")]
    for p in section["proxy"]:
        if p["compared"] or p["failed_compared"]:
            L += [f"- proxy {p['agent']}: certified-but-wrong {p['certified_wrong']}/{p['compared']} ({p['rate']}), failed-but-accepted "
                  f"{p['failed_accepted']}/{p['failed_compared']}, golden-vs-followed correlation over {p['edits']} edits "
                  f"{p['golden_followed_correlation']}" + (f" -- HELD: {p['why']}" if p["held"] else "")]
    for a, s in sorted(section["sim_gap"].items()):
        L += [f"- sim-to-real {a}: simulated {s['sim_score']} ({s['sim_cases']} cases) vs real {s['real_score']} ({s['real_cases']})"
              + (f" -- the simulated set is STALE (gap {s['gap']} > {s['max']}): adoption rests on the real cases" if s["flagged"] else "")]
    return L


# -- CLI -----------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    from engine.packs import load_pack
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.governance")
    p.add_argument("pack")
    p.add_argument("command", choices=("status", "ack"))
    p.add_argument("--reason")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            pack = load_pack(args.pack)
            if args.command == "ack":
                ev = record_review(engine, pack, args.reason or "")
                print(f"review recorded: {ev['event_id']} ({ev['payload']['adoptions']} adoptions, {ev['payload']['grown']} grown, "
                      f"{ev['payload']['batches']} batches acknowledged)")
                return 0
            section = crank_section(engine, pack, [])
            print("\n".join(render_top(section)))
            for p_ in section["policies"]:
                print(f"{'STALE' if p_['stale'] else 'ok   '} {p_['policy']} reviewed_at={p_['reviewed_at']} {p_['why'] or ''}")
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
