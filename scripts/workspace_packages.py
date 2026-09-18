#!/usr/bin/env python3
"""The workspace's package graph, for CI: affected packages and this build's wheels (PIR-872).

Stdlib only; every answer is read from the packages' own ``pyproject.toml`` files, so
the CI jobs and this script cannot disagree about the dependency graph.

The command-line entry point lives in ``scripts/workspace_packages_cli.py``
(``WorkspacePackagesCli``) — one public class per file — and is dispatched from the
``__main__`` block at the bottom, so ``python3 scripts/workspace_packages.py <subcommand>``
keeps working unchanged for every workflow that invokes it.

Change scopes (PIR-873)
-----------------------
A changed-file list maps to exactly one scope, and no scope ever means "run nothing":

``all-packages``
    An empty diff (push to main / dispatch) or a change under ``.github/`` or
    ``scripts/`` — shared CI tooling, so every package is affected.
``affected-packages``
    At least one ``packages/<pkg>/`` tree changed; the affected set is those packages
    plus every package whose dependency closure contains one of them.
``workspace-only``
    Changes that touch no package tree at all — ``docs/``, ``examples/``,
    ``Dockerfile*``, ``.pre-commit-config.yaml``, any other root-level file. NO package
    is affected, so the per-package matrices legitimately have nothing to fan out over,
    but the workspace-wide gates (import-forwarding, conventions, version-lockstep,
    import-graph, doc-imports, scripts/examples ruff) still run. Before PIR-873 this
    scope was an empty affected list and ``any=false``, which skipped every gate job in
    ``.github/workflows/workspace.yml`` — and a skipped job is not a failure, so the
    aggregator went green with zero checks having run.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar


class WorkspacePackages:
    """The pirn distributions under ``packages/`` and the dependency edges between them."""

    _shared_prefixes: ClassVar[tuple[str, ...]] = (".github/", "scripts/")
    _heavy_extras: ClassVar[frozenset[str]] = frozenset({"pytorch", "tensorflow", "tflite"})
    _requirement_name_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)"
    )
    # The three change scopes (see the module docstring). Lowercase private ClassVars,
    # not module-level UPPER_SNAKE constants (python.md).
    _scope_all: ClassVar[str] = "all-packages"
    _scope_affected: ClassVar[str] = "affected-packages"
    _scope_workspace: ClassVar[str] = "workspace-only"

    def __init__(self, repo_root: Path) -> None:
        self._projects: dict[str, dict[str, object]] = {}
        for pyproject in sorted((repo_root / "packages").glob("*/pyproject.toml")):
            project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
            self._projects[str(project["name"])] = project

    @classmethod
    def _requirement_name(cls, requirement: str) -> str:
        match = cls._requirement_name_pattern.match(requirement)
        if match is None:
            raise ValueError(f"unparseable requirement: {requirement!r}")
        return re.sub(r"[-_.]+", "-", match.group(1)).lower()

    def names(self) -> list[str]:
        return sorted(self._projects)

    def _require(self, package: str) -> dict[str, object]:
        if package not in self._projects:
            raise KeyError(f"unknown workspace package {package!r}; known: {self.names()}")
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
            if extra in self._heavy_extras:
                continue
            if any(self._requirement_name(str(r)) in self._projects for r in requirements):
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

    @staticmethod
    def _paths(changed: Iterable[str]) -> list[str]:
        return [path.strip() for path in changed if path.strip()]

    def scope(self, changed: Iterable[str]) -> str:
        """Which of the three change scopes this diff falls into (module docstring)."""
        paths = self._paths(changed)
        if not paths or any(path.startswith(self._shared_prefixes) for path in paths):
            return self._scope_all
        if self.touched_packages(paths) & set(self._projects):
            return self._scope_affected
        return self._scope_workspace

    def affected(self, changed: Iterable[str]) -> list[str]:
        """The packages this diff affects — EMPTY only for the ``workspace-only`` scope.

        An empty list never means "run nothing": read it together with :meth:`scope`
        (or the ``workspace_only`` key of :meth:`change_outputs`), which says the
        workspace-wide gates must still run.
        """
        paths = self._paths(changed)
        if self.scope(paths) == self._scope_all:
            return self.names()
        touched = self.touched_packages(paths) & set(self._projects)
        return sorted(package for package in self._projects if set(self.closure(package)) & touched)

    def change_outputs(self, changed: Iterable[str]) -> dict[str, str]:
        """The ``$GITHUB_OUTPUT`` keys the ``changes`` job publishes for this diff.

        ``packages``/``any`` gate ONLY the per-package matrices. ``scope`` and
        ``workspace_only`` make the docs/examples/root-tooling case explicit, so the
        workspace-wide gates are never keyed off an empty package list.
        """
        scope = self.scope(changed)
        packages = self.affected(changed)
        return {
            "packages": json.dumps(packages),
            "any": "true" if packages else "false",
            "workspace_only": "true" if scope == self._scope_workspace else "false",
            "scope": scope,
        }

    def closure_wheels(self, package: str, dist: Path, *, include_self: bool = True) -> list[Path]:
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


if __name__ == "__main__":
    import sys

    # Imported here, not at module top: `workspace_packages_cli` imports THIS module, so
    # a top-level import would be a cycle. Running `python3 scripts/workspace_packages.py`
    # puts `scripts/` on sys.path[0], which is what makes this resolve.
    from workspace_packages_cli import WorkspacePackagesCli

    sys.exit(WorkspacePackagesCli.main())
