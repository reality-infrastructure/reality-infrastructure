"""The conditions an experiment puts a run under (JH-C11 wpC).

One ``Experiment`` rides on a ``Runner`` (``runner.experiment``) for the length of an eval batch, an ablation, a
grid cell, a probe or a soak.  It can

- swap an agent for a *variant* (a component removed, another prompt or onboarding file): the run is recorded under
  a derived manifest hash ``x-<sha256>``, so it never passes for the agent's version and the kill rule, reputation,
  tier promotion and suspect detection leave it out (``is_experiment_run``);
- *frame* the run under evaluation: a structured ``framing`` object (counterpart, test cue, the operator's preferred
  answer) placed in its working context (engine/probes.py, Brown G-B19);
- put the run at a *point in time*: a golden case's ``as_of`` filters every read the run and its children make to
  records observed at or before it (events, runs, tables with an ``as_of_field``), stamps the cutoff on every tool
  call of the trace, and adds the ``no_future_citation`` guardrail (Patel G-D10);
- *isolate* the event channel: runs of one batch cannot read what another case of the same batch wrote (events whose
  ``source_ref`` is that run, and those runs themselves).  Reads the engine makes for grounding and memory are
  filtered silently; a read the model asked for that would have crossed is a side channel: it is recorded as
  ``<pack>.side_channel`` and fails the case (Brown G-B23).

Nothing here reads the wall clock: the cutoff is the case's, the batch id comes from the engine's id generator.
"""

from __future__ import annotations

import contextlib
import dataclasses
import threading
from datetime import timedelta
from typing import Any, Callable

from engine.errors import ToolError
from engine.hashing import sha256_json
from engine.runtime import iso, parse_iso

EXPERIMENT_HASH_PREFIX = "x-"           # a run of an agent variant: never the agent's version
SOAK_SESSION_PREFIX = "soak:"           # engine/soak.py
EVAL_SESSION_PREFIX = "eval:"           # engine/runctx.run_session_case
FUTURE_GUARDRAIL = "no_future_citation"


def is_experiment_run(row: dict) -> bool:
    """A run made under an experimental condition (a variant, a framing, a soak): it is evidence about the
    experiment, not about how the agent's version performs on its work."""
    return str(row.get("manifest_hash") or "").startswith(EXPERIMENT_HASH_PREFIX) or \
        str(row.get("session_id") or "").startswith(SOAK_SESSION_PREFIX)


def variant_hash(base_hash: str, label: str) -> str:
    return EXPERIMENT_HASH_PREFIX + sha256_json({"of": base_hash, "variant": label})


@dataclasses.dataclass
class Experiment:
    label: str = "eval"
    variants: dict[str, Callable] = dataclasses.field(default_factory=dict)   # agent name -> Agent -> Agent
    variant_id: str | None = None
    framing: dict | None = None
    isolate: bool | None = None          # None: config eval.isolate_events
    auto_case: bool = False              # every top-level run starts its own case (trap and honeypot batches)
    marked: bool = False                 # every top-level run is an experiment run, framed or not (a probe's baseline)
    batch: str | None = None
    as_of: str | None = None             # the current case's cutoff (ISO), set by begin_case
    case_id: str | None = None
    side_channels: list[dict] = dataclasses.field(default_factory=list)
    unfiltered_tables: set[str] = dataclasses.field(default_factory=set)
    _batch_runs: set[str] = dataclasses.field(default_factory=set)
    _case_runs: set[str] = dataclasses.field(default_factory=set)
    _case_side: list[dict] = dataclasses.field(default_factory=list)
    _lock: Any = dataclasses.field(default_factory=threading.Lock)

    def bind(self, engine) -> "Experiment":
        if self.isolate is None:
            self.isolate = bool(engine.config.experiments["isolate_events"])
        if self.batch is None:
            self.batch = f"{self.label}:{engine.ids.new()}"
        return self

    # -- cases ------------------------------------------------------------------------------------------

    def begin_case(self, case_id: str | None = None, *, as_of: str | None = None) -> None:
        with self._lock:
            self.case_id, self.as_of = case_id, as_of
            self._case_runs = set()
            self._case_side = []

    def end_case(self) -> list[dict]:
        """The side channels the model of this case tried; a non-empty list fails the case."""
        with self._lock:
            out, self._case_side = list(self._case_side), []
            self.as_of = None
            return out

    def started(self, run_id: str, parent_run_id: str | None) -> None:
        with self._lock:
            if self.auto_case and parent_run_id is None:
                self._case_runs = set()
            self._batch_runs.add(run_id)
            self._case_runs.add(run_id)

    def hidden(self) -> frozenset[str]:
        """Runs of this batch outside the current case: what an isolated run may not see."""
        if not self.isolate:
            return frozenset()
        with self._lock:
            return frozenset(self._batch_runs - self._case_runs)

    # -- the run ----------------------------------------------------------------------------------------

    def apply(self, agent, depth: int):
        """The agent this run executes: its variant, framed at the top level, at the case's point in time."""
        labels, base_hash = [], agent.hash
        transform = self.variants.get(agent.name)
        if transform is not None:
            agent = transform(agent)
            labels.append(self.variant_id or self.label)
        if self.framing is not None and depth == 0:
            labels.append(f"framing:{sha256_json(self.framing)}")
        elif self.marked and depth == 0:
            labels.append(self.label)
        if labels:
            agent = dataclasses.replace(agent, hash=variant_hash(base_hash, "|".join(labels)))
        if self.as_of is not None:
            guardrails = agent.guardrails if FUTURE_GUARDRAIL in agent.guardrails else agent.guardrails + (FUTURE_GUARDRAIL,)
            agent = dataclasses.replace(agent, guardrails=guardrails,
                                        manifest={**agent.manifest, "experiment": {"as_of": self.as_of}})
        return agent

    def frame(self, context: dict, depth: int) -> None:
        if self.framing is not None and depth == 0:
            context["framing"] = dict(self.framing)
        if self.as_of is not None:
            context["as_of"] = self.as_of

    def _side_channel(self, ctx, channel: str, authors: set[str], refs: list[str]) -> None:
        record = {"batch": self.batch, "label": self.label, "case": self.case_id, "reader_run_id": ctx.run_id,
                  "agent": ctx.agent.name, "channel": channel, "authors": sorted(authors), "refs": sorted(refs)[:50]}
        with self._lock:
            self._case_side.append(record)
            self.side_channels.append(record)
        ctx.extra["events"].append(entity_type="agent_run", entity_id=ctx.run_id,
                                   event_type=f"{ctx.pack.name}.side_channel", payload=record,
                                   source="pipeline:eval", source_ref=ctx.run_id)


# -- hooks the tools and the memory call ------------------------------------------------------------------

def cutoff(agent) -> str | None:
    """The point in time the run is held to (a backtest case's ``as_of``), or None."""
    manifest = getattr(agent, "manifest", None) or {}
    return (manifest.get("experiment") or {}).get("as_of")


def run_until(agent) -> str | None:
    """``until`` (exclusive) for store.list_runs / query_events that keeps records at or before the cutoff."""
    cut = cutoff(agent)
    return None if cut is None else iso(parse_iso(cut) + timedelta(microseconds=1))


def _experiment(ctx) -> Experiment | None:
    return (ctx.extra or {}).get("experiment")


def _asked_by_model(ctx) -> bool:
    """The model's own tool call (a candidate is being proposed), not a grounding or memory read."""
    return ctx.extra.get("candidate") is not None


def query_events(ctx, log, filters: dict, limit: int) -> list[dict]:
    """events.query under the run's cutoff and its batch's isolation."""
    until = run_until(ctx.agent)
    if until is not None:
        filters = {**filters, "until": until if filters.get("until") is None else min(until, filters["until"])}
    rows = log.query(limit=limit, **filters)
    exp = _experiment(ctx)
    hidden = exp.hidden() if exp is not None else frozenset()
    if not hidden:
        return rows
    n = limit
    while len(rows) == n and sum(1 for r in rows if r.get("source_ref") not in hidden) < limit:
        n *= 2
        rows = log.query(limit=n, **filters)
    crossed = [r for r in rows if r.get("source_ref") in hidden]
    if crossed and _asked_by_model(ctx):
        exp._side_channel(ctx, "events", {r["source_ref"] for r in crossed}, [r["event_id"] for r in crossed])
    return [r for r in rows if r.get("source_ref") not in hidden][:limit]


def check_run(ctx, row: dict) -> None:
    """agent_output.read / agent_run.read: a run after the cutoff, or of another case of the batch, is not there."""
    cut = cutoff(ctx.agent)
    if cut is not None and parse_iso(row["created_at"]) > parse_iso(cut):
        raise ToolError(f"run {row['run_id']!r} was created after this run's as_of {cut}")
    exp = _experiment(ctx)
    hidden = exp.hidden() if exp is not None else frozenset()
    if row["run_id"] in hidden or row.get("parent_run_id") in hidden:
        if _asked_by_model(ctx):
            exp._side_channel(ctx, "runs", {row.get("parent_run_id") or row["run_id"]}, [row["run_id"]])
        raise ToolError(f"run {row['run_id']!r} is not visible to this run (isolated evaluation)")


def visible_runs(ctx, rows: list[dict]) -> list[dict]:
    """runs.list and the memory's reads of prior runs, under the cutoff and the isolation."""
    cut = cutoff(ctx.agent)
    if cut is not None:
        at = parse_iso(cut)
        rows = [r for r in rows if parse_iso(r["created_at"]) <= at]
    exp = _experiment(ctx)
    hidden = exp.hidden() if exp is not None else frozenset()
    if not hidden:
        return rows
    crossed = {r["run_id"]: r for r in rows if r["run_id"] in hidden or r.get("parent_run_id") in hidden}
    if crossed and _asked_by_model(ctx):
        exp._side_channel(ctx, "runs", {r.get("parent_run_id") or r["run_id"] for r in crossed.values()}, list(crossed))
    return [r for r in rows if r["run_id"] not in crossed]


def visible_table_rows(ctx, name: str, rows: list[dict]) -> list[dict]:
    """tables.read under the cutoff: rows of a table that declares ``as_of_field`` (pack.yaml) observed after it
    are not there; a table without one cannot be cut and is reported (or refused, eval.backtest.unfiltered)."""
    cut = cutoff(ctx.agent)
    if cut is None:
        return rows
    spec = (ctx.pack.config.get("tables") or {}).get(name) or {}
    field = spec.get("as_of_field")
    if field is None:
        if ctx.engine.config.experiments["backtest"]["unfiltered"] == "refuse":
            raise ToolError(f"table {name!r} declares no as_of_field; a backtest at {cut} cannot read it")
        exp = _experiment(ctx)
        if exp is not None:
            with exp._lock:
                exp.unfiltered_tables.add(name)
        return rows
    at = parse_iso(cut)
    out = []
    for r in rows:
        try:
            if r.get(field) is not None and parse_iso(str(r[field])) <= at:
                out.append(r)
        except ValueError:
            continue
    return out


def future_citations(output, gctx) -> list[str]:
    """The ``no_future_citation`` guardrail: a citation to a record observed after the run's as_of."""
    from engine.citations import iter_citations
    from engine.errors import CitationError
    cut = cutoff(gctx.agent)
    if cut is None:
        return []
    at, problems = parse_iso(cut), []
    for path, cite in iter_citations(output):
        try:
            resolved = gctx.resolver.resolve(cite)
        except CitationError:
            continue                                   # citations_resolve reports it
        c, src = resolved.citation, resolved.source
        when = None
        if c.kind == "event":
            when = src.get("observed_at")
        elif c.kind == "run":
            when = src.get("created_at")
        elif c.kind == "table":
            field = (((gctx.pack.config.get("tables") or {}).get(c.locator)) or {}).get("as_of_field")
            when = src.get(field) if field else None
        if when is not None and parse_iso(str(when)) > at:
            problems.append(f"{'/'.join(path) or '<root>'}: {c.ref} was observed at {when}, after the case's as_of {cut}")
    return problems


def tool_record_cutoff(ctx) -> str | None:
    return cutoff(getattr(ctx, "agent", None))


# -- batches outside run_eval -------------------------------------------------------------------------------

def for_eval(engine, base: Experiment | None = None) -> Experiment:
    return (base or Experiment(label="eval")).bind(engine)


@contextlib.contextmanager
def isolated_batch(runner, label: str):
    """Trap and honeypot runs of one cycle: each top-level run is its own case on an isolated event channel."""
    if runner.experiment is not None or not runner.engine.config.experiments["isolate_events"]:
        yield runner.experiment
        return
    runner.experiment = Experiment(label=label, auto_case=True).bind(runner.engine)
    try:
        yield runner.experiment
    finally:
        runner.experiment = None


def backtest_summary(cases: list[dict], confidence: float, unfiltered: set[str]) -> dict | None:
    """The backtest score, apart from the rest: the counted cases that declare an ``as_of``."""
    from engine import stats
    bt = [c for c in cases if c.get("as_of") and c.get("counted")]
    if not bt:
        return None
    k = sum(1 for c in bt if c["passed"])
    return {"cases": [c["id"] for c in bt], "passed": k, "counted": len(bt), "interval": stats.rate(k, len(bt), confidence),
            "unfiltered_tables": sorted(unfiltered)}


def adoption_gate(engine, pack, agent_name: str) -> list[str]:
    """What an experiment says against adopting this version (called by engine.autoloop.refine on the candidate):
    framing probes that diverge above eval.probes.max_divergence, and an evaluated horizon shorter than the one
    the agent works at in production (soak.min_horizon_ratio)."""
    from engine import probes, soak
    out: list[str] = []
    cfg = engine.config.experiments
    if cfg["probes"]["on_adoption"]:
        rep = probes.run_probes(engine, pack, agent_name)
        out += [f"framing probe {k['kind']}: divergence {k['interval']['rate']} on {k['divergent']} above "
                f"{rep['max_divergence']}" for k in rep["kinds"] if k["blocked"]]
    if cfg["soak"]["on_adoption"]:
        why = soak.horizon_refusal(engine, pack, agent_name)
        if why:
            out.append(why)
    return out


def normalize_as_of(value) -> str | None:
    """A golden case's ``as_of`` as the engine's ISO form (ValueError when it is not a date or datetime)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"as_of must be an ISO-8601 string, got {type(value).__name__}")
    return iso(parse_iso(value))


def latest_runs(engine, pack, agent: str, n: int) -> list[dict]:
    """The agent's latest ``n`` runs that are not experiment runs, oldest first (the kill rule's window)."""
    limit = n
    while True:
        rows = engine.store.list_runs(pack=pack.name, agent=agent, limit=limit, newest_first=True)
        kept = [r for r in rows if not is_experiment_run(r)]
        if len(kept) >= n or len(rows) < limit:
            return kept[-n:] if n else []
        limit *= 2
