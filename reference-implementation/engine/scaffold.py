"""Blueprint scaffolder.

    python -m engine.scaffold new-domain <pack> [--root DIR]

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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.scaffold")
    sub = p.add_subparsers(dest="cmd", required=True)
    nd = sub.add_parser("new-domain")
    nd.add_argument("pack")
    nd.add_argument("--root")
    args = p.parse_args(argv)
    try:
        dest = new_domain(args.pack, Path(args.root) if args.root else None)
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"scaffolded {dest}")
    print("next: fill every TODO, then `python -m engine.validate " + args.pack + "`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
