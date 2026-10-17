"""Post-training export, gated.

    python -m engine.export <pack>/<specialist> --format sft|preference --out FILE [--db DSN]

Refuses unless the agent is a specialist and at least ``export.min_verdicted_runs``
(config/engine.yaml, 500) of its runs carry a verdict that counts: a human's always,
a judge agent's when ``export.accept_agent_verdicts`` is true.  Output is a JSONL
dataset file only; training and hosting are outside the engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

from engine.errors import EngineError, GateError
from engine.loop import SUBMIT_TOOL
from engine.manifest import load_agent
from engine.packs import load_pack, parse_agent_ref
from engine.store import Engine

FORMATS = ("sft", "preference")


def _accepted_candidate(row: dict) -> dict | None:
    for it in row["iterations"]:
        for cand in it.get("candidates", []):
            if cand.get("accepted"):
                return cand
    return None


def _rejected_candidates(row: dict) -> list[dict]:
    out = []
    for it in row["iterations"]:
        for cand in it.get("candidates", []):
            if not cand.get("accepted") and cand.get("output") is not None:
                out.append(cand)
    return out


def counted_runs(engine: Engine, pack, agent_name: str, **kw) -> list[dict]:
    """Verdicted runs whose verdict counts: human always; agent when config says so."""
    rows = engine.store.list_runs(pack=pack.name, agent=agent_name, verdicted=True, **kw)
    if engine.config.export_accepts_agent_verdicts:
        return rows
    return [r for r in rows if (r.get("verdict_source") or "human") == "human"]


def check_gate(engine: Engine, pack, agent_name: str) -> tuple[object, int]:
    agent = load_agent(pack, agent_name, config=engine.config)
    if agent.role != "specialist":
        raise GateError(f"export refused: {agent.ref} has role {agent.role!r}; only specialists are post-trained")
    n = len(counted_runs(engine, pack, agent_name))
    need = engine.config.export_min_verdicts
    if n < need:
        raise GateError(f"export refused: {n} verdicted runs for {agent.ref}, gate is {need}")
    return agent, n


def sft_rows(engine: Engine, pack, agent) -> Iterator[dict]:
    """Runs a human marked ``followed``: the accepted candidate's full exchange."""
    for row in counted_runs(engine, pack, agent.name, status="succeeded"):
        if row["human_verdict"] != "followed":
            continue
        cand = _accepted_candidate(row)
        if cand is None:
            continue
        yield {
            "run_id": row["run_id"],
            "manifest_hash": row["manifest_hash"],
            "model": f"{row['provider']}/{row['model']}",
            "system": agent.model.system_prompt,
            "messages": cand["messages"],
            "output": row["output"],
            "verdict": row["human_verdict"],
            "verdict_reason": row["verdict_reason"],
            "verdict_source": row.get("verdict_source") or "human",
        }


def preference_rows(engine: Engine, pack, agent) -> Iterator[dict]:
    """Pairs: chosen = accepted + followed; rejected = a failed candidate of the same run,
    or the output of a run on the same input the human marked wrong/overridden."""
    runs = counted_runs(engine, pack, agent.name)
    bad_by_input: dict[str, list[dict]] = {}
    for row in runs:
        if row["human_verdict"] not in ("wrong", "overridden"):
            continue
        # a run the human rejected: its certified output if it had one, else the
        # discarded candidates the harness already rejected (output is null on failed runs)
        outputs = [row["output"]] if row["output"] is not None else [c["output"] for c in _rejected_candidates(row)]
        for out in outputs:
            bad_by_input.setdefault(row["input_hash"], []).append({**row, "output": out})
    for row in runs:
        if row["human_verdict"] != "followed" or row["status"] != "succeeded":
            continue
        cand = _accepted_candidate(row)
        if cand is None:
            continue
        prompt = cand["messages"][0] if cand["messages"] else None
        for rej in _rejected_candidates(row):
            yield {"run_id": row["run_id"], "prompt": prompt, "chosen": row["output"],
                   "rejected": rej["output"], "rejected_reason": rej.get("failure_reasons") or
                   [g for g in rej.get("guardrails", []) if not g["passed"]], "source": "intra_run"}
        for bad in bad_by_input.get(row["input_hash"], []):
            yield {"run_id": row["run_id"], "prompt": prompt, "chosen": row["output"],
                   "rejected": bad["output"], "rejected_reason": [bad["verdict_reason"]],
                   "source": f"human:{bad['run_id']}"}


def export(engine: Engine, pack, agent_name: str, fmt: str, out: Path) -> int:
    if fmt not in FORMATS:
        raise EngineError(f"format must be one of {FORMATS}")
    agent, _ = check_gate(engine, pack, agent_name)
    rows = sft_rows(engine, pack, agent) if fmt == "sft" else preference_rows(engine, pack, agent)
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
            n += 1
    if n == 0:
        raise GateError("export refused: gate met but no exportable rows (no followed runs)")
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.export")
    p.add_argument("agent_ref")
    p.add_argument("--format", choices=FORMATS, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            n = export(engine, load_pack(pack_name), agent_name, args.format, Path(args.out))
        finally:
            engine.close()
    except GateError as e:
        print(str(e), file=sys.stderr)
        return 2
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {n} {args.format} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
