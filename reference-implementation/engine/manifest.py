"""Manifest loading and validation.  Fail at load, never at run.

Invariants enforced here:
- unknown keys, unknown tools, unknown guardrails, unknown verifier -> ManifestError
- role: orchestrator  -> model must be the frontier (config/frontier.yaml)
- role: specialist    -> verifier required, pack problem.md required,
                         count <= pack max_specialists (override needs an ADR)
- fixture providers (local) only inside fixture packs
- any non-frontier model outside a fixture pack needs an eval parity matrix
- every agent carries skills.md, workflow.md (with manual_baseline_items) and access.yaml
- manifest + onboarding + prompt + schema files are hashed; the hash rides on every trace
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.access import AccessPolicy
from engine.config import CONFIG_DIR, EngineConfig, load_config, load_yaml
from engine.errors import ManifestError
from engine.hashing import sha256_tree
from engine.packs import Pack
from engine.schema import load_schema, validate

ROLES = ("orchestrator", "specialist", "worker")
AGENT_TOOL_PREFIX = "agent."


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str
    system_prompt: str
    tools: tuple[str, ...]
    max_tokens: int

    @property
    def model_string(self) -> str:
        return f"{self.provider}/{self.name}"


@dataclass(frozen=True)
class Agent:
    pack: Pack
    name: str
    dir: Path
    manifest: dict
    role: str
    version: str
    model: ModelSpec
    grounding: tuple[dict, ...]
    tools: tuple[str, ...]
    memory: dict
    loop: dict
    output_schema: dict
    guardrails: tuple[str, ...]
    verifier: str | None
    confidence_field: str | None
    max_output_bytes: int
    items_evaluated_field: str | None
    skills: str
    workflow: str
    workflow_meta: dict
    access: AccessPolicy
    hash: str

    @property
    def ref(self) -> str:
        return f"{self.pack.name}/{self.name}"

    @property
    def manual_baseline_items(self) -> int:
        return int(self.workflow_meta["manual_baseline_items"])

    def with_model(self, provider: str, name: str) -> "Agent":
        """The same agent on a different model string (eval matrix, swap tests)."""
        model = _resolve_model(self.manifest, self.dir, provider, name)
        return Agent(**{**self.__dict__, "model": model, "tools": model.tools})


def _front_matter(text: str, where: Path) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        raise ManifestError(f"{where}: unterminated front matter")
    meta = yaml.safe_load(text[4:end]) or {}
    if not isinstance(meta, dict):
        raise ManifestError(f"{where}: front matter must be a mapping")
    return meta, text[end + 4:]


def _resolve_model(manifest: dict, agent_dir: Path, provider: str, name: str) -> ModelSpec:
    m = manifest["model"]
    variants = m.get("variants") or {}
    variant = variants.get(name) or {}
    prompt_file = variant.get("system_prompt_file") or m["system_prompt_file"]
    prompt_path = (agent_dir / prompt_file).resolve()
    if not prompt_path.is_file():
        raise ManifestError(f"system prompt file not found: {prompt_path}")
    system_prompt = prompt_path.read_text(encoding="utf-8")
    if not system_prompt.strip():
        raise ManifestError(f"system prompt file is empty: {prompt_path}")
    tools = tuple(variant.get("tool_overrides") or manifest["tools"])
    return ModelSpec(provider=provider, name=name, system_prompt=system_prompt,
                     tools=tools, max_tokens=int(m.get("max_tokens", 16000)))


def _latest_matrix(agent_dir: Path) -> dict | None:
    files = sorted((agent_dir / "eval").glob("matrix-*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _check_model_economics(agent_dir: Path, agent_name: str, role: str, model: ModelSpec,
                           pack: Pack, config: EngineConfig) -> None:
    frontier = config.frontier
    is_frontier = (model.provider, model.name) == (frontier.provider, frontier.name)
    is_fixture_model = model.provider in config.fixture_providers
    if is_fixture_model and not pack.fixture:
        raise ManifestError(
            f"{agent_name}: provider {model.provider!r} is a fixture provider; "
            f"only packs with fixture: true may use it")
    # A fixture responder is not a model; the frontier pin governs real models.
    if role == "orchestrator" and not is_frontier and not (pack.fixture and is_fixture_model):
        raise ManifestError(
            f"{agent_name}: role orchestrator must run the frontier model "
            f"{frontier.model_string}; model swap is disallowed for orchestrators")
    if is_frontier or pack.fixture:
        return
    matrix = _latest_matrix(agent_dir)
    if matrix is None:
        raise ManifestError(
            f"{agent_name}: model {model.model_string} is not the frontier and no "
            f"eval/matrix-*.json shows parity; run engine.eval --models first")
    rows = {r["model"]: r for r in matrix.get("models", [])}
    row = rows.get(model.model_string)
    if row is None or not row.get("parity"):
        raise ManifestError(
            f"{agent_name}: latest eval matrix does not show {model.model_string} "
            f"at parity with the frontier; downgrade refused")


def load_agent(pack: Pack, name: str, *, config: EngineConfig | None = None,
               model_override: tuple[str, str] | None = None,
               enforce_economics: bool = True) -> Agent:
    config = config or load_config()
    agent_dir = pack.agent_dir(name)
    manifest_path = agent_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise ManifestError(f"no agent {name!r} in pack {pack.name!r} ({manifest_path})")
    manifest = load_yaml(manifest_path)
    validate(load_schema(CONFIG_DIR / "manifest.schema.json"), manifest, str(manifest_path))
    if manifest["name"] != name:
        raise ManifestError(f"{manifest_path}: name {manifest['name']!r} does not match directory {name!r}")
    role = manifest["role"]

    # tools / guardrails / verifier must exist
    for t in manifest["tools"]:
        if not pack.tools.has(t):
            raise ManifestError(f"{manifest_path}: unknown tool {t!r}")
    for variant_name, variant in (manifest["model"].get("variants") or {}).items():
        for t in variant.get("tool_overrides") or []:
            if not pack.tools.has(t):
                raise ManifestError(f"{manifest_path}: variant {variant_name!r} names unknown tool {t!r}")
    for g in manifest["safeguards"]["guardrails"]:
        if not pack.guardrails.has(g):
            raise ManifestError(f"{manifest_path}: unknown guardrail {g!r}")
    verifier = manifest["safeguards"]["verifier"]
    if verifier is not None and not pack.verifiers.has(verifier):
        raise ManifestError(f"{manifest_path}: unknown verifier {verifier!r}")
    if role == "specialist":
        if verifier is None:
            raise ManifestError(f"{manifest_path}: role specialist requires a verifier")
        if not (pack.problem_text or "").strip():
            raise ManifestError(f"pack {pack.name!r}: a specialist requires problem.md")
    if role == "orchestrator" and verifier is not None:
        raise ManifestError(f"{manifest_path}: an orchestrator does no proprietary math and takes no verifier")

    # agent tools: orchestrators only, one level deep
    agent_tools = [t for t in manifest["tools"] if t.startswith(AGENT_TOOL_PREFIX)]
    if agent_tools and role != "orchestrator":
        raise ManifestError(f"{manifest_path}: only an orchestrator may call other agents ({agent_tools})")
    for t in agent_tools:
        child = t.split(".")[-1]
        if child == name:
            raise ManifestError(f"{manifest_path}: an agent may not call itself")
        child_manifest = pack.agent_dir(child) / "manifest.yaml"
        if child_manifest.is_file() and load_yaml(child_manifest).get("role") == "orchestrator":
            raise ManifestError(f"{manifest_path}: orchestrators may not call orchestrators ({t})")

    # grounding refs
    for src in manifest["grounding"]["sources"]:
        if src["kind"] == "table" and src["ref"] not in pack.tables:
            raise ManifestError(f"{manifest_path}: grounding table {src['ref']!r} is not a pack table")
        if src["kind"] == "agent_output" and src["ref"] not in pack.agent_names:
            raise ManifestError(f"{manifest_path}: grounding agent_output {src['ref']!r} is not a pack agent")
        if src["kind"] == "file" and not (agent_dir / src["ref"]).is_file() and not (pack.root / src["ref"]).is_file():
            raise ManifestError(f"{manifest_path}: grounding file {src['ref']!r} not found")

    compaction = manifest["memory"]["compaction"]
    if compaction is not None and compaction["summary_agent"] not in pack.agent_names:
        raise ManifestError(f"{manifest_path}: compaction summary_agent {compaction['summary_agent']!r} is not a pack agent")

    # onboarding pack
    skills_path, workflow_path, access_path = (agent_dir / "skills.md", agent_dir / "workflow.md",
                                               agent_dir / "access.yaml")
    for p in (skills_path, workflow_path, access_path):
        if not p.is_file():
            raise ManifestError(f"{agent_dir}: missing onboarding file {p.name}")
    skills = skills_path.read_text(encoding="utf-8")
    workflow_meta, workflow = _front_matter(workflow_path.read_text(encoding="utf-8"), workflow_path)
    if not skills.strip():
        raise ManifestError(f"{skills_path}: skills.md is empty")
    baseline = workflow_meta.get("manual_baseline_items")
    if isinstance(baseline, bool) or not isinstance(baseline, int) or baseline < 1:
        raise ManifestError(f"{workflow_path}: front matter must declare manual_baseline_items (positive int)")

    access_doc = load_yaml(access_path)
    validate(load_schema(CONFIG_DIR / "access.schema.json"), access_doc, str(access_path))
    access = AccessPolicy.from_doc(
        access_doc, agent=name, pack_root=pack.root,
        tools=frozenset(manifest["tools"]) | frozenset(
            t for v in (manifest["model"].get("variants") or {}).values() for t in (v.get("tool_overrides") or [])),
        agents=frozenset(t.split(".")[-1] for t in agent_tools))

    # output schema
    schema_path = (agent_dir / manifest["safeguards"]["output_schema"]).resolve()
    output_schema = load_schema(schema_path)

    # model
    provider, model_name = model_override or (manifest["model"]["provider"], manifest["model"]["name"])
    model = _resolve_model(manifest, agent_dir, provider, model_name)
    if enforce_economics:
        _check_model_economics(agent_dir, name, role, model, pack, config)

    loop = {
        "max_iterations": int(manifest["loop"].get("max_iterations", config.default_max_iterations)),
        "search_width": int(manifest["loop"].get("search_width", config.default_search_width)),
        "stop_when": manifest["loop"].get(
            "stop_when", "verifier_certified" if role == "specialist" else "all_guardrails_pass"),
    }
    if loop["stop_when"] == "verifier_certified" and verifier is None:
        raise ManifestError(f"{manifest_path}: stop_when verifier_certified needs a verifier")

    return Agent(
        pack=pack, name=name, dir=agent_dir, manifest=manifest, role=role,
        version=manifest["version"], model=model,
        grounding=tuple(manifest["grounding"]["sources"]), tools=model.tools,
        memory=manifest["memory"], loop=loop, output_schema=output_schema,
        guardrails=tuple(manifest["safeguards"]["guardrails"]), verifier=verifier,
        confidence_field=manifest["safeguards"].get("confidence_field"),
        max_output_bytes=int(manifest["safeguards"].get("max_output_bytes", 65536)),
        items_evaluated_field=(manifest.get("metrics") or {}).get("items_evaluated_field"),
        skills=skills, workflow=workflow, workflow_meta=workflow_meta, access=access,
        hash=sha256_tree(agent_dir, exclude_dirs=("eval", "crank")),
    )


def load_all_agents(pack: Pack, *, config: EngineConfig | None = None) -> dict[str, Agent]:
    """Load every agent in the pack and enforce pack-level invariants."""
    config = config or load_config()
    agents = {name: load_agent(pack, name, config=config) for name in pack.agent_names}
    specialists = [a for a in agents.values() if a.role == "specialist"]
    limit = pack.max_specialists
    if limit > 1 and not pack.has_adr():
        raise ManifestError(
            f"pack {pack.name!r}: max_specialists={limit} > 1 requires an ADR under {pack.root / 'adr'}")
    if len(specialists) > limit:
        raise ManifestError(
            f"pack {pack.name!r}: {len(specialists)} specialists but max_specialists={limit} "
            f"(one bespoke super sub-agent per pack; override needs pack.yaml + adr/)")
    return agents
