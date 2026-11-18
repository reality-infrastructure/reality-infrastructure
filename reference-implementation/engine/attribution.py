"""Credit and blame through composition (JH-C11 wpF, G-NAB3).

Naval: every exchange carries its own ledger of who contributed what.  When a verdict lands on a run
whose output cites other runs (an orchestrator stating a child's certified figures), the verdict is
passed down along the citations: ``followed`` credits every cited child run; ``overridden`` / ``wrong``
blames the children cited by the fields the reason names (a citation's field or the ``name`` of the object
that carries it; failing that, every citation under a top-level key the reason
names).  Each transfer is a ``<pack>.attribution`` event {verdict_event_id, from_run, to_run, field,
kind}.  The child's own verdict is never touched; the crank shows own and inherited verdicts per agent,
and the kill rule counts an inherited blame as ``inherited_weight`` of a failure.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from engine.analytics import week_events
from engine.citations import iter_citations

RUN_PREFIX = "run:agent_runs:"


def _named(reason: str, owner, cite: dict) -> bool:
    words = [cite.get("field")]
    if isinstance(owner, dict) and isinstance(owner.get("name"), str):
        words.append(owner["name"])
    return any(isinstance(w, str) and w and w in reason for w in words)


def _owner(output, path: tuple):
    o = output
    for p in path:
        o = o[int(p)] if isinstance(o, list) else o[p]
    return o


def transfers(output, verdict: str, reason: str) -> list[tuple[str, str, str]]:
    """(child_run_id, field, kind) for every citation the verdict passes down."""
    if verdict not in ("followed", "overridden", "wrong") or not isinstance(output, dict):
        return []
    cites = [(path, c) for path, c in iter_citations(output) if isinstance(c.get("ref"), str) and c["ref"].startswith(RUN_PREFIX)]
    if verdict == "followed":
        picked = cites
    else:
        picked = [(p, c) for p, c in cites if _named(reason, _owner(output, p), c)]
        if not picked:
            picked = [(p, c) for p, c in cites if p and p[0] in reason]
    kind = "credit" if verdict == "followed" else "blame"
    out, seen = [], set()
    for path, c in picked:
        key = (c["ref"][len(RUN_PREFIX):], c.get("field") or "/".join(path))
        if key not in seen:
            seen.add(key)
            out.append((key[0], key[1], kind))
    return out


def attribute(engine, pack, row: dict, verdict: str, reason: str, verdict_event: dict, *, source: str) -> list[dict]:
    """Write the verdict's credit or blame to every child run it reaches; called by record_verdict."""
    if not engine.config.analytics["attribution"]["enabled"]:
        return []
    from engine.events import EventLog
    log = EventLog(engine, pack)
    out = []
    for child_id, field, kind in transfers(row["output"], verdict, reason):
        child = engine.store.get_run(child_id)
        if child is None or child["pack"] != pack.name:
            continue
        out.append(log.append(entity_type="agent_run", entity_id=child_id, event_type=f"{pack.name}.attribution",
                              payload={"verdict_event_id": verdict_event["event_id"], "from_run": row["run_id"], "to_run": child_id,
                                       "to_agent": child["agent"], "field": field, "kind": kind, "verdict": verdict},
                              source=source, source_ref=verdict_event["event_id"]))
    return out


def inherited_blame(engine, pack, run_ids: set[str]) -> set[str]:
    """The runs among ``run_ids`` that inherited a blame from a parent's verdict."""
    if not engine.config.analytics["attribution"]["enabled"]:
        return set()
    return {e["payload"]["to_run"] for e in week_events(engine, pack, "attribution")
            if e["payload"]["kind"] == "blame" and e["payload"]["to_run"] in run_ids}


def report(engine, pack, week: str, runs: list[dict]) -> list[dict]:
    w = engine.config.analytics["attribution"]["inherited_weight"]
    own: dict[str, Counter] = defaultdict(Counter)
    for r in runs:
        if r["human_verdict"]:
            own[r["agent"]][r["human_verdict"]] += 1
    inh: dict[str, Counter] = defaultdict(Counter)
    for e in week_events(engine, pack, "attribution", week):
        inh[e["payload"]["to_agent"]][e["payload"]["kind"]] += 1
    out = []
    for agent in sorted(set(own) | set(inh)):
        out.append({"agent": agent, "own": dict(sorted(own[agent].items())), "inherited_credit": inh[agent]["credit"],
                    "inherited_blame": inh[agent]["blame"], "inherited_weight": w,
                    "weighted_inherited": round(w * (inh[agent]["credit"] - inh[agent]["blame"]), 4)})
    return out


def render(report_: dict) -> list[str]:
    L = ["", "## Credit and blame through composition", "", "| agent | own verdicts | inherited credit | inherited blame | weighted |",
         "|---|---|---|---|---|"]
    for a in report_["attribution"]:
        L.append(f"| {a['agent']} | {a['own'] or '—'} | {a['inherited_credit']} | {a['inherited_blame']} | {a['weighted_inherited']} |")
    return L
