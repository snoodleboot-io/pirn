#!/usr/bin/env python3
"""The workspace's package graph, for CI: affected packages and this build's wheels (PIR-872).

Stdlib only; every answer is read from the packages' own ``pyproject.toml`` files, so
the CI jobs and this script cannot disagree about the dependency graph.

Subcommands
-----------
``affected --changed-file FILE [--github-output PATH]``
    The JSON array of packages a change affects. ``FILE`` lists changed paths, one
    per line, from ``git diff --name-only <merge-base> <head>``. A package is affected
    when a file under ``packages/<pkg>/`` changed or a pirn package it depends on
    (transitively) is affected; any change under ``.github/`` or ``scripts/``, or an
    empty file list, affects every package. The command asserts that every package
    whose tree the diff touches is in the result before printing it.

``closure-wheels PKG --dist DIR [--exclude-self]``
    The wheel file paths in ``DIR`` for ``PKG`` and every pirn package it depends on.
    CI installs these by path so a job tests this build, never a same-named release
    resolved from the public index. Exactly one wheel per distribution must exist.

``closure PKG [--exclude-self]``
    The pirn distribution names of that closure, space separated.

``version PKG``
    The version ``PKG``'s ``pyproject.toml`` declares.

``test-extras PKG``
    ``PKG``'s optional extras that a per-package CI job installs: every extra except
    the heavy ML ones and any extra that pulls another pirn distribution (those would
    resolve from the index, not this build).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path


class WorkspacePackages:
    """The pirn distributions under ``packages/`` and the dependency edges between them."""

    _SHARED_PREFIXES = (".github/", "scripts/")
    _HEAVY_EXTRAS = frozenset({"pytorch", "tensorflow", "tflite"})
    _REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

    def __init__(self, repo_root: Path) -> None:
        self._projects: dict[str, dict[str, object]] = {}
        for pyproject in sorted((repo_root / "packages").glob("*/pyproject.toml")):
            project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
            self._projects[str(project["name"])] = project

    @classmethod
    def _requirement_name(cls, requirement: str) -> str:
        match = cls._REQUIREMENT_NAME.match(requirement)
        if match is None:
            raise ValueError(f"unparseable requirement: {requirement!r}")
        return re.sub(r"[-_.]+", "-", match.group(1)).lower()

    def names(self) -> list[str]:
        return sorted(self._projects)

    def _require(self, package: str) -> dict[str, object]:
        if package not in self._projects:
            raise KeyError(
                f"unknown workspace package {package!r}; known: {self.names()}"
            )
        return self._projects[package]

    def pirn_dependencies(self, package: str) -> list[str]:
        """Direct hard dependencies of ``package`` that are workspace packages."""
        requirements = self._require(package).get("dependencies", [])
        assert isinstance(requirements, list)
        names = (self._requirement_name(str(r)) for r in requirements)
        return sorted(name for name in names if name in self._projects)

    def closure(self, package: str, *, include_self: bool = True) -> list[str]:
        seen: set[str] = set()
        stack = [package]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.pirn_dependencies(current))
        if not include_self:
            seen.discard(package)
        return sorted(seen)

    def version(self, package: str) -> str:
        return str(self._require(package)["version"])

    def test_extras(self, package: str) -> list[str]:
        optional = self._require(package).get("optional-dependencies", {})
        assert isinstance(optional, dict)
        extras: list[str] = []
        for extra, requirements in optional.items():
            if extra in self._HEAVY_EXTRAS:
                continue
            if any(
                self._requirement_name(str(r)) in self._projects for r in requirements
            ):
                continue
            extras.append(str(extra))
        return extras

    @classmethod
    def touched_packages(cls, changed: Iterable[str]) -> set[str]:
        touched: set[str] = set()
        for path in changed:
            parts = path.strip().split("/")
            if len(parts) > 2 and parts[0] == "packages":
                touched.add(parts[1])
        return touched

    def affected(self, changed: Iterable[str]) -> list[str]:
        paths = [path.strip() for path in changed if path.strip()]
        if not paths or any(path.startswith(self._SHARED_PREFIXES) for path in paths):
            return self.names()
        touched = self.touched_packages(paths) & set(self._projects)
        return sorted(
            package
            for package in self._projects
            if set(self.closure(package)) & touched
        )

    def closure_wheels(
        self, package: str, dist: Path, *, include_self: bool = True
    ) -> list[Path]:
        wheels: list[Path] = []
        for name in self.closure(package, include_self=include_self):
            stem = name.replace("-", "_")
            version = self.version(name)
            found = sorted(dist.glob(f"{stem}-{version}-*.whl"))
            if len(found) != 1:
                raise FileNotFoundError(
                    f"expected exactly one {stem}-{version}-*.whl in {dist}, found {found}"
                )
            wheels.extend(found)
        return wheels


class WorkspacePackagesCli:
    """Command-line entry point (see the module docstring)."""

    @staticmethod
    def main(argv: list[str] | None = None, repo_root: Path | None = None) -> int:
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        sub = parser.add_subparsers(dest="command", required=True)
        affected = sub.add_parser("affected")
        affected.add_argument("--changed-file", required=True, type=Path)
        affected.add_argument("--github-output", type=Path)
        wheels = sub.add_parser("closure-wheels")
        wheels.add_argument("package")
        wheels.add_argument("--dist", required=True, type=Path)
        wheels.add_argument("--exclude-self", action="store_true")
        closure = sub.add_parser("closure")
        closure.add_argument("package")
        closure.add_argument("--exclude-self", action="store_true")
        sub.add_parser("version").add_argument("package")
        sub.add_parser("test-extras").add_argument("package")
        args = parser.parse_args(argv)

        workspace = WorkspacePackages(repo_root or Path(__file__).resolve().parents[1])
        if args.command == "affected":
            changed = args.changed_file.read_text(encoding="utf-8").splitlines()
            result = workspace.affected(changed)
            missing = sorted(WorkspacePackages.touched_packages(changed) - set(result))
            if missing:
                print(
                    f"affected-set defect: changed packages missing from {result}: {missing}"
                )
                return 1
            print("changed files:", len([c for c in changed if c.strip()]))
            print("affected:", json.dumps(result))
            if args.github_output is not None:
                with args.github_output.open("a", encoding="utf-8") as fh:
                    fh.write(f"packages={json.dumps(result)}\n")
                    fh.write(f"any={'true' if result else 'false'}\n")
            return 0
        if args.command == "closure-wheels":
            paths = workspace.closure_wheels(
                args.package, args.dist, include_self=not args.exclude_self
            )
            print(" ".join(str(path) for path in paths))
            return 0
        if args.command == "closure":
            print(
                " ".join(
                    workspace.closure(args.package, include_self=not args.exclude_self)
                )
            )
            return 0
        if args.command == "version":
            print(workspace.version(args.package))
            return 0
        print(",".join(workspace.test_extras(args.package)))
        return 0


if __name__ == "__main__":
    sys.exit(WorkspacePackagesCli.main())
