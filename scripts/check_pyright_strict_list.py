#!/usr/bin/env python3
"""Ratchet gate for the per-subpackage pyright ``strict`` list (PIR-869).

Policy (``.claude/conventions/languages/python.md``, "Type Checking
Enforcement"): pyright strict mode is adopted **per top-level subpackage**,
not per package. Each package's ``[tool.pyright]`` carries a ``strict = [...]``
list of subpackage paths; a subpackage joins the list the moment its strict
error count hits 0, new subpackages start strict, and a listed subpackage may
never regress. The remaining counts are the burn-down table in
``docs/architecture/ci-pipelines.md``.

This script makes that policy mechanical. For every package directory given
it:

1. reads ``include`` and ``strict`` from ``pyproject.toml`` ``[tool.pyright]``;
2. runs pyright once with **every** file of the import package in strict mode
   (a throwaway ``.pyright-strict-list.json`` that ``extends`` the
   ``pyproject.toml``, so ``venvPath``/``venv``/``include`` still apply and the
   real ``strict`` list is overridden for the measurement only);
3. counts strict errors per top-level subpackage — ``<pkg>/<sub>`` for every
   directory with an ``__init__.py`` directly under the import root, and
   ``<pkg>/*.py`` for the modules that sit directly in the root;
4. fails when a listed subpackage has errors (regression), when a subpackage
   with 0 errors is missing from the list (must join), or when a listed path
   is not a subpackage at all.

``--table`` prints the per-subpackage counts as a Markdown table for the
burn-down doc. ``--extra-path`` is forwarded to pyright's ``extraPaths`` so a
worktree that changes ``pirn-core`` can check a sibling package against the
worktree's core rather than the installed one.

Exit codes: ``0`` policy holds, ``1`` policy violated, ``2`` usage error or
pyright could not be run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

_TEMP_CONFIG_NAME = ".pyright-strict-list.json"


class _Subpackages:
    """Naming of strict-list entries and mapping of files onto them."""

    @staticmethod
    def root_glob(import_pkg: str) -> str:
        """The strict-list entry that covers modules directly under the import root."""
        return f"{import_pkg}/*.py"

    @staticmethod
    def enumerate(package_dir: Path, import_pkg: str) -> list[str]:
        """Every subpackage entry a package can list, sorted, root glob last."""
        root = package_dir / import_pkg
        entries = sorted(
            f"{import_pkg}/{child.name}"
            for child in root.iterdir()
            if child.is_dir() and (child / "__init__.py").exists()
        )
        entries.append(_Subpackages.root_glob(import_pkg))
        return entries

    @staticmethod
    def key_for(file_path: str, package_dir: Path, import_pkg: str) -> str | None:
        """Strict-list entry for a diagnostic's file, or ``None`` if outside the import root."""
        try:
            relative = Path(file_path).resolve().relative_to((package_dir / import_pkg).resolve())
        except ValueError:
            return None
        if len(relative.parts) == 1:
            return _Subpackages.root_glob(import_pkg)
        return f"{import_pkg}/{relative.parts[0]}"


class _PyrightConfig:
    """Read the bits of ``[tool.pyright]`` this gate cares about."""

    @staticmethod
    def load(package_dir: Path) -> tuple[str, list[str]]:
        """Return ``(import_pkg, strict_list)`` from the package's ``pyproject.toml``."""
        pyproject = package_dir / "pyproject.toml"
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        section = data.get("tool", {}).get("pyright", {})
        include = section.get("include")
        if not isinstance(include, list) or not include or not isinstance(include[0], str):
            raise ValueError(f"{pyproject}: [tool.pyright].include must name the import package")
        strict = section.get("strict", [])
        if not isinstance(strict, list) or not all(isinstance(s, str) for s in strict):
            raise ValueError(f"{pyproject}: [tool.pyright].strict must be a list of paths")
        return include[0], list(strict)


class _StrictRun:
    """Run pyright with the whole import package in strict mode and count per subpackage."""

    @staticmethod
    def run(
        package_dir: Path,
        import_pkg: str,
        *,
        pyright: str,
        extra_paths: list[str],
    ) -> dict[str, int]:
        config = package_dir / _TEMP_CONFIG_NAME
        payload: dict[str, object] = {"extends": "./pyproject.toml", "strict": [import_pkg]}
        if extra_paths:
            payload["extraPaths"] = extra_paths
        config.write_text(json.dumps(payload), encoding="utf-8")
        try:
            proc = subprocess.run(
                [pyright, "-p", _TEMP_CONFIG_NAME, "--outputjson"],
                cwd=package_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            config.unlink(missing_ok=True)
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"pyright produced no JSON report for {package_dir} "
                f"(exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
            ) from exc
        return _StrictRun.count(report.get("generalDiagnostics", []), package_dir, import_pkg)

    @staticmethod
    def count(
        diagnostics: list[dict[str, object]], package_dir: Path, import_pkg: str
    ) -> dict[str, int]:
        """Errors per subpackage entry; every enumerable entry is present, zero or not."""
        counts = dict.fromkeys(_Subpackages.enumerate(package_dir, import_pkg), 0)
        for diagnostic in diagnostics:
            if diagnostic.get("severity") != "error":
                continue
            file_path = diagnostic.get("file")
            if not isinstance(file_path, str):
                continue
            key = _Subpackages.key_for(file_path, package_dir, import_pkg)
            if key is None:
                continue
            counts[key] = counts.get(key, 0) + 1
        return counts


class _Policy:
    """The three rules, evaluated over measured counts and the declared list."""

    @staticmethod
    def problems(strict_list: list[str], counts: dict[str, int]) -> list[str]:
        problems: list[str] = []
        for entry in strict_list:
            if entry not in counts:
                problems.append(f"strict list names {entry!r}, which is not a subpackage")
            elif counts[entry] > 0:
                problems.append(
                    f"{entry} is strict-listed but has {counts[entry]} strict error(s) — regression"
                )
        for entry, count in counts.items():
            if count == 0 and entry not in strict_list:
                problems.append(
                    f"{entry} has 0 strict errors but is not in the strict list — add it"
                )
        return problems

    @staticmethod
    def table_rows(package: str, strict_list: list[str], counts: dict[str, int]) -> list[str]:
        rows: list[str] = []
        for entry, count in sorted(counts.items(), key=lambda kv: (kv[1], kv[0])):
            flag = "yes" if entry in strict_list else ""
            rows.append(f"| {package} | `{entry}` | {count} | {flag} |")
        return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check each package's pyright strict list against measured strict errors."
    )
    parser.add_argument("package_dirs", nargs="*", help="packages/<dist> directories")
    parser.add_argument("--pyright", default="pyright", help="pyright executable (default: pyright)")
    parser.add_argument(
        "--extra-path",
        action="append",
        default=[],
        help="forwarded to pyright extraPaths (repeatable); worktree sibling-package trick",
    )
    parser.add_argument(
        "--table", action="store_true", help="print a Markdown burn-down table instead of notes"
    )
    args = parser.parse_args(argv)

    if not args.package_dirs:
        print("usage: check_pyright_strict_list.py packages/<dist>... [--table]", file=sys.stderr)
        return 2

    failed = False
    rows: list[str] = []
    for raw in args.package_dirs:
        package_dir = Path(raw)
        if not (package_dir / "pyproject.toml").is_file():
            print(f"{raw}: no pyproject.toml", file=sys.stderr)
            return 2
        try:
            import_pkg, strict_list = _PyrightConfig.load(package_dir)
            counts = _StrictRun.run(
                package_dir, import_pkg, pyright=args.pyright, extra_paths=args.extra_path
            )
        except (ValueError, RuntimeError, OSError) as exc:
            print(f"{raw}: {exc}", file=sys.stderr)
            return 2

        if args.table:
            rows.extend(_Policy.table_rows(package_dir.name, strict_list, counts))
            continue

        problems = _Policy.problems(strict_list, counts)
        strict_count = sum(1 for entry in strict_list if entry in counts)
        remaining = sum(count for entry, count in counts.items() if entry not in strict_list)
        print(
            f"{package_dir.name}: {strict_count}/{len(counts)} subpackages strict, "
            f"{remaining} strict error(s) remaining outside the list"
        )
        for problem in problems:
            failed = True
            print(f"  {package_dir.name}: {problem}")

    if args.table:
        print("| package | subpackage | strict errors | strict |")
        print("|---|---|---:|:---:|")
        for row in rows:
            print(row)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
