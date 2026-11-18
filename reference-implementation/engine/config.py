"""Engine configuration: YAML files under config/, loaded once, hashed for traces."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from engine.errors import EngineError

ENGINE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ENGINE_ROOT / "config"


def load_yaml(path: Path) -> dict:
    """Load a YAML mapping.  Non-mapping documents are an error, not a surprise."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise EngineError(f"cannot read {path}: {e}") from e
    data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise EngineError(f"{path} must be a YAML mapping, got {type(data).__name__}")
    return data


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Frontier:
    provider: str
    name: str

    @property
    def model_string(self) -> str:
        return f"{self.provider}/{self.name}"


@dataclass(frozen=True)
class EngineConfig:
    prices: dict
    frontier: Frontier
    fixture_providers: frozenset[str]
    judgement: dict
    judgement_hash: str
    engine: dict
    tools: dict

    @property
    def max_tool_calls(self) -> int:
        return int(self.engine["loop"]["max_tool_calls_per_candidate"])

    @property
    def default_max_iterations(self) -> int:
        return int(self.engine["loop"]["default_max_iterations"])

    @property
    def default_search_width(self) -> int:
        return int(self.engine["loop"]["default_search_width"])

    @property
    def export_min_verdicts(self) -> int:
        return int(self.engine["export"]["min_verdicted_runs"])

    @property
    def export_accepts_agent_verdicts(self) -> bool:
        return bool(self.engine["export"].get("accept_agent_verdicts", False))

    @property
    def autoloop_max_runs(self) -> int:
        return int((self.engine.get("autoloop") or {}).get("max_runs_per_cycle", 20))

    @property
    def autoloop_refine_rungs(self) -> tuple[int, ...]:
        return tuple(int(r) for r in (self.engine.get("autoloop") or {}).get("refine_rungs", [1, 2]))

    @property
    def sweep(self) -> dict:
        s = dict(self.engine.get("sweep") or {})
        return {"workers": int(s.get("workers", 8)), "budget_usd": s.get("budget_usd"),
                "kill_check_every": int(s.get("kill_check_every", 20))}

    @property
    def autoloop(self) -> dict:
        """The loop's law with its defaults (config/engine.yaml autoloop)."""
        a = dict(self.engine.get("autoloop") or {})
        kill = {"window_runs": 20, "min_runs": 5, "min_pass_rate": 0.5, **(a.get("kill") or {})}
        judge = {"min_compared": 5, "max_disagreement": 0.25, "honeypots_per_cycle": 2, "min_planted": 4, "max_missed": 0.25,
                 **(a.get("judge") or {})}
        return {"holdout": bool(a.get("holdout", True)), "kill": kill, "judge": judge,
                "grow_golden": bool(a.get("grow_golden", True)),
                "refine_min_cluster_runs": int(a.get("refine_min_cluster_runs", 1))}

    @property
    def citation_kinds(self) -> frozenset[str]:
        return frozenset(self.engine["citations"]["kinds"])

    def price_per_token(self, provider: str, model: str) -> tuple[Decimal, Decimal]:
        """(input, output) USD per token.  Unknown model -> EngineError."""
        table = self.prices.get(provider)
        if table is None:
            raise EngineError(f"no price table for provider {provider!r}")
        row = table.get(model) or table.get("default")
        if row is None:
            raise EngineError(f"no price for {provider}/{model} in config/prices.yaml")
        per_million = Decimal(1_000_000)
        return (Decimal(str(row["input"])) / per_million,
                Decimal(str(row["output"])) / per_million)

    def cache_read_price_per_token(self, provider: str, model: str) -> Decimal:
        """USD per prompt token the provider served from its cache (`cache_read` in prices.yaml).
        A model without the figure is billed at its input rate: never cheaper than published."""
        table = self.prices.get(provider)
        if table is None:
            raise EngineError(f"no price table for provider {provider!r}")
        row = table.get(model) or table.get("default")
        if row is None:
            raise EngineError(f"no price for {provider}/{model} in config/prices.yaml")
        return Decimal(str(row.get("cache_read", row["input"]))) / Decimal(1_000_000)

    # -- JH-C11 wpA: eval rigor (every key defaulted so older engine.yaml files still load) -------------

    @property
    def stats(self) -> dict:
        s = dict(self.engine.get("stats") or {})
        return {"confidence": float(s.get("confidence", 0.9)), "gate_on_bounds": bool(s.get("gate_on_bounds", False))}

    @property
    def eval_rigor(self) -> dict:
        e = dict(self.engine.get("eval") or {})
        suspect = {"min_evals": 3, **(e.get("suspect") or {})}
        return {"samples": int(e.get("samples", 3)), "fixture_samples": int(e.get("fixture_samples", 1)),
                "min_case_rate": float(e.get("min_case_rate", 0.6)),
                "strata": tuple(e.get("strata", ["area", "realism", "dimension"])),
                "min_stratum_cases": int(e.get("min_stratum_cases", 3)),
                "saturation_k": int(e.get("saturation_k", 3)), "max_saturated_share": float(e.get("max_saturated_share", 0.8)),
                "hard_tier": int(e.get("hard_tier", 3)), "min_hard_share": float(e.get("min_hard_share", 0.2)),
                "require_controls": bool(e.get("require_controls", True)),
                "require_tool_coverage": bool(e.get("require_tool_coverage", True)),
                "suspect": {"min_evals": int(suspect["min_evals"])}}

    @property
    def curriculum(self) -> dict:
        c = dict(self.engine.get("curriculum") or {})
        return {"promote_at": float(c.get("promote_at", 0.9)), "min_runs": int(c.get("min_runs", 5)),
                "window_runs": int(c.get("window_runs", 20)), "plan_frontier_window": int(c.get("plan_frontier_window", 1)),
                "max_teacher_gap": float(c.get("max_teacher_gap", 0.5))}

    @property
    def sweep_broken(self) -> dict:
        b = dict((self.engine.get("sweep") or {}).get("broken") or {})
        return {"window": int(b.get("window", 20)), "max_cluster_share": float(b.get("max_cluster_share", 0.6))}


@lru_cache(maxsize=4)
def load_config(config_dir: Path = CONFIG_DIR) -> EngineConfig:
    prices = load_yaml(config_dir / "prices.yaml")
    frontier_doc = load_yaml(config_dir / "frontier.yaml")
    judgement_path = config_dir / "judgement.yaml"
    judgement = load_yaml(judgement_path)
    engine = load_yaml(config_dir / "engine.yaml")
    tools = load_yaml(config_dir / "tools.yaml")
    f = frontier_doc["frontier"]
    return EngineConfig(
        prices=prices,
        frontier=Frontier(provider=str(f["provider"]), name=str(f["name"])),
        fixture_providers=frozenset(frontier_doc.get("fixture_providers", [])),
        judgement=judgement,
        judgement_hash=sha256_file(judgement_path),
        engine=engine,
        tools=tools,
    )
