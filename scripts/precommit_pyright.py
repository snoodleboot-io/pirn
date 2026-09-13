#!/usr/bin/env python3
"""Pre-commit wrapper: run ``pyright`` once per package a commit touches (PIR-856).

The local ``pyright`` hook used to run bare ``pyright`` (``pass_filenames: false``)
from the repo root, which has no ``pyproject.toml`` of its own — there is no
shared root config in this monorepo, only one per package. That invocation
resolved no project and was effectively a no-op alongside the ``files: ^pirn/``
trigger pattern that also never matched this repo's ``packages/<dist>/<import_pkg>/``
layout. This wrapper takes the staged files pre-commit hands it, determines the
unique ``packages/<dist>/`` directories they live under, and runs
``pyright`` from inside each one — matching how CI and the documented local gate
invoke it (``cd packages/<pkg> && pyright``), so ``venvPath``/``venv``/``include``
resolve correctly from that package's own config.

CLI contract
------------
``precommit_pyright.py <file>...`` — a file outside any ``packages/<dist>/`` is
reported and skipped. Exit code is the worst exit code across all packages run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYRIGHT = _REPO_ROOT / ".venv" / "bin" / "pyright"


def package_root(path: Path) -> Path | None:
    """The ``packages/<dist>/`` directory *path* lives under, or ``None``."""
    parts = path.resolve().parts
    for index, part in enumerate(parts):
        if part == "packages" and index + 1 < len(parts):
            return Path(*parts[: index + 2])
    return None


def unique_package_roots(files: list[str]) -> tuple[list[Path], list[str]]:
    """Every distinct package root among *files*, plus any files outside one."""
    roots: list[Path] = []
    unmatched: list[str] = []
    seen: set[Path] = set()
    for f in files:
        root = package_root(Path(f))
        if root is None:
            unmatched.append(f)
        elif root not in seen:
            seen.add(root)
            roots.append(root)
    return roots, unmatched


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: precommit_pyright.py <file>...", file=sys.stderr)
        return 2

    roots, unmatched = unique_package_roots(argv)
    for f in unmatched:
        print(
            f"precommit_pyright.py: {f} is not under packages/<dist>/ — skipping", file=sys.stderr
        )

    pyright = str(_PYRIGHT) if _PYRIGHT.exists() else "pyright"
    exit_code = 0
    for root in sorted(roots):
        result = subprocess.run([pyright], cwd=root)
        exit_code = exit_code or result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
