#!/usr/bin/env python3
"""Pre-commit wrapper: run ``ruff`` with each staged file's OWN package config.

Why this exists (PIR-856)
--------------------------
This is a monorepo of seven independent packages, each with its own
``pyproject.toml`` ``[tool.ruff]`` section — not a shared root config. The
``astral-sh/ruff-pre-commit`` hooks invoke a single ``ruff check``/``ruff format``
per run over whatever files pre-commit hands them, with no per-file ``--config``.
Running ruff from the repo root without each package's own config once
reformatted 560 files across every package, including pirn-core (see the
layout note in ``.pre-commit-config.yaml``). This wrapper groups the staged
files by the ``packages/<dist>/`` they live under and invokes one ``ruff``
subprocess per group with that package's own ``pyproject.toml`` — so a commit
touching only ``pirn-signal`` can never reformat ``pirn-core``.

CLI contract
------------
``precommit_ruff.py <check|format> <file>...``

* ``check``  — runs ``ruff check --fix --config <pkg>/pyproject.toml <files>``
* ``format`` — runs ``ruff format --config <pkg>/pyproject.toml <files>``

A file that is not under any ``packages/<dist>/`` directory is reported and
skipped rather than silently ignored — a hook that quietly does nothing for a
file it was supposed to check is worse than one that fails loudly.

Exit code is the worst (first non-zero) exit code across all package groups,
matching how pre-commit interprets a failing hook.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUFF = _REPO_ROOT / ".venv" / "bin" / "ruff"


def package_root(path: Path) -> Path | None:
    """The ``packages/<dist>/`` directory *path* lives under, or ``None``."""
    parts = path.resolve().parts
    for index, part in enumerate(parts):
        if part == "packages" and index + 1 < len(parts):
            return Path(*parts[: index + 2])
    return None


def group_by_package(files: list[str]) -> tuple[dict[Path, list[str]], list[str]]:
    """Split *files* into {package_root: [file, ...]} plus any unmatched files."""
    groups: dict[Path, list[str]] = {}
    unmatched: list[str] = []
    for f in files:
        root = package_root(Path(f))
        if root is None:
            unmatched.append(f)
        else:
            groups.setdefault(root, []).append(f)
    return groups, unmatched


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("check", "format"):
        print("usage: precommit_ruff.py <check|format> <file>...", file=sys.stderr)
        return 2

    mode, files = argv[0], argv[1:]
    groups, unmatched = group_by_package(files)

    for f in unmatched:
        print(f"precommit_ruff.py: {f} is not under packages/<dist>/ — skipping", file=sys.stderr)

    ruff = str(_RUFF) if _RUFF.exists() else "ruff"
    exit_code = 0
    for pkg_root, pkg_files in sorted(groups.items()):
        config = pkg_root / "pyproject.toml"
        if not config.exists():
            print(f"precommit_ruff.py: {config} not found — skipping {pkg_files}", file=sys.stderr)
            exit_code = 2
            continue
        cmd = [ruff, mode, "--config", str(config)]
        if mode == "check":
            cmd.append("--fix")
        cmd.extend(pkg_files)
        result = subprocess.run(cmd)
        exit_code = exit_code or result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
