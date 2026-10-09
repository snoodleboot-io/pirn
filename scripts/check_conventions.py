#!/usr/bin/env python3
"""AST gate over the house style conventions, across the whole repository.

Checks the rules in ``.claude/conventions/languages/python.md`` and
``docs/contributing/knot-design-rules.md`` that are mechanically detectable from
source text. Stdlib only: nothing under inspection is imported.

What is scanned
---------------
Every path given on the command line, walked for ``*.py``. CI passes
``packages examples scripts``, so package source, package tests, the runnable
examples and the CI tooling itself are all held to the same rules — until PIR-873
the gate scanned ``packages/*/pirn*`` only and skipped every ``tests`` directory,
``examples/`` and ``scripts/`` entirely, which hid the majority of its own findings.

Whatever is scanned, the **whole workspace** (``packages/*/pirn*``) is indexed first,
so a class's bases resolve even when the file that defines them is not being checked.

The rules
---------
``gatekit.module_shape_checker.ModuleShapeChecker``
    ``multi_class_file``, ``module_level_function``, ``nested_def_missing_override``,
    ``filename_mismatch``, ``module_level_constant``, ``reexport_module``.
``gatekit.knot_design_checker.KnotDesignChecker``
    ``gate_wrong_base``, ``knot_init_impure``, ``knot_super_init_argument``,
    ``knot_self_assignment``, ``knot_property``, ``knot_process_kwargs_name``.
``gatekit.alias_checker.AliasChecker``
    ``module_alias_assignment``, ``class_alias_assignment``, ``payload_alias_property``.
``gatekit.deprecation_checker.DeprecationChecker``
    ``deprecation_reference``.
``gatekit.suppression_checker.SuppressionChecker``
    ``suppression_without_rule_or_reason``, ``suppression_unknown_rule``,
    ``file_level_directive``.
Each of those modules' docstrings is the authoritative statement of its rules.

A file that does not parse is reported as ``unparsable_file``. A gate that silently
skips what it cannot read reports success for code it never checked.

Knots are resolved, not guessed
-------------------------------
A class is a knot because ``gatekit.class_hierarchy_index.ClassHierarchyIndex``
resolves its bases — through import bindings, relative imports, intermediate bases and
subscripted generics — to ``pirn.core.knot.Knot``. The list of base *names* this gate
used until PIR-873 missed 61 real knots (every ``Check``, ``Router``, ``Retriever``,
``Tool`` and ``class Loop(LoopSubTapestry[State])``) and would have trusted any class
that merely reused one of its names. The only exemptions are the framework's own
definitions of the primitives the rules describe, named by fully qualified class id in
``KnotDesignChecker.framework_root_ids``. There is no path allowlist and no baseline.

Test code
---------
Test code (anything under a ``tests`` directory, and every ``conftest.py``) is held to
the rules about *meaning* — suppressions, deprecation, aliases, knot design — and not
to the six structural rules in ``ConventionScan.structural_rules``, which are about
file layout. That boundary is a **product decision, not an engineering one**: pytest
collects module-level ``def test_...`` functions and groups them in ``Test*`` classes,
so "one class per file", "no module-level function" and "filename matches the class"
would have to be restated for tests before they could be enforced there
(``.claude/conventions/languages/python.md`` does not currently say what it wants of a
test module). Until it does, enforcing them would mean 5,342 findings across the seven
packages' test trees with no rule to appeal to. Every other rule applies to test code
exactly as it applies to source.

CLI contract
------------
* ``0`` — files were checked and nothing is wrong.
* ``1`` — at least one finding; every violation is listed, then per-package counts.
* ``2`` — the invocation itself was unusable: no arguments, a path that does not
  exist, or paths matching zero Python files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gatekit.convention_scan import ConventionScan
from gatekit.suppression_rule_catalog import SuppressionRuleCatalog


class CheckConventions:
    """Command-line entry point for the house-convention gate."""

    @staticmethod
    def repository_root() -> Path:
        return Path(__file__).resolve().parents[1]

    @staticmethod
    def workspace_import_roots(repository_root: Path) -> list[Path]:
        """``packages/<dist>/<import_pkg>`` for every package in the workspace."""
        return sorted(
            path
            for path in (repository_root / "packages").glob("*/pirn*")
            if path.is_dir() and (path / "__init__.py").is_file()
        )

    @staticmethod
    def build_scan(
        repository_root: Path, paths: list[Path], ruff: str | None = None
    ) -> ConventionScan:
        """A scan that has indexed the whole workspace and collected ``paths``."""
        scan = ConventionScan(repository_root, SuppressionRuleCatalog.from_installed_tools(ruff))
        scan.add_paths(CheckConventions.workspace_import_roots(repository_root), checked=False)
        scan.add_paths(paths, checked=True)
        return scan

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            description="AST gate over the house style conventions (PIR-873)."
        )
        parser.add_argument(
            "paths",
            nargs="*",
            help="Directories or files to check, e.g. packages examples scripts",
        )
        parser.add_argument(
            "--repository-root",
            default=None,
            help="Repository root used to label findings and index the workspace.",
        )
        parser.add_argument(
            "--ruff",
            default=None,
            help="Path to the ruff binary whose rule codes validate '# noqa' comments.",
        )
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)

        if not args.paths:
            print("usage: check_conventions.py <path>...", file=sys.stderr)
            return 2
        paths = [Path(argument) for argument in args.paths]
        missing = [str(path) for path in paths if not path.exists()]
        for path in missing:
            print(f"{path}: no such file or directory", file=sys.stderr)
        if missing:
            return 2

        root = (
            Path(args.repository_root)
            if args.repository_root
            else CheckConventions.repository_root()
        )
        try:
            scan = CheckConventions.build_scan(root, paths, args.ruff)
        except LookupError as error:
            print(f"check_conventions: {error}", file=sys.stderr)
            return 2
        if scan.checked_file_count == 0:
            print(
                "check_conventions: the given paths match no Python file — a gate that "
                "checked nothing must not report success",
                file=sys.stderr,
            )
            return 2

        violations = scan.run()
        for violation in violations:
            print(violation)
        for package, rule_counts in sorted(scan.counts(violations).items()):
            for rule, count in rule_counts.items():
                if count:
                    print(f"{package}: {rule} {count}")
        return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(CheckConventions.main())
