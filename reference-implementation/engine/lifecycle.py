"""The refinement lifecycle: what happens to an edit before, at and after adoption (JH-C11 wpB).

- trial          an edit (or a combination, a consolidation, a removal) is written to a copy of the pack and
                 evaluated on the agent's golden and held-out sets and on those of every orchestrator that
                 calls it (Musk, G-M15); engine.adoption.decide rules on it
- snapshots      every text an adoption replaces or writes is kept, content-addressed, as a ``<pack>.snapshot``
                 event: a revert restores bytes from the ledger, not from memory
- anchor         generation 0 (Brown, G-B16): the agent's scores and live override rate when the loop first
                 touched it, re-scored on the current sets whenever they change; every adoption, every
                 probation and every distilled student holds against it
- probation      (the panel, G-P3) every adopted edit, consolidation and model swap is watched over its next
                 ``probation.runs`` live runs against as many before it; a fall in pass rate or a rise in the
                 operator's override rate restores the stored text and re-runs golden to confirm (``<pack>.revert``)
- revalidation   (Naval, G-NCD4) an edit adopted under another drift regime or another golden / held-out set is
                 re-scored with and without itself and reverted when it no longer helps
- combinations   (Patel, G-D14) edits rejected alone are queued and tried together, 2-3 at a time
- consolidation  (the panel, G-P4) after ``consolidate.after_edits`` adoptions on one file, or once it outgrows
                 ``consolidate.max_onboarding_tokens``, the refiner rewrites it from scratch keeping every adopted
                 rule; the rewrite is adopted only if it holds against the current file and the last base

No clock, no randomness: ordering is the ledger's.
"""

from __future__ import annotations

import hashlib
import itertools
import shutil
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from engine import adoption, escalation, rigor, rules
from engine.eval import load_golden, run_eval
from engine.events import EventLog
from engine.hashing import sha256_json
from engine.packs import load_pack

TEXT_FILES = ("skills.md", "workflow.md")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _events(engine, pack, kind: str) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{kind}", limit=100000, ascending=True)


def _log(engine, pack, kind: str, entity: str, payload: dict, source: str = "pipeline:autoloop", ref: str | None = None) -> dict:
    return EventLog(engine, pack).append(entity_type="agent_run", entity_id=entity, event_type=f"{pack.name}.{kind}",
                                         payload=payload, source=source, source_ref=ref)


def agent_files(agent_dir: Path) -> dict[str, str]:
    """The agent's editable texts: skills, workflow, prompts/*.md."""
    out = {n: (agent_dir / n).read_text(encoding="utf-8") for n in TEXT_FILES if (agent_dir / n).is_file()}
    for p in sorted((agent_dir / "prompts").glob("*.md")):
        out[f"prompts/{p.name}"] = p.read_text(encoding="utf-8")
    return out


def write(agent_dir: Path, rel: str, text: str) -> None:
    (agent_dir / rel).write_text(text, encoding="utf-8", newline="\n")


# -- evaluation on a copy -------------------------------------------------------------------------------------

def holdout_used(engine, pack, agent: str) -> bool:
    p = pack.agent_dir(agent) / "eval" / "holdout.jsonl"
    return bool(engine.config.autoloop["holdout"] and p.is_file() and load_golden(p, pack_is_fixture=pack.fixture).cases)


def evaluate(engine, pack, agent: str, use_holdout: bool) -> tuple[dict, dict | None]:
    return run_eval(engine, pack, agent), (run_eval(engine, pack, agent, golden_file="holdout.jsonl") if use_holdout else None)


@contextmanager
def pack_copy(pack, packs_root: Path, agent: str, writes: dict[str, str]):
    """A throwaway copy of the pack with ``writes`` ({path in the agent dir: text}) applied."""
    tmp = Path(tempfile.mkdtemp(prefix="autoloop-"))
    try:
        root = tmp / "packs"
        shutil.copytree(packs_root / pack.name, root / pack.name, ignore=shutil.ignore_patterns("__pycache__", ".harness", "crank", "export"))
        for rel, text in writes.items():
            write(root / pack.name / "agents" / agent, rel, text)
        yield load_pack(pack.name, root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def callers(engine, pack, agent: str) -> list[str]:
    """Orchestrators whose manifest lets them call ``agent`` and that have a golden set (G-M15)."""
    from engine.config import load_yaml
    tool = f"agent.{pack.name}.{agent}"
    return [n for n in sorted(pack.agent_names) if n != agent
            and tool in (load_yaml(pack.agent_dir(n) / "manifest.yaml").get("tools") or [])
            and (pack.agent_dir(n) / "eval" / "golden.jsonl").is_file()]


def baseline(engine, pack, agent: str, before: dict, before_h: dict | None, *, packs_root: Path) -> dict:
    """What every trial of one agent this cycle is judged against: its before scores, the anchor, the callers' before
    scores and the rule pins."""
    down = []
    if engine.config.lifecycle["system_adoption"]:
        for c in callers(engine, pack, agent):
            b, bh = evaluate(engine, pack, c, holdout_used(engine, pack, c))
            down.append({"agent": c, "before": b, "before_h": bh})
    return {"agent": agent, "before": before, "before_h": before_h, "callers": down, "pins": rules.pins(pack.agent_dir(agent)),
            "anchor": anchor_for(engine, pack, agent, before, before_h, packs_root=packs_root)}


def trial(engine, pack, agent: str, writes: dict[str, str], base: dict, *, packs_root: Path, explore: bool = False, index: int = 0) -> dict:
    """``writes`` evaluated on a copy, ruled on by the adoption law."""
    with pack_copy(pack, packs_root, agent, writes) as pc:
        after, after_h = evaluate(engine, pc, agent, base["before_h"] is not None)
        down = []
        for d in base["callers"]:
            a, ah = evaluate(engine, pc, d["agent"], d["before_h"] is not None)
            down.append({**d, "after": a, "after_h": ah})
    texts = {**agent_files(pack.agent_dir(agent)), **writes}
    broken = rules.broken(base["pins"], base["before"], after, base["before_h"], after_h) + rules.unpinned_after(pack, agent, texts)
    law = adoption.decide(engine, pack, base["before"], after, base["before_h"], after_h, anchor=base["anchor"], downstream=down,
                          broken_rules=broken, explore=explore)
    return {"index": index, "writes": writes, "after": after, "after_h": after_h, "law": law}


# -- provenance: the drift regime and the eval sets an adoption was made under -------------------------------

def regime(readings: list[dict]) -> dict:
    rows = sorted(({"id": r["id"], "shifted": bool(r["shifted"]), "regime": (r.get("measured") or {}).get("regime")} for r in readings),
                  key=lambda r: r["id"])
    return {"signature": sha256_json(rows), "readings": rows}


def regime_on_record(engine, pack) -> dict:
    """The regime of the latest ``<pack>.drift`` reading of each drift function."""
    latest = {}
    for e in _events(engine, pack, "drift"):
        latest[e["payload"]["id"]] = e["payload"]
    return regime(list(latest.values()))


def eval_shas(pack, agent: str) -> tuple[str | None, str | None]:
    out = []
    for name in ("golden.jsonl", "holdout.jsonl"):
        p = pack.agent_dir(agent) / "eval" / name
        out.append(hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
    return out[0], out[1]


def law_block(engine, pack, agent: str, t: dict, *, mode: str, edits: list[dict], candidates: int = 1,
              explore_of: str | None = None) -> dict:
    """The ``law`` field of a refinement event: the verdict's figures plus the provenance revalidation reads later."""
    g, h = eval_shas(pack, agent)
    law = t["law"]
    return {"mode": mode, "edit": edits[0] if len(edits) == 1 else None, "edits": edits if len(edits) > 1 else None,
            "deletion": any(e.get("file") == "manifest.yaml" for e in edits), "evidence": law["evidence"], "cost": law["cost"],
            "efficiency_gain": law["efficiency_gain"], "exploratory": law["exploratory"], "explore_of": explore_of,
            "anchor": law["anchor"], "downstream": law["downstream"], "regime": regime_on_record(engine, pack),
            "golden_sha256": g, "holdout_sha256": h, "candidate": t["index"], "candidates": candidates}


def refinement_payload(agent: str, rung: int, file: str, old_text: str, new_text: str, base: dict, t: dict, *, adopted: bool,
                       refiner_run_id: str, why: str, law: dict, **extra) -> dict:
    before, before_h, after, after_h = base["before"], base["before_h"], t["after"], t["after_h"]
    return {"agent": agent, "rung": int(rung), "file": file, "old_sha256": sha(old_text), "new_sha256": sha(new_text),
            "before_score": before["models"][0]["score"], "after_score": after["models"][0]["score"], "adopted": adopted,
            "refiner_run_id": refiner_run_id, "why": str(why)[:1000],
            "before_holdout": None if before_h is None else before_h["models"][0]["score"],
            "after_holdout": None if after_h is None else after_h["models"][0]["score"],
            "objective_hash": before["objective_hash"], "samples": before["samples"],
            "before_pass_at_k": before["models"][0]["pass_at_k"], "after_pass_at_k": after["models"][0]["pass_at_k"],
            "before_interval": before["models"][0]["interval"], "after_interval": after["models"][0]["interval"],
            "before_strata": before["models"][0]["strata"], "after_strata": after["models"][0]["strata"],
            "refusals": list(t["law"]["refusals"]), "law": law, **extra}


# -- snapshots ----------------------------------------------------------------------------------------------------

def snapshot(engine, pack, agent: str, file: str, text: str) -> str:
    """Keep ``text`` on the ledger under its sha256 (once per agent, file and sha)."""
    h = sha(text)
    if not any(e["payload"]["sha256"] == h and e["payload"]["agent"] == agent and e["payload"]["file"] == file
               for e in _events(engine, pack, "snapshot")):
        _log(engine, pack, "snapshot", agent, {"agent": agent, "file": file, "sha256": h, "text": text})
    return h


def text_at(engine, pack, agent: str, file: str, h: str) -> str | None:
    for e in _events(engine, pack, "snapshot"):
        p = e["payload"]
        if p["agent"] == agent and p["file"] == file and p["sha256"] == h:
            return p["text"]
    return None


def adopt_write(engine, pack, agent: str, file: str, old_text: str, new_text: str) -> None:
    snapshot(engine, pack, agent, file, old_text)
    snapshot(engine, pack, agent, file, new_text)
    write(pack.agent_dir(agent), file, new_text)


# -- the generation-0 anchor (G-B16) --------------------------------------------------------------------------------

def _live_rates(engine, pack, agent: str, rows: list[dict]) -> dict:
    verdicted = [r for r in rows if r["human_verdict"] and (r.get("verdict_source") or "human") == "human"]
    over = sum(1 for r in verdicted if r["human_verdict"] in ("overridden", "wrong"))
    return {"runs": len(rows), "pass_rate": None if not rows else round(sum(1 for r in rows if r["status"] == "succeeded") / len(rows), 6),
            "verdicts": len(verdicted), "override_rate": None if not verdicted else round(over / len(verdicted), 6)}


def anchors(engine, pack, agent: str) -> list[dict]:
    return [e for e in _events(engine, pack, "anchor") if e["payload"]["agent"] == agent]


def anchor_for(engine, pack, agent: str, before: dict, before_h: dict | None, *, packs_root: Path) -> dict | None:
    """The agent's generation 0 for its current objective: recorded from ``before`` the first time the loop refines the
    agent; re-scored (its stored texts evaluated on a copy) when the golden or held-out set has changed since."""
    if not engine.config.lifecycle["anchor"]:
        return None
    obj = before["objective_hash"]
    mine = [e for e in anchors(engine, pack, agent) if e["payload"]["objective_hash"] == obj]
    g, h = eval_shas(pack, agent)
    if not mine:
        d = pack.agent_dir(agent)
        files = {**agent_files(d), "manifest.yaml": (d / "manifest.yaml").read_text(encoding="utf-8")}
        ev = _log(engine, pack, "anchor", agent, {
            "agent": agent, "objective_hash": obj, "files": {f: snapshot(engine, pack, agent, f, t) for f, t in sorted(files.items())},
            "golden_sha256": g, "holdout_sha256": h, "golden_score": before["models"][0]["score"],
            "holdout_score": None if before_h is None else before_h["models"][0]["score"],
            "live": _live_rates(engine, pack, agent, escalation.live_runs(engine, pack, agent, int(engine.config.lifecycle["probation"]["runs"]))),
            "rescored_from": None})
        return {"event_id": ev["event_id"], **ev["payload"]}
    last = mine[-1]
    p = last["payload"]
    if p["golden_sha256"] == g and p["holdout_sha256"] == h:
        return {"event_id": last["event_id"], **p}
    writes = {f: text_at(engine, pack, agent, f, s) for f, s in p["files"].items()}
    with pack_copy(pack, packs_root, agent, {f: t for f, t in writes.items() if t is not None}) as pc:
        ag, ah = evaluate(engine, pc, agent, before_h is not None)
    ev = _log(engine, pack, "anchor", agent, {**p, "golden_sha256": g, "holdout_sha256": h, "golden_score": ag["models"][0]["score"],
                                              "holdout_score": None if ah is None else ah["models"][0]["score"], "rescored_from": last["event_id"]})
    return {"event_id": ev["event_id"], **ev["payload"]}


def anchor_gate_matrix(engine, pack, agent: str, out: dict, student: str) -> dict | None:
    """A distilled student holds against the anchor too: below it (beyond tolerance) on golden or held-out, its matrix
    row loses parity, so the manifest validator refuses the swap the matrix would otherwise permit."""
    obj = out["golden"]["objective_hash"]
    mine = [e for e in anchors(engine, pack, agent) if e["payload"]["objective_hash"] == obj]
    if not mine:
        return None
    p, tol = mine[-1]["payload"], Decimal(repr(engine.config.lifecycle["anchor_tolerance"]))
    verdict = {"event_id": mine[-1]["event_id"], "golden_score": p["golden_score"], "holdout_score": p["holdout_score"], "holds": True}
    for name, floor in (("golden", p["golden_score"]), ("holdout", p["holdout_score"])):
        if name not in out or floor is None:
            continue
        for row in out[name]["models"]:
            if row["model"] == student and Decimal(row["score"]) < Decimal(floor) - tol:
                row["parity"] = False
                verdict["holds"] = False
                verdict[f"{name}_student"] = row["score"]
    out["anchor"] = verdict
    return verdict


# -- probation and revert (G-P3) -----------------------------------------------------------------------------------

def _adoptions(engine, pack) -> list[dict]:
    items = []
    for e in _events(engine, pack, "refinement"):
        p = e["payload"]
        if p["adopted"]:
            items.append({"event": e, "kind": "edit", "agent": p["agent"], "file": p["file"], "old_sha": p["old_sha256"],
                          "new_sha": p["new_sha256"], "edit": (p.get("law") or {}).get("edit"), "after_score": p["after_score"], "model": None})
    for e in _events(engine, pack, "consolidation"):
        p = e["payload"]
        if p["adopted"]:
            items.append({"event": e, "kind": "consolidation", "agent": p["agent"], "file": p["file"], "old_sha": p["current_sha"],
                          "new_sha": p["new_sha"], "edit": None, "after_score": p["scores"]["after"]["golden"], "model": None})
    for e in _events(engine, pack, "model_swap"):
        p = e["payload"]
        if p["from"] is not None:
            items.append({"event": e, "kind": "model_swap", "agent": p["agent"], "file": "manifest.yaml", "old_sha": p["from_manifest_sha256"],
                          "new_sha": p["manifest_sha256"], "edit": None, "after_score": None, "model": (p["from"], p["to"])})
    return sorted(items, key=lambda i: i["event"]["ledger_index"])


def _restore(engine, pack, item: dict) -> tuple[str | None, str]:
    """The text a revert writes, or None with the reason it cannot be isolated."""
    path = pack.agent_dir(item["agent"]) / item["file"]
    cur = path.read_text(encoding="utf-8")
    if sha(cur) == item["new_sha"]:
        old = text_at(engine, pack, item["agent"], item["file"], item["old_sha"])
        if old is not None:
            return old, "restored the stored text"
    e = item["edit"]
    if e and e.get("new") and cur.count(e["new"]) == 1:
        return cur.replace(e["new"], e["old"], 1), "the edit undone in place (the file changed since)"
    return None, "the file changed since and the edit cannot be isolated"


def revert(engine, pack, item: dict, *, why: str, before: dict, after: dict) -> dict:
    agent, file = item["agent"], item["file"]
    cur = (pack.agent_dir(agent) / file).read_text(encoding="utf-8")
    text, how = _restore(engine, pack, item)
    if text is None:
        return {"status": "blocked", "why": how}
    adopt_write(engine, pack, agent, file, cur, text)
    fresh = load_pack(pack.name, pack.root.parent)
    golden = run_eval(engine, fresh, agent)
    ev = _log(engine, pack, "revert", agent, {"agent": agent, "file": file, "from_sha": sha(cur), "to_sha": sha(text), "before": before,
                                              "after": after, "refinement_event_id": item["event"]["event_id"], "kind": item["kind"],
                                              "golden": golden["summary"], "why": f"{why}; {how}"[:1000]})
    return {"status": "reverted", "event_id": ev["event_id"], "golden": golden["summary"], "to_sha": sha(text)}


def probation(engine, pack) -> list[dict]:
    """Close every open probation whose window has filled: passed, or reverted (or blocked when the edit cannot be undone)."""
    cfg = engine.config.lifecycle["probation"]
    n, tol = int(cfg["runs"]), engine.config.lifecycle["anchor_tolerance"]
    closed = {e["payload"]["refinement_event_id"] for e in _events(engine, pack, "adoption_probation")}
    closed |= {e["payload"]["refinement_event_id"] for e in _events(engine, pack, "revert")}
    out = []
    for item in _adoptions(engine, pack):
        eid, at = item["event"]["event_id"], item["event"]["ledger_index"]
        if eid in closed or item["agent"] not in pack.agent_names:
            continue
        rows = escalation.live_runs(engine, pack, item["agent"])
        if item["model"]:
            old_m, new_m = item["model"]
            before_rows = [r for r in rows if r["ledger_index"] < at and f"{r['provider']}/{r['model']}" == old_m][-n:]
            after_rows = [r for r in rows if r["ledger_index"] > at and f"{r['provider']}/{r['model']}" == new_m][:n]
        else:
            before_rows = [r for r in rows if r["ledger_index"] < at][-n:]
            after_rows = [r for r in rows if r["ledger_index"] > at][:n]
        if len(after_rows) < n:
            continue
        b, a = _live_rates(engine, pack, item["agent"], before_rows), _live_rates(engine, pack, item["agent"], after_rows)
        base_pass = b["pass_rate"] if b["pass_rate"] is not None else (float(item["after_score"]) if item["after_score"] else None)
        why = []
        if base_pass is not None and base_pass - a["pass_rate"] > cfg["max_pass_drop"]:
            why.append(f"live pass rate fell {base_pass} -> {a['pass_rate']} over {n} runs (max drop {cfg['max_pass_drop']})")
        if a["verdicts"] and a["verdicts"] >= cfg["min_verdicts"]:
            if a["override_rate"] - (b["override_rate"] or 0.0) > cfg["max_override_rise"]:
                why.append(f"operator override rate rose {b['override_rate'] or 0.0} -> {a['override_rate']} (max rise {cfg['max_override_rise']})")
            anc = [x for x in anchors(engine, pack, item["agent"])]
            live0 = anc[-1]["payload"]["live"] if anc else None
            if live0 and live0.get("override_rate") is not None and a["override_rate"] > live0["override_rate"] + tol:
                why.append(f"override rate {a['override_rate']} is above the generation-0 anchor's {live0['override_rate']} (tolerance {tol})")
        res = revert(engine, pack, item, why="; ".join(why), before=b, after=a) if why else {"status": "passed"}
        outcome = {"passed": "passed", "reverted": "reverted", "blocked": "blocked"}[res["status"]]
        _log(engine, pack, "adoption_probation", item["agent"], {"refinement_event_id": eid, "agent": item["agent"], "file": item["file"],
                                                                 "kind": item["kind"], "outcome": outcome, "before": b, "after": a,
                                                                 "why": "; ".join(why) or res.get("why") or "the live record held"})
        out.append({"refinement_event_id": eid, "agent": item["agent"], "kind": item["kind"], "outcome": outcome, "why": why, **res})
    return out


def track_models(engine, pack) -> list[dict]:
    """A ``<pack>.model_swap`` event whenever a worker's / specialist's / orchestrator's manifest model changes (the
    first sighting records the baseline); the manifest text is snapshotted so a failed probation can restore it."""
    from engine.manifest import load_agent
    last = {}
    for e in _events(engine, pack, "model_swap"):
        last[e["payload"]["agent"]] = e["payload"]
    out = []
    for name in escalation.judgeable(pack):
        agent = load_agent(pack, name, config=engine.config)
        text = (agent.dir / "manifest.yaml").read_text(encoding="utf-8")
        model = agent.model.model_string
        prev = last.get(name)
        if prev is not None and prev["to"] == model:
            continue
        h = snapshot(engine, pack, name, "manifest.yaml", text)
        out.append(_log(engine, pack, "model_swap", name, {"agent": name, "from": None if prev is None else prev["to"], "to": model,
                                                           "manifest_sha256": h,
                                                           "from_manifest_sha256": None if prev is None else prev["manifest_sha256"]})["payload"])
    return out


# -- revalidation when the regime or the eval sets change (G-NCD4) ---------------------------------------------------

def revalidate(engine, pack, readings: list[dict], *, packs_root: Path) -> dict:
    cfg = engine.config.lifecycle
    if not cfg["revalidate_on_drift"]:
        return {"status": "off", "results": []}
    if any(r["shifted"] for r in readings):
        return {"status": "held", "why": "a drift reading says shifted: edits are re-scored once the new regime is stable", "results": []}
    now = regime(readings)
    done = {(e["payload"]["refinement_event_id"], e["payload"]["regime_now"], e["payload"]["golden_now"], e["payload"]["holdout_now"])
            for e in _events(engine, pack, "revalidation")}
    gone = {e["payload"]["refinement_event_id"] for e in _events(engine, pack, "revert")}
    due = []
    for e in _events(engine, pack, "refinement"):
        p, law = e["payload"], e["payload"].get("law") or {}
        if not p["adopted"] or e["event_id"] in gone or not law.get("regime") or p["agent"] not in pack.agent_names:
            continue
        g, h = eval_shas(pack, p["agent"])
        if law["regime"]["signature"] == now["signature"] and law.get("golden_sha256") == g and law.get("holdout_sha256") == h:
            continue
        if (e["event_id"], now["signature"], g, h) not in done:
            due.append((e, g, h))
    results = []
    for e, g, h in due[:int(cfg["revalidate_max_per_cycle"])]:
        p, law = e["payload"], e["payload"]["law"]
        agent, file = p["agent"], p["file"]
        item = {"event": e, "agent": agent, "file": file, "old_sha": p["old_sha256"], "new_sha": p["new_sha256"], "edit": law.get("edit"),
                "kind": "edit"}
        cur = (pack.agent_dir(agent) / file).read_text(encoding="utf-8")
        without, how = _restore(engine, pack, item)
        payload = {"refinement_event_id": e["event_id"], "agent": agent, "file": file, "regime_then": law["regime"]["signature"],
                   "regime_now": now["signature"], "golden_then": law.get("golden_sha256"), "golden_now": g,
                   "holdout_then": law.get("holdout_sha256"), "holdout_now": h, "with": None, "without": None}
        if without is None:
            payload.update(outcome="skipped", why=how)
        else:
            use_h = holdout_used(engine, pack, agent)
            w, wh = evaluate(engine, pack, agent, use_h)
            base = {"before": w, "before_h": wh, "callers": [], "pins": rules.pins(pack.agent_dir(agent)), "anchor": None}
            t = trial(engine, pack, agent, {file: without}, base, packs_root=packs_root)
            payload["with"] = {"golden": w["models"][0]["score"], "holdout": None if wh is None else wh["models"][0]["score"]}
            payload["without"] = {"golden": t["after"]["models"][0]["score"], "holdout": None if t["after_h"] is None else t["after_h"]["models"][0]["score"]}
            if t["law"]["adopted"]:
                adopt_write(engine, pack, agent, file, cur, without)
                _log(engine, pack, "revert", agent, {"agent": agent, "file": file, "from_sha": sha(cur), "to_sha": sha(without),
                                                     "before": payload["with"], "after": payload["without"], "refinement_event_id": e["event_id"],
                                                     "kind": "revalidation", "golden": t["after"]["summary"],
                                                     "why": "under the current regime and sets the edit no longer helps: without it the law holds"})
                payload.update(outcome="reverted", why="without the edit the scores do not fall: it no longer helps")
            else:
                payload.update(outcome="kept", why="; ".join(t["law"]["refusals"])[:1000] or "the edit still helps")
        _log(engine, pack, "revalidation", agent, payload)
        results.append(payload)
    return {"status": "ran", "regime": now["signature"], "results": results}


# -- combinations of queued edits (G-D14) ----------------------------------------------------------------------------

def queue(engine, pack, agent: str) -> dict[str, list[dict]]:
    """{file: [rejected single edits that still apply to the file, newest first]}, at most ``refine.combo_queue`` per file."""
    cap = int(engine.config.lifecycle["refine"]["combo_queue"])
    out: dict[str, list[dict]] = {}
    seen = set()
    for e in reversed(escalation.refinements(engine, pack, agent)):
        p, law = e["payload"], e["payload"].get("law") or {}
        edit = law.get("edit")
        if p["adopted"] or p.get("combo") or law.get("mode") != "edit" or not edit:
            continue
        key = (p["file"], edit["old"], edit["new"])
        path = pack.agent_dir(agent) / p["file"]
        if key in seen or not path.is_file():
            continue
        if path.read_text(encoding="utf-8").count(edit["old"]) != 1:
            continue
        seen.add(key)
        q = out.setdefault(p["file"], [])
        if len(q) < cap:
            q.append({"event_id": e["event_id"], "rung": p["rung"], "refiner_run_id": p["refiner_run_id"], **edit})
    return out


def _apply_all(text: str, edits: list[dict]) -> str | None:
    for e in edits:
        if text.count(e["old"]) != 1:
            return None
        text = text.replace(e["old"], e["new"], 1)
    return text


def combine(engine, pack, agent: str | None, *, packs_root: Path) -> dict:
    """Try up to ``refine.max_combo`` untried 2- and 3-edit combinations of queued edits on one file; adopt the best the law adopts."""
    cfg = engine.config.lifecycle["refine"]
    targets = [agent] if agent else [a for a in escalation.judgeable(pack) if any(len(q) > 1 for q in queue(engine, pack, a).values())]
    if not targets or targets[0] is None:
        return {"status": "skipped", "why": "no agent with queued edits"}
    agent = targets[0]
    tried = {frozenset(e["payload"]["combo"]) for e in escalation.refinements(engine, pack, agent) if e["payload"].get("combo")}
    plans = []
    for file, q in sorted(queue(engine, pack, agent).items()):
        text = (pack.agent_dir(agent) / file).read_text(encoding="utf-8")
        for k in (2, 3):
            for combo in itertools.combinations(q, k):
                ids = frozenset(c["event_id"] for c in combo)
                if ids in tried or len(plans) >= int(cfg["max_combo"]):
                    continue
                new = _apply_all(text, list(combo))
                if new is not None and new != text:
                    plans.append((file, text, new, list(combo)))
                    tried.add(ids)
    if not plans:
        return {"status": "skipped", "agent": agent, "why": "no untried combination of queued edits applies"}
    use_h = holdout_used(engine, pack, agent)
    before, before_h = evaluate(engine, pack, agent, use_h)
    base = baseline(engine, pack, agent, before, before_h, packs_root=packs_root)
    trials = [dict(trial(engine, pack, agent, {f: new}, base, packs_root=packs_root, index=i), plan=(f, old, new, combo))
              for i, (f, old, new, combo) in enumerate(plans)]
    win = adoption.best(trials)
    out = []
    for t in trials:
        f, old, new, combo = t["plan"]
        adopted = t is win
        if adopted:
            adopt_write(engine, pack, agent, f, old, new)
        law = law_block(engine, pack, agent, t, mode="combo", edits=[{"file": f, "old": c["old"], "new": c["new"]} for c in combo],
                        candidates=len(trials))
        if not adopted and t["law"]["adopted"]:
            t["law"]["refusals"].append("another combination scored higher this cycle")
        ev = _log(engine, pack, "refinement", combo[-1]["refiner_run_id"], refinement_payload(
            agent, max(int(c["rung"]) for c in combo), f, old, new, base, t, adopted=adopted, refiner_run_id=combo[-1]["refiner_run_id"],
            why=f"combination of {len(combo)} edits that did not pass alone: {', '.join(c['event_id'] for c in combo)}", law=law,
            combo=[c["event_id"] for c in combo]), ref=combo[-1]["refiner_run_id"])
        out.append({"event_id": ev["event_id"], "combo": [c["event_id"] for c in combo], "adopted": adopted,
                    "after": t["after"]["summary"], "refusals": t["law"]["refusals"]})
    return {"status": "adopted" if win else "rejected", "agent": agent, "before": before["summary"], "trials": out}


# -- consolidation (G-P4) --------------------------------------------------------------------------------------------

def consolidation_due(engine, pack) -> dict | None:
    cfg = engine.config.lifecycle["consolidate"]
    cons = _events(engine, pack, "consolidation")
    for agent in escalation.judgeable(pack):
        texts = agent_files(pack.agent_dir(agent))
        for file in sorted(texts):
            last = [e for e in cons if e["payload"]["agent"] == agent and e["payload"]["file"] == file and e["payload"]["adopted"]]
            since = last[-1]["ledger_index"] if last else -1
            folded = [e for e in escalation.refinements(engine, pack, agent)
                      if e["payload"]["adopted"] and e["payload"]["file"] == file and e["ledger_index"] > since]
            big = len(texts[file]) / 4 > cfg["max_onboarding_tokens"]
            if len(folded) >= int(cfg["after_edits"]) or (big and folded):
                base = last[-1]["payload"]["new_sha"] if last else (folded[0]["payload"]["old_sha256"] if folded else None)
                return {"agent": agent, "file": file, "text": texts[file], "folded": folded, "base_sha": base,
                        "trigger": "edits" if len(folded) >= int(cfg["after_edits"]) else "size"}
    return None


def consolidate(engine, pack, runner, refiner: str, *, week: str, packs_root: Path) -> dict:
    """Ask the refiner for a from-scratch rewrite of one file that keeps every adopted rule; adopt it only when it holds
    against the current file and the last consolidated base on golden, held-out and every stratum."""
    due = consolidation_due(engine, pack)
    if due is None:
        return {"status": "skipped", "why": "no file has enough adopted edits or tokens to consolidate"}
    agent, file, text = due["agent"], due["file"], due["text"]
    evidence = [h for h in escalation.history(engine, pack, agent, limit=100) if h["event_id"] in {e["event_id"] for e in due["folded"]}]
    r = runner.run(refiner, {"agent": agent, "rung": 2, "rungs": [1, 2], "mode": "consolidate", "week": week,
                             "change": (f"Consolidate {file}: rewrite it from scratch as one clean text that keeps every rule the "
                                        f"{len(evidence)} adopted edits since the last base added (the evidence lists them)."),
                             "evidence": evidence, "files": {file: text},
                             "forecast_required": engine.config.autoloop_long_horizon["taste"]["require_forecast"]})
    if r.status != "succeeded" or r.output.get("file") is None:
        return {"status": "refiner_failed" if r.status != "succeeded" else "declined", "agent": agent, "file": file, "refiner_run_id": r.run_id}
    new = r.output["new"]
    use_h = holdout_used(engine, pack, agent)
    before, before_h = evaluate(engine, pack, agent, use_h)
    base = baseline(engine, pack, agent, before, before_h, packs_root=packs_root)
    t = trial(engine, pack, agent, {file: new}, base, packs_root=packs_root)
    refusals = list(t["law"]["refusals"])
    base_text = text_at(engine, pack, agent, file, due["base_sha"]) if due["base_sha"] else None
    scores = {"current": {"golden": before["models"][0]["score"], "holdout": None if before_h is None else before_h["models"][0]["score"]},
              "after": {"golden": t["after"]["models"][0]["score"], "holdout": None if t["after_h"] is None else t["after_h"]["models"][0]["score"]},
              "base": None}
    if base_text is not None and base_text != text:
        with pack_copy(pack, packs_root, agent, {file: base_text}) as pc:
            bg, bh = evaluate(engine, pc, agent, use_h)
        scores["base"] = {"golden": bg["models"][0]["score"], "holdout": None if bh is None else bh["models"][0]["score"]}
        if Decimal(scores["after"]["golden"]) < Decimal(scores["base"]["golden"]):
            refusals.append(f"golden {scores['after']['golden']} is below the last consolidated base's {scores['base']['golden']}")
        if bh is not None and t["after_h"] is not None and Decimal(scores["after"]["holdout"]) < Decimal(scores["base"]["holdout"]):
            refusals.append(f"held-out {scores['after']['holdout']} is below the last consolidated base's {scores['base']['holdout']}")
        refusals += [f"against the base: {x}" for x in rigor.adoption_refusals(bg, t["after"], bh, t["after_h"])]
    adopted = not refusals
    if adopted:
        adopt_write(engine, pack, agent, file, text, new)
    ev = _log(engine, pack, "consolidation", agent, {
        "agent": agent, "file": file, "base_sha": due["base_sha"], "current_sha": sha(text), "new_sha": sha(new),
        "edits_folded": [e["event_id"] for e in due["folded"]], "trigger": due["trigger"], "scores": scores, "adopted": adopted,
        "refusals": refusals, "refiner_run_id": r.run_id, "why": str(r.output.get("why", ""))[:1000]},
        source=f"agent:{refiner}", ref=r.run_id)
    return {"status": "adopted" if adopted else "rejected", "agent": agent, "file": file, "event_id": ev["event_id"],
            "edits_folded": len(due["folded"]), "scores": scores, "refusals": refusals, "refiner_run_id": r.run_id}


# -- the cycle's report ------------------------------------------------------------------------------------------------

def render_section(result: dict) -> list[str]:
    lc = result.get("lifecycle") or {}
    if not lc and not result.get("combine") and not result.get("consolidate"):
        return []
    L = ["", "## Refinement lifecycle", ""]
    for s in lc.get("model_swaps") or []:
        L.append(f"- model {s['agent']}: {s['from'] or '(first sighting)'} -> {s['to']}")
    for p in lc.get("probation") or []:
        L.append(f"- probation {p['agent']} ({p['kind']} {p['refinement_event_id']}): {p['outcome'].upper()}"
                 + (f": {'; '.join(p['why'])}" if p["why"] else "") + (f"; golden after the revert {p['golden']}" if p.get("golden") else ""))
    rv = lc.get("revalidation") or {}
    if rv.get("status") == "held":
        L.append(f"- revalidation held: {rv['why']}")
    for r in rv.get("results") or []:
        L.append(f"- revalidation {r['agent']} {r['file']} (edit {r['refinement_event_id']}): {r['outcome']}; with {r['with']} without {r['without']}")
    c = result.get("combine")
    if c:
        L.append(f"- combinations: {c['status']}" + (": " + ", ".join(f"{t['combo']} -> {t['after']}{' ADOPTED' if t['adopted'] else ''}" for t in c.get("trials") or [])
                                                     if c.get("trials") else f" ({c.get('why')})"))
    k = result.get("consolidate")
    if k:
        L.append(f"- consolidation: {k['status']}" + (f" {k['agent']} {k['file']}: {k['edits_folded']} edits folded, scores {k['scores']}"
                                                      + (f"; refused: {'; '.join(k['refusals'])}" if k["refusals"] else "")
                                                      if k["status"] in ("adopted", "rejected") else f" ({k.get('why', '')})"))
    for e in result.get("escalations") or []:
        L.append(f"- {e['event_type'].split('.')[-1]} recorded for {e['payload']['agent']}: next rung {e['payload']['next_rung']}")
    return L


def cycle_start(engine, pack, readings: list[dict], *, packs_root: Path) -> dict:
    """The lifecycle steps at the start of a cycle, before anything new is adopted: model swaps noticed, probations
    closed (reverting what the live record says got worse), edits from another regime or eval set re-scored."""
    return {"model_swaps": track_models(engine, pack), "probation": probation(engine, pack),
            "revalidation": revalidate(engine, pack, readings, packs_root=packs_root)}
