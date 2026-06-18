"""CLI for the ``pirn.domains.<x>`` -> ``pirn_<x>`` import codemod (SCD-17).

Exposed as the ``pirn-migrate-imports`` console script. Accepts one or more
files or directories. Directories are walked recursively for ``.py`` files.
By default rewrites in place; ``--check`` is a dry run that reports what
would change and exits non-zero if any file needs rewriting. Output is a
deterministic, sorted summary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pirn._migrate.import_rewriter import ImportRewriter


def _collect_py_files(paths: list[str]) -> list[Path]:
    """Return the sorted, de-duplicated set of ``.py`` files under ``paths``."""
    found: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.update(p for p in path.rglob("*.py") if p.is_file())
        elif path.suffix == ".py" and path.is_file():
            found.add(path)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``pirn-migrate-imports`` console script."""
    parser = argparse.ArgumentParser(
        prog="pirn-migrate-imports",
        description=(
            "Rewrite legacy `pirn.domains.<x>` imports to the standalone "
            "`pirn_<x>` packages (x in signal, oilgas, data, ml, agents, health)."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to rewrite (directories are walked recursively).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run: report files that need rewriting and exit non-zero, writing nothing.",
    )
    args = parser.parse_args(argv)

    rewriter = ImportRewriter()
    files = _collect_py_files(args.paths)
    changed: list[Path] = []

    for path in files:
        if args.check:
            if rewriter.file_needs_rewrite(path):
                changed.append(path)
        elif rewriter.rewrite_file(path):
            changed.append(path)

    verb = "would rewrite" if args.check else "rewrote"
    for path in changed:
        print(f"{verb}: {path}")

    if not changed:
        print(f"no changes — scanned {len(files)} file(s)")
        return 0

    print(f"{verb} {len(changed)} of {len(files)} file(s)")
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
