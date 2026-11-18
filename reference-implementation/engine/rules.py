"""The instruction ledger: every rule an agent is told is pinned, and an edit that breaks one is named (JH-C11 wpB, G-M13).

A rule line in ``skills.md`` or ``workflow.md`` carries an id, ``[R7]``.  Each id is pinned by at least one
golden or held-out case that lists it (``"pins": ["R7"]``), or is named in the pack's ``problem.md`` (the
objective itself states it).  ``engine.validate`` refuses an unpinned rule (``autoloop.rules.require_pins``).

An edit that contradicts an earlier rule is caught by that rule's pinning case: adoption already runs the
golden and held-out sets, and ``broken`` names every rule whose pinning case passed before the edit and fails
after it.  An edit may not reuse an id for a different rule, and a rule line it adds to a ledgered file must
carry a new id; a new id with no pinning case is refused at adoption (``unpinned_after``).

Pure text and JSON: no clock, no randomness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RULE_RE = re.compile(r"\[(R\d+)\]")
LEDGER_FILES = ("skills.md", "workflow.md")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def rule_ids(text: str) -> list[str]:
    return sorted(set(RULE_RE.findall(text or "")), key=lambda r: int(r[1:]))


def rule_lines(text: str) -> dict[str, str]:
    """{id: the line that declares it} (the first line carrying the id)."""
    out = {}
    for ln in (text or "").splitlines():
        for rid in RULE_RE.findall(ln):
            out.setdefault(rid, ln.strip())
    return out


def pins(agent_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """{rule id: [(eval file, case id)]} from the ``pins`` field of every golden and held-out case."""
    out: dict[str, list[tuple[str, str]]] = {}
    for name in ("golden.jsonl", "holdout.jsonl"):
        p = agent_dir / "eval" / name
        if not p.is_file():
            continue
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for ln in lines[1:]:
            case = json.loads(ln)
            for rid in case.get("pins") or []:
                out.setdefault(str(rid), []).append((name, str(case["id"])))
    return out


def ledger(pack, agent_name: str, texts: dict[str, str] | None = None) -> dict:
    """The agent's rules, where each is declared, its pins, and the ones neither pinned nor named in problem.md."""
    d = pack.agent_dir(agent_name)
    texts = texts if texts is not None else {f: (d / f).read_text(encoding="utf-8") for f in LEDGER_FILES if (d / f).is_file()}
    declared = {rid: f for f, t in texts.items() if f in LEDGER_FILES for rid in rule_ids(t)}
    pinned = pins(d)
    linked = set(rule_ids(pack.problem_text or ""))
    return {"rules": declared, "pins": {k: v for k, v in pinned.items() if k in declared},
            "unpinned": sorted((r for r in declared if r not in pinned and r not in linked), key=lambda r: int(r[1:]))}


def edit_problems(text: str, old: str, new: str) -> list[str]:
    """An edit to a ledgered file may not give an existing id to another rule, and each rule line it adds
    (a list item) carries a new id."""
    if not RULE_RE.search(text):
        return []
    out = []
    rest = rule_lines(text.replace(old, "", 1))
    for rid, line in sorted(rule_lines(new).items()):
        if rid in rest and rest[rid] != line:
            out.append(f"rule id {rid} already names another rule ({rest[rid]!r}); a new rule takes a new id")
    old_lines = set(old.splitlines())
    for ln in new.splitlines():
        if ln not in old_lines and _BULLET.match(ln) and not RULE_RE.search(ln):
            out.append(f"the rule line {ln.strip()!r} added to a ledgered file carries no [Rn] id")
    return out


def broken(pins_map: dict[str, list[tuple[str, str]]], before: dict, after: dict, before_h: dict | None, after_h: dict | None) -> list[str]:
    """Refusals naming each rule whose pinning case passed before the edit and fails after it."""
    def passed(ev):
        return {} if ev is None else {c["id"]: c["passed"] for c in ev["models"][0].get("cases") or []}
    sets = {"golden.jsonl": (passed(before), passed(after)), "holdout.jsonl": (passed(before_h), passed(after_h))}
    out = []
    for rid in sorted(pins_map, key=lambda r: int(r[1:])):
        for fname, cid in pins_map[rid]:
            b, a = sets[fname]
            if b.get(cid) and cid in a and not a[cid]:
                out.append(f"rule {rid} broken: its pinning case {cid} ({fname}) passed before the edit and fails after it")
                break
    return out


def unpinned_after(pack, agent_name: str, texts_after: dict[str, str]) -> list[str]:
    """Refusals for rule ids the edited files declare that no case pins and problem.md does not name."""
    before = set(ledger(pack, agent_name)["unpinned"])
    return [f"rule {rid} is pinned by no golden case and not named in problem.md" for rid in ledger(pack, agent_name, texts_after)["unpinned"]
            if rid not in before]
