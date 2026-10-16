"""JSON Schema helpers: validation, key extraction, traceable-field discovery.

The engine treats two custom keywords as synonyms on a property schema:
``traceable: true`` (spec 2.8) and ``requires_source: true`` (spec 2.7).
A field so marked must carry a citation or be null (guardrail no_fabrication).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import jsonschema
from jsonschema import Draft202012Validator

from engine.errors import ManifestError

_TRACEABLE_KEYS = ("traceable", "requires_source")


def load_schema(path: Path) -> dict:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f"cannot load schema {path}: {e}") from e
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise ManifestError(f"invalid JSON Schema {path}: {e.message}") from e
    return schema


def validation_errors(schema: dict, instance) -> list[str]:
    """Every violation as a stable, sorted, human-readable line."""
    validator = Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(instance):
        where = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{where}: {err.message}")
    return sorted(errors)


def validate(schema: dict, instance, what: str) -> None:
    errs = validation_errors(schema, instance)
    if errs:
        raise ManifestError(f"{what} failed schema validation: " + "; ".join(errs))


def declared_keys(schema: dict) -> set[str] | None:
    """Top-level property names, or None when the schema does not bound them."""
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    return set(props.keys())


def _walk(schema: dict, pointer: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], dict]]:
    """Yield (pointer, subschema) for every property schema, descending arrays."""
    props = schema.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            if isinstance(sub, dict):
                yield pointer + (name,), sub
                yield from _walk(sub, pointer + (name,))
    items = schema.get("items")
    if isinstance(items, dict):
        yield from _walk(items, pointer + ("*",))
    for combiner in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(combiner, []) or []:
            if isinstance(sub, dict):
                yield from _walk(sub, pointer)


def traceable_pointers(schema: dict) -> list[tuple[str, ...]]:
    """Pointers (with '*' for array items) to fields marked traceable/requires_source."""
    out = []
    for pointer, sub in _walk(schema, ()):
        if any(sub.get(k) is True for k in _TRACEABLE_KEYS):
            out.append(pointer)
    return sorted(set(out))


def resolve_pointer(instance, pointer: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], object, object]]:
    """Yield (concrete_path, parent_object, value) for each match of a '*'-pointer."""
    def rec(node, remaining: tuple[str, ...], path: tuple[str, ...], parent):
        if not remaining:
            yield path, parent, node
            return
        head, rest = remaining[0], remaining[1:]
        if head == "*":
            if isinstance(node, list):
                for i, item in enumerate(node):
                    yield from rec(item, rest, path + (str(i),), node)
        elif isinstance(node, dict) and head in node:
            yield from rec(node[head], rest, path + (head,), node)
    yield from rec(instance, pointer, (), None)


def get_path(instance, dotted: str):
    """Fetch a value by dotted/indexed path like ``items.0.total``.  KeyError if absent."""
    node = instance
    for part in dotted.split(".") if dotted else []:
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            node = node[part]
        else:
            raise KeyError(dotted)
    return node
