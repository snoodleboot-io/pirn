#!/usr/bin/env python3
"""CLI over the workspace package graph, for CI (PIR-872; scopes hardened in PIR-873).

Invoked as ``python3 scripts/workspace_packages.py <subcommand>`` — that module's
``__main__`` block dispatches here, so the path every workflow already uses is unchanged.
The graph itself lives in ``scripts/workspace_packages.py`` (``WorkspacePackages``).

Subcommands
-----------
``affected --changed-file FILE [--github-output PATH]``
    The JSON array of packages a change affects, plus the change SCOPE. ``FILE`` lists
    changed paths, one per line, from ``git diff --name-only <merge-base> <head>``. A
    package is affected when a file under ``packages/<pkg>/`` changed or a pirn package
    it depends on (transitively) is affected; any change under ``.github/`` or
    ``scripts/``, or an empty file list, affects every package. A diff that touches no
    package tree at all (``docs/``, ``examples/``, ``Dockerfile*``,
    ``.pre-commit-config.yaml``, other root files) is the ``workspace-only`` scope:
    ``packages=[]`` and ``any=false``, but ``workspace_only=true`` — the per-package
    matrices have nothing to run, the workspace-wide gates still must. The command
    asserts that every package whose tree the diff touches is in the result, and that
    an empty result is always accompanied by ``workspace_only=true``, before printing.

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
import sys
from pathlib import Path

from workspace_packages import WorkspacePackages


class WorkspacePackagesCli:
    """Command-line entry point (see the module docstring)."""

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
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
        return parser

    @staticmethod
    def _affected(workspace: WorkspacePackages, changed_file: Path, output: Path | None) -> int:
        changed = changed_file.read_text(encoding="utf-8").splitlines()
        result = workspace.affected(changed)
        outputs = workspace.change_outputs(changed)
        missing = sorted(WorkspacePackages.touched_packages(changed) - set(result))
        if missing:
            print(f"affected-set defect: changed packages missing from {result}: {missing}")
            return 1
        # An empty package set is only ever legitimate as the `workspace-only` scope,
        # where the workspace-wide gates carry the pull request. Any other empty result
        # would mean "run nothing", which is the PIR-873 hole — fail loudly instead.
        if outputs["any"] == "false" and outputs["workspace_only"] != "true":
            print(f"affected-set defect: empty package set outside workspace-only: {outputs}")
            return 1
        print("changed files:", len([c for c in changed if c.strip()]))
        print("scope:", outputs["scope"])
        print("affected:", outputs["packages"])
        if output is not None:
            with output.open("a", encoding="utf-8") as handle:
                for key, value in outputs.items():
                    handle.write(f"{key}={value}\n")
        return 0

    @staticmethod
    def main(argv: list[str] | None = None, repo_root: Path | None = None) -> int:
        args = WorkspacePackagesCli._parser().parse_args(argv)
        workspace = WorkspacePackages(repo_root or Path(__file__).resolve().parents[1])
        if args.command == "affected":
            return WorkspacePackagesCli._affected(workspace, args.changed_file, args.github_output)
        if args.command == "closure-wheels":
            paths = workspace.closure_wheels(
                args.package, args.dist, include_self=not args.exclude_self
            )
            print(" ".join(str(path) for path in paths))
            return 0
        if args.command == "closure":
            print(" ".join(workspace.closure(args.package, include_self=not args.exclude_self)))
            return 0
        if args.command == "version":
            print(workspace.version(args.package))
            return 0
        print(",".join(workspace.test_extras(args.package)))
        return 0


if __name__ == "__main__":
    sys.exit(WorkspacePackagesCli.main())
