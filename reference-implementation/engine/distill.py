"""Rung four, as far as it can be built without a training API: the student learns from the record.

    python -m engine.distill <pack>/<agent> --student provider/model [--exemplars K] [--matrix] [--db DSN]

Past the export gate, the agent's runs that carry a ``followed`` verdict become the exemplars: the
input and the certified output of each, chosen most recent first and spread across distinct inputs.
The distiller writes them to ``agents/<agent>/distill/exemplars.jsonl`` (every row cites its run), and
a prompt variant ``prompts/system-<student>.md``: the agent's own system prompt followed by the
worked examples, so the student model is grounded on the record the operator and the judge graded,
not on a description of it.  The variant is registered in the manifest under ``model.variants``, which
is the engine's existing way to run one agent on another model string, so nothing else changes.

With ``--matrix`` the distiller then runs the parity matrix, frontier against student, on the golden
set and on the held-out set when one exists, and writes ``eval/matrix-<date>.*``: the only evidence a
rung-3 swap may cite.  Nothing is adopted here; adoption is the manifest edit the matrix permits.

Weight-level post-training stays outside the engine: the dataset ``engine.export`` writes is its input.
This is in-context distillation, the panel's observation that what RL learned can be copied from a
small number of certified trajectories; its limit is the context window, and the matrix measures it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from engine.config import load_yaml
from engine.errors import EngineError, GateError
from engine.eval import run_eval, write_matrix
from engine.export import check_gate, counted_runs
from engine.manifest import load_agent
from engine.packs import load_pack, parse_agent_ref
from engine.providers import parse_model_string
from engine.runtime import iso
from engine.store import Engine

MAX_EXEMPLAR_BYTES = 6000


def exemplars(engine: Engine, pack, agent_name: str, k: int) -> list[dict]:
    """The k most recent followed runs on distinct inputs, each small enough to show whole."""
    rows = counted_runs(engine, pack, agent_name, status="succeeded")
    out, seen = [], set()
    for r in reversed(rows):
        key = json.dumps(r["input"], sort_keys=True)
        if r["human_verdict"] != "followed" or key in seen:
            continue
        text = json.dumps(r["output"], sort_keys=True)
        if len(text) > MAX_EXEMPLAR_BYTES:
            continue
        seen.add(key)
        out.append({"run_id": r["run_id"], "verdict_source": r.get("verdict_source") or "human", "verdict_reason": r["verdict_reason"],
                    "input": r["input"], "output": r["output"]})
        if len(out) >= k:
            break
    return out


def student_prompt(system_prompt: str, rows: list[dict]) -> str:
    L = [system_prompt.rstrip("\n"), "",
         "Worked examples from this agent's own record. Each was certified by code and adjudicated as",
         "followed; the run id is the citation. Produce the same shape and the same discipline: every",
         "figure a copy with its citation, nothing invented.", ""]
    for i, r in enumerate(rows, 1):
        L += [f"### Example {i} (run {r['run_id']}, verdict by {r['verdict_source']}: {r['verdict_reason']})",
              "Input:", "```json", json.dumps(r["input"], sort_keys=True), "```",
              "Output:", "```json", json.dumps(r["output"], sort_keys=True), "```", ""]
    return "\n".join(L)


def distill(engine: Engine, pack, agent_name: str, student: str, k: int) -> dict:
    agent, n = check_gate(engine, pack, agent_name)
    provider, model = parse_model_string(student)
    rows = exemplars(engine, pack, agent_name, k)
    if not rows:
        raise GateError(f"no followed run of {agent.ref} is small enough to be an exemplar")
    ddir = agent.dir / "distill"
    ddir.mkdir(exist_ok=True)
    with open(ddir / "exemplars.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"agent": agent.ref, "student": student, "gate_verdicted_runs": n, "written_at": iso(engine.clock.now())}) + "\n")
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    prompt_name = f"system-{model}.md"
    (agent.dir / "prompts" / prompt_name).write_text(student_prompt(agent.model.system_prompt, rows), encoding="utf-8", newline="\n")
    mpath = agent.dir / "manifest.yaml"
    manifest = load_yaml(mpath)
    manifest["model"].setdefault("variants", {})[model] = {"system_prompt_file": f"prompts/{prompt_name}"}
    mpath.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {"agent": agent.ref, "student": student, "exemplars": len(rows), "gate_verdicted_runs": n,
            "prompt": str(agent.dir / "prompts" / prompt_name), "exemplar_file": str(ddir / "exemplars.jsonl")}


def matrix(engine: Engine, pack, agent_name: str, student: str, date: str) -> dict:
    """The student against the model the agent runs on today, on the golden set and the held-out set."""
    agent = load_agent(pack, agent_name, config=engine.config)
    teacher = agent.model.model_string
    out = {"golden": run_eval(engine, pack, agent_name, models=[teacher, student], reference=teacher)}
    if (agent.dir / "eval" / "holdout.jsonl").is_file():
        out["holdout"] = run_eval(engine, pack, agent_name, models=[teacher, student], golden_file="holdout.jsonl", reference=teacher)
    md, js = write_matrix(agent.dir, out["golden"], date)
    if "holdout" in out:
        write_matrix(agent.dir, out["holdout"], f"{date}-holdout")
    out["written"] = str(md)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.distill")
    p.add_argument("agent_ref")
    p.add_argument("--student", required=True, help="provider/model the exemplars are distilled into")
    p.add_argument("--exemplars", type=int, default=12)
    p.add_argument("--matrix", action="store_true", help="then run the parity matrix on golden and held-out")
    p.add_argument("--db")
    p.add_argument("--date")
    a = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(a.agent_ref)
        engine = Engine.open(a.db)
        try:
            pack = load_pack(pack_name)
            res = distill(engine, pack, agent_name, a.student, a.exemplars)
            print(f"distilled {res['exemplars']} exemplars of {res['agent']} into {res['student']} ({res['gate_verdicted_runs']} verdicted runs past the gate): {res['prompt']}")
            if a.matrix:
                date = a.date or iso(engine.clock.now())[:10]
                m = matrix(engine, load_pack(pack_name), agent_name, a.student, date)
                for name in ("golden", "holdout"):
                    if name in m:
                        rows = {r["model"]: r for r in m[name]["models"]}
                        s = rows[a.student]
                        teacher = [r for r in m[name]["models"] if r["model"] != a.student][0]
                        print(f"{name}: student {s['score']} ({s['passed']}/{s['counted']}) parity={'yes' if s['parity'] else 'no'}; teacher {teacher['model']} {teacher['score']}")
                print(f"matrix: {m['written']}")
        finally:
            engine.close()
    except GateError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
