"""Domain packs: locate, load, validate.

A pack supplies nouns and domain code behind fixed interfaces; the engine
never imports a pack by name.  Pack Python modules are imported from the packs
root (``HARNESS_PACKS`` or ``<repo>/packs``) and scanned for ``@tool``,
``@guardrail`` and ``@verifier`` declarations.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from engine.config import CONFIG_DIR, ENGINE_ROOT, load_yaml
from engine.errors import ManifestError
from engine.guardrails import GuardrailRegistry, builtin_registry
from engine.schema import load_schema, validate
from engine.tools import ToolRegistry
from engine.verify import VerifierRegistry

RESERVED_PACK_NAMES = frozenset(sys.stdlib_module_names) | {"engine", "ri_core", "tests", "packs"}


def packs_root() -> Path:
    env = os.environ.get("HARNESS_PACKS")
    return Path(env).resolve() if env else ENGINE_ROOT / "packs"


@dataclass(frozen=True)
class TableSpec:
    name: str
    path: Path
    id_field: str


@dataclass
class Pack:
    name: str
    root: Path
    config: dict
    fixture: bool
    entity_types: frozenset[str]
    max_specialists: int
    tables: dict[str, TableSpec]
    event_types: dict[str, dict]
    adapters_config: dict | None
    problem_text: str | None
    local_models: dict[str, object]
    tools: ToolRegistry
    guardrails: GuardrailRegistry
    verifiers: VerifierRegistry
    agent_names: tuple[str, ...]
    _table_cache: dict = field(default_factory=dict, repr=False)

    # -- tables ----------------------------------------------------------------

    def table_rows(self, name: str) -> list[dict]:
        spec = self.tables.get(name)
        if spec is None:
            raise ManifestError(f"pack {self.name!r} has no table {name!r}")
        if name not in self._table_cache:
            self._table_cache[name] = _read_table(spec)
        return [dict(r) for r in self._table_cache[name]]

    def table_row(self, name: str, row_id: str) -> dict | None:
        spec = self.tables.get(name)
        if spec is None:
            return None
        for row in self.table_rows(name):
            if str(row.get(spec.id_field)) == str(row_id):
                return row
        return None

    # -- layout -------------------------------------------------------------------

    def agent_dir(self, agent: str) -> Path:
        return self.root / "agents" / agent

    def has_adr(self) -> bool:
        adr = self.root / "adr"
        return adr.is_dir() and any(p.suffix == ".md" for p in adr.iterdir())


def _read_table(spec: TableSpec) -> list[dict]:
    path = spec.path
    if not path.is_file():
        raise ManifestError(f"table {spec.name!r}: file not found {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif path.suffix == ".json":
        rows = json.loads(text)
    elif path.suffix == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    else:
        raise ManifestError(f"table {spec.name!r}: unsupported file type {path.suffix}")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ManifestError(f"table {spec.name!r}: rows must be objects")
    seen = set()
    for r in rows:
        if spec.id_field not in r:
            raise ManifestError(f"table {spec.name!r}: row without id field {spec.id_field!r}")
        key = str(r[spec.id_field])
        if key in seen:
            raise ManifestError(f"table {spec.name!r}: duplicate id {key!r}")
        seen.add(key)
    return rows


def import_pack_module(pack_name: str, dotted: str, root: Path):
    """Import ``<pack>.<dotted>`` with the packs root on sys.path."""
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        return importlib.import_module(f"{pack_name}.{dotted}")
    except ImportError as e:
        raise ManifestError(f"pack {pack_name!r}: cannot import module {dotted!r}: {e}") from e


def _load_local_models(pack_name: str, declared: dict, root: Path) -> dict:
    out = {}
    for model_name, target in sorted(declared.items()):
        module_path, attr = target.split(":", 1)
        mod = import_pack_module(pack_name, module_path, root)
        fn = getattr(mod, attr, None)
        if not callable(fn):
            raise ManifestError(f"pack {pack_name!r}: local model {model_name!r} -> {target!r} is not callable")
        out[model_name] = fn
    return out


def load_pack(name: str, root: Path | None = None) -> Pack:
    root = (root or packs_root()).resolve()
    pack_dir = root / name
    pack_yaml = pack_dir / "pack.yaml"
    if not pack_yaml.is_file():
        raise ManifestError(f"no pack {name!r} at {pack_dir}")
    config = load_yaml(pack_yaml)
    validate(load_schema(CONFIG_DIR / "pack.schema.json"), config, f"{pack_yaml}")
    if config["name"] != name:
        raise ManifestError(f"pack.yaml name {config['name']!r} does not match directory {name!r}")
    if name.lstrip("_") in RESERVED_PACK_NAMES or name in RESERVED_PACK_NAMES:
        raise ManifestError(f"pack name {name!r} shadows a reserved module name")
    if not (pack_dir / "__init__.py").is_file():
        raise ManifestError(f"pack {name!r} must be an importable package (missing __init__.py)")

    tables = {}
    for tname, tspec in sorted((config.get("tables") or {}).items()):
        tables[tname] = TableSpec(name=tname, path=(pack_dir / tspec["ref"]).resolve(),
                                  id_field=tspec.get("id_field", "id"))

    events_path = pack_dir / "events.yaml"
    event_types: dict[str, dict] = {}
    if events_path.is_file():
        doc = load_yaml(events_path)
        validate(load_schema(CONFIG_DIR / "events.schema.json"), doc, f"{events_path}")
        for etype, spec in doc["events"].items():
            if not etype.startswith(f"{name}."):
                raise ManifestError(f"{events_path}: event type {etype!r} must be namespaced {name}.<verb>")
            schema = spec["payload"]
            try:
                from jsonschema import Draft202012Validator
                Draft202012Validator.check_schema(schema)
            except Exception as e:  # noqa: BLE001
                raise ManifestError(f"{events_path}: payload schema for {etype!r} invalid: {e}") from e
            event_types[etype] = schema

    adapters_path = pack_dir / "adapters.yaml"
    adapters_config = None
    if adapters_path.is_file():
        adapters_config = load_yaml(adapters_path)
        validate(load_schema(CONFIG_DIR / "adapters.schema.json"), adapters_config, f"{adapters_path}")
        for slot, sdoc in adapters_config["slots"].items():
            if sdoc["binding"] not in adapters_config["bindings"]:
                raise ManifestError(f"{adapters_path}: slot {slot!r} binds unknown adapter {sdoc['binding']!r}")

    problem_path = pack_dir / "problem.md"
    problem_text = problem_path.read_text(encoding="utf-8") if problem_path.is_file() else None

    fixture = bool(config["fixture"])
    local_models = {}
    if config.get("local_models"):
        if not fixture:
            raise ManifestError(f"pack {name!r} declares local_models but is not a fixture pack")
        local_models = _load_local_models(name, config["local_models"], root)

    tools = ToolRegistry()
    from engine.builtin_tools import register_builtin_tools
    register_builtin_tools(tools)
    guardrails = builtin_registry()
    verifiers = VerifierRegistry()
    modules = config.get("modules") or {}
    for dotted in modules.get("tools") or []:
        tools.register_module(import_pack_module(name, dotted, root))
    for dotted in modules.get("guardrails") or []:
        guardrails.register_module(import_pack_module(name, dotted, root))
    for dotted in modules.get("verifiers") or []:
        verifiers.register_module(import_pack_module(name, dotted, root))

    agents_dir = pack_dir / "agents"
    agent_names = tuple(sorted(p.name for p in agents_dir.iterdir()
                               if p.is_dir() and (p / "manifest.yaml").is_file())) if agents_dir.is_dir() else ()
    from engine.builtin_tools import register_agent_tools
    register_agent_tools(tools, name, agent_names)

    return Pack(
        name=name, root=pack_dir, config=config, fixture=fixture,
        entity_types=frozenset(config["entity_types"]),
        max_specialists=int(config["max_specialists"]),
        tables=tables, event_types=event_types, adapters_config=adapters_config,
        problem_text=problem_text, local_models=local_models,
        tools=tools, guardrails=guardrails, verifiers=verifiers, agent_names=agent_names,
    )


def parse_agent_ref(ref: str) -> tuple[str, str]:
    """``<pack>/<agent>`` -> (pack, agent)."""
    if "/" not in ref:
        raise ManifestError(f"agent ref {ref!r} must be <pack>/<agent>")
    pack, agent = ref.split("/", 1)
    if not pack or not agent or "/" in agent:
        raise ManifestError(f"agent ref {ref!r} must be <pack>/<agent>")
    return pack, agent
