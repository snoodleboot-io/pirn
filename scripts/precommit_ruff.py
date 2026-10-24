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
from typing import ClassVar

from gatekit.package_root_locator import PackageRootLocator


class PrecommitRuff:
    """Run ``ruff`` once per workspace package the staged files belong to."""

    _repo_root: ClassVar[Path] = Path(__file__).resolve().parents[1]
    _ruff_path: ClassVar[Path] = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "ruff"
    _modes: ClassVar[tuple[str, ...]] = ("check", "format")

    @staticmethod
    def group_by_package(files: list[str]) -> tuple[dict[Path, list[str]], list[str]]:
        """Split *files* into {package_root: [file, ...]} plus any unmatched files."""
        groups: dict[Path, list[str]] = {}
        unmatched: list[str] = []
        for name in files:
            root = PackageRootLocator.locate(Path(name))
            if root is None:
                unmatched.append(name)
            else:
                groups.setdefault(root, []).append(name)
        return groups, unmatched

    @staticmethod
    def main(argv: list[str]) -> int:
        """Run ruff for every package group in *argv*; return the worst exit code."""
        if len(argv) < 2 or argv[0] not in PrecommitRuff._modes:
            print("usage: precommit_ruff.py <check|format> <file>...", file=sys.stderr)
            return 2

        mode, files = argv[0], argv[1:]
        groups, unmatched = PrecommitRuff.group_by_package(files)

        for name in unmatched:
            print(
                f"precommit_ruff.py: {name} is not under packages/<dist>/ — skipping",
                file=sys.stderr,
            )

        ruff = str(PrecommitRuff._ruff_path) if PrecommitRuff._ruff_path.exists() else "ruff"
        exit_code = 0
        for pkg_root, pkg_files in sorted(groups.items()):
            config = pkg_root / "pyproject.toml"
            if not config.exists():
                print(
                    f"precommit_ruff.py: {config} not found — skipping {pkg_files}",
                    file=sys.stderr,
                )
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
    sys.exit(PrecommitRuff.main(sys.argv[1:]))
