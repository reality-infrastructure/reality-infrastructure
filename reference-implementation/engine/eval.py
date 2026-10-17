"""Eval harness and model matrix.

    python -m engine.eval <pack>/<agent> [--models provider/a,provider/b] [--db DSN]

Golden set: ``packs/<pack>/agents/<agent>/eval/golden.jsonl``.  Line 1 is the
header ``{"threshold": 0.9, "compare": ["field", ...], "fixture": true|false}``;
every following line is a case ``{"id", "input", "expected", "provenance",
"fixture"?}``.  Golden cases come from real history; ``provenance`` is
required.  Cases flagged ``fixture: true`` are excluded from a real pack's
threshold.

Prints exactly one summary line: ``PASS (k/n >= t)`` or ``FAIL (k/n < t)``.
With ``--models`` it also writes ``eval/matrix-<date>.md`` and ``.json``:
score, cost/run, latency per model, and whether each model is at parity
with the frontier on the same golden set.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from engine.errors import EngineError, EvalError
from engine.loop import Runner
from engine.packs import load_pack, parse_agent_ref
from engine.providers import parse_model_string
from engine.schema import get_path
from engine.store import Engine


@dataclass(frozen=True)
class GoldenCase:
    id: str
    input: dict
    expected: dict
    provenance: str
    fixture: bool


@dataclass(frozen=True)
class GoldenSet:
    threshold: Decimal
    compare: tuple[str, ...]
    fixture: bool
    cases: tuple[GoldenCase, ...]


def load_golden(path: Path, *, pack_is_fixture: bool) -> GoldenSet:
    if not path.is_file():
        raise EvalError(f"no golden set at {path}")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise EvalError(f"{path}: empty golden file")
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as e:
        raise EvalError(f"{path}: header is not JSON: {e}") from e
    for key in ("threshold", "compare", "fixture"):
        if key not in header:
            raise EvalError(f"{path}: header lacks {key!r}")
    threshold = Decimal(str(header["threshold"]))
    if not (Decimal(0) <= threshold <= Decimal(1)):
        raise EvalError(f"{path}: threshold must be in [0,1]")
    if header["fixture"] and not pack_is_fixture:
        raise EvalError(f"{path}: a real pack's golden set may not be flagged fixture")
    cases = []
    seen = set()
    for n, line in enumerate(lines[1:], start=2):
        try:
            c = json.loads(line)
        except json.JSONDecodeError as e:
            raise EvalError(f"{path}:{n}: not JSON: {e}") from e
        for key in ("id", "input", "expected", "provenance"):
            if key not in c:
                raise EvalError(f"{path}:{n}: case lacks {key!r}")
        if not isinstance(c["provenance"], str) or not c["provenance"].strip():
            raise EvalError(f"{path}:{n}: provenance must say where the real historical answer came from")
        if c["id"] in seen:
            raise EvalError(f"{path}:{n}: duplicate case id {c['id']!r}")
        seen.add(c["id"])
        is_fixture = bool(c.get("fixture", header["fixture"]))
        if is_fixture and not pack_is_fixture:
            # excluded from real-domain thresholds, but kept visible
            pass
        cases.append(GoldenCase(id=str(c["id"]), input=c["input"], expected=c["expected"],
                                provenance=c["provenance"], fixture=is_fixture))
    return GoldenSet(threshold=threshold, compare=tuple(header["compare"]),
                     fixture=bool(header["fixture"]), cases=tuple(cases))


def _normalize(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(Decimal(str(v)).normalize())
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in sorted(v.items())}
    return v


def case_passes(output, expected: dict, compare: tuple[str, ...]) -> tuple[bool, list[str]]:
    if output is None:
        return False, ["no output"]
    diffs = []
    for path in compare:
        try:
            got = get_path(output, path)
        except (KeyError, IndexError, ValueError):
            diffs.append(f"{path}: missing in output")
            continue
        try:
            want = get_path(expected, path)
        except (KeyError, IndexError, ValueError):
            diffs.append(f"{path}: missing in expected")
            continue
        if _normalize(got) != _normalize(want):
            diffs.append(f"{path}: got {got!r}, expected {want!r}")
    return not diffs, diffs


@dataclass
class ModelReport:
    model: str
    passed: int = 0
    counted: int = 0
    excluded: int = 0
    cost: Decimal = Decimal(0)
    latency_ms: int = 0
    runs: int = 0
    cases: list[dict] = field(default_factory=list)

    @property
    def score(self) -> Decimal:
        return Decimal(0) if self.counted == 0 else (Decimal(self.passed) / Decimal(self.counted)).quantize(Decimal("0.0001"))

    @property
    def mean_cost(self) -> Decimal:
        return Decimal(0) if self.runs == 0 else (self.cost / self.runs).quantize(Decimal("0.00000001"))

    @property
    def mean_latency_ms(self) -> int:
        return 0 if self.runs == 0 else self.latency_ms // self.runs


def run_eval(engine: Engine, pack, agent_name: str, *, models: list[str] | None = None,
             golden_file: str = "golden.jsonl") -> dict:
    """``golden_file`` may name ``holdout.jsonl``: the held-out set the loop never tunes on."""
    runner = Runner(engine, pack)
    agent = runner.agent(agent_name)
    golden = load_golden(agent.dir / "eval" / golden_file, pack_is_fixture=pack.fixture)
    model_strings = models or [agent.model.model_string]
    reports: dict[str, ModelReport] = {}
    for ms in model_strings:
        provider, name = parse_model_string(ms)
        rep = ModelReport(model=ms)
        for case in golden.cases:
            counted = pack.fixture or not case.fixture
            result = runner.run(agent_name, case.input, model_override=(provider, name),
                                enforce_economics=False)
            ok, diffs = case_passes(result.output, case.expected, golden.compare)
            rep.runs += 1
            rep.cost += result.cost_usd
            rep.latency_ms += int(result.row["latency_ms"])
            if counted:
                rep.counted += 1
                rep.passed += int(ok)
            else:
                rep.excluded += 1
            rep.cases.append({"id": case.id, "run_id": result.run_id, "status": result.status,
                              "passed": ok, "counted": counted, "diffs": diffs})
        reports[ms] = rep
    if all(r.counted == 0 for r in reports.values()):
        raise EvalError("no countable golden cases (a real pack cannot be scored on fixture cases)")
    frontier = engine.config.frontier.model_string
    frontier_score = reports[frontier].score if frontier in reports else None
    rows = []
    for ms, rep in reports.items():
        parity = None if frontier_score is None else bool(rep.score >= frontier_score)
        rows.append({"model": ms, "score": str(rep.score), "passed": rep.passed, "counted": rep.counted,
                     "excluded": rep.excluded, "mean_cost_usd": str(rep.mean_cost),
                     "mean_latency_ms": rep.mean_latency_ms, "parity": parity, "cases": rep.cases})
    primary = reports[model_strings[0]]
    return {"agent": agent.ref, "manifest_hash": agent.hash, "threshold": str(golden.threshold),
            "compare": list(golden.compare), "frontier": frontier, "frontier_score":
            None if frontier_score is None else str(frontier_score),
            "models": rows, "primary": primary.model,
            "pass": primary.score >= golden.threshold,
            "summary": _summary_line(primary, golden.threshold)}


def _summary_line(rep: ModelReport, threshold: Decimal) -> str:
    verdict = "PASS" if rep.score >= threshold else "FAIL"
    op = ">=" if verdict == "PASS" else "<"
    return f"{verdict} ({rep.passed}/{rep.counted} {op} {threshold})"


def write_matrix(agent_dir: Path, report: dict, date: str) -> tuple[Path, Path]:
    eval_dir = agent_dir / "eval"
    eval_dir.mkdir(exist_ok=True)
    json_path = eval_dir / f"matrix-{date}.json"
    md_path = eval_dir / f"matrix-{date}.md"
    slim = {k: v for k, v in report.items() if k != "models"}
    slim["models"] = [{k: v for k, v in r.items() if k != "cases"} for r in report["models"]]
    json_path.write_text(json.dumps(slim, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# Eval matrix — {report['agent']} — {date}", "",
             f"manifest_hash: `{report['manifest_hash']}`  ",
             f"threshold: {report['threshold']}  frontier: `{report['frontier']}`  "
             f"frontier_score: {report['frontier_score']}", "",
             "| model | score | passed/counted | excluded | mean cost USD | mean latency ms | parity |",
             "|---|---|---|---|---|---|---|"]
    for r in report["models"]:
        parity = "n/a (frontier not in matrix)" if r["parity"] is None else ("yes" if r["parity"] else "no")
        lines.append(f"| `{r['model']}` | {r['score']} | {r['passed']}/{r['counted']} | {r['excluded']} | "
                     f"{r['mean_cost_usd']} | {r['mean_latency_ms']} | {parity} |")
    lines += ["", "A downgrade is permitted only for a row with parity = yes (score >= frontier score "
              "on the same golden set).  The manifest validator reads the JSON twin of this file."]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.eval")
    p.add_argument("agent_ref")
    p.add_argument("--models", help="comma-separated provider/model strings; writes eval/matrix-<date>.*")
    p.add_argument("--db")
    p.add_argument("--date", help="matrix date stamp (default: today UTC)")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            models = [m.strip() for m in args.models.split(",")] if args.models else None
            report = run_eval(engine, pack, agent_name, models=models)
            if models:
                date = args.date or engine.clock.now().date().isoformat()
                md, js = write_matrix(pack.agent_dir(agent_name), report, date)
                print(f"matrix written: {md} , {js}")
        finally:
            engine.close()
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(report["summary"])
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
