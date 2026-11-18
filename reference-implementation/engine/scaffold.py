"""Blueprint scaffolder.

    python -m engine.scaffold new-domain <pack> [--root DIR]
    python -m engine.scaffold new-agent <pack>/<name> --from <pack>/<proven> [--root DIR]

Copies ``engine/templates/new-domain`` to ``<root>/<pack>``, substitutes
``__PACK__``, refuses to overwrite, and validates the result with
engine.validate.  The skeleton carries TODO markers where the domain must
supply nouns; it loads as-is so the first commit of a pack is green.
``packs/_reference`` is the worked example the skeleton points at.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

from engine.errors import EngineError, EvalError, ManifestError
from engine.packs import RESERVED_PACK_NAMES, packs_root
from engine.validate import validate_pack

TEMPLATE = Path(__file__).resolve().parent / "templates" / "new-domain"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".json", ".jsonl", ".txt"}


def new_domain(pack: str, root: Path | None = None) -> Path:
    if not _NAME_RE.match(pack):
        raise ManifestError(f"pack name {pack!r} must match {_NAME_RE.pattern}")
    if pack in RESERVED_PACK_NAMES:
        raise ManifestError(f"pack name {pack!r} shadows a reserved module name")
    root = (root or packs_root()).resolve()
    dest = root / pack
    if dest.exists():
        raise ManifestError(f"refusing to overwrite existing {dest}")
    if not TEMPLATE.is_dir():
        raise EngineError(f"template missing at {TEMPLATE}")
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("__pycache__"))
    for path in dest.rglob("*"):
        if path.is_file() and path.suffix in _TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            if "__PACK__" in text:
                path.write_text(text.replace("__PACK__", pack), encoding="utf-8")
    try:
        validate_pack(pack, root)
    except (EngineError, EvalError):
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest


def new_agent(ref: str, source_ref: str, root: Path | None = None) -> Path:
    """A new agent started from a proven one: its onboarding text, prompts, guardrail list, tools, access
    and golden header (never its cases), with ``derived_from`` naming the source and its manifest hash.
    The pack is validated with the new agent in it; on failure nothing is left behind."""
    from engine.manifest import load_agent
    from engine.packs import load_pack, parse_agent_ref
    pack_name, name = parse_agent_ref(ref)
    src_pack_name, src_name = parse_agent_ref(source_ref)
    if not _NAME_RE.match(name):
        raise ManifestError(f"agent name {name!r} must match {_NAME_RE.pattern}")
    root = (root or packs_root()).resolve()
    source = load_agent(load_pack(src_pack_name, root), src_name, enforce_economics=False)
    dest = root / pack_name / "agents" / name
    if dest.exists():
        raise ManifestError(f"refusing to overwrite existing {dest}")
    shutil.copytree(source.dir, dest, ignore=shutil.ignore_patterns("__pycache__", "eval", "crank", "export"))
    try:
        golden = source.dir / "eval" / "golden.jsonl"
        if golden.is_file():
            (dest / "eval").mkdir()
            header = next(ln for ln in golden.read_text(encoding="utf-8").splitlines() if ln.strip())
            (dest / "eval" / "golden.jsonl").write_text(header + "\n", encoding="utf-8", newline="\n")
        manifest_path = dest / "manifest.yaml"
        doc = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        doc.update({"name": name, "version": "0.1.0",
                    "derived_from": {"agent": f"{src_pack_name}/{src_name}", "manifest_hash": source.hash}})
        manifest_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8", newline="\n")
        validate_pack(pack_name, root)
    except (EngineError, EvalError):
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.scaffold")
    sub = p.add_subparsers(dest="cmd", required=True)
    nd = sub.add_parser("new-domain")
    nd.add_argument("pack")
    nd.add_argument("--root")
    na = sub.add_parser("new-agent")
    na.add_argument("agent_ref", help="<pack>/<name> of the new agent")
    na.add_argument("--from", dest="source", required=True, help="<pack>/<agent> of the proven agent to start from")
    na.add_argument("--root")
    args = p.parse_args(argv)
    try:
        if args.cmd == "new-agent":
            dest = new_agent(args.agent_ref, args.source, Path(args.root) if args.root else None)
            print(f"scaffolded {dest} from {args.source}")
            print("next: rewrite skills.md and workflow.md for the new job, grow its golden set, then "
                  f"`python -m engine.validate {args.agent_ref.split('/')[0]}`")
            return 0
        dest = new_domain(args.pack, Path(args.root) if args.root else None)
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"scaffolded {dest}")
    print("next: fill every TODO, then `python -m engine.validate " + args.pack + "`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
