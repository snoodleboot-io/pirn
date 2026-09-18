#!/usr/bin/env python3
"""Pre-commit hook / CI gate: reject UPPER_SNAKE_CASE assignments at module or class scope.

Disallowed
----------
Module-level constants:      MY_CONST = 42
Class-level constants:       class Foo: MY_CONST = 42

Module scope is not just ``tree.body``: an ``if TYPE_CHECKING:`` / ``try:`` /
``for`` / ``while`` / ``with`` / ``match`` block at module level executes at
module scope too, so a constant bound inside one is a module-level constant and
is reported. The same holds for compound blocks inside a class body.

Allowed
-------
Enum / IntEnum members:      class Color(Enum): RED = 1
Dunder names:                __all__, __version__, etc.
Single-letter type vars:     T, K, V  (not ALL_CAPS, so not matched)
TypeVar / ParamSpec:         _T = TypeVar("T")  (value is a TypeVar call)
Annotated type aliases:      MyType = Union[int, str]  (PascalCase — not matched)

CLI contract
------------
Pre-commit passes explicit changed ``.py`` file paths; CI (``workspace.yml``)
passes package import root directories (``packages/*/pirn*``, i.e. source
only — a directory argument is walked for ``*.py``, skipping ``tests/``,
``.venv``/``venv``, ``__pycache__``, and any ``conftest.py``). There is no
baseline: any violation fails.

* ``0`` — files were checked and are clean, **or** every argument was an
  existing non-``.py`` file (pre-commit hands a hook whatever it staged; a
  ``.md``/``.toml`` path is legitimately nothing for this gate to check).
* ``1`` — findings, printed one per line on stdout.
* ``2`` — unusable invocation: no arguments, an argument that does not exist,
  or a directory argument matching zero ``.py`` files. A gate that checked
  nothing must never report success, and a file it cannot parse is a failure
  rather than a silent skip.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import ClassVar

from gatekit.ast_shapes import AstShapes


class CheckNoCapsConstants:
    """AST gate rejecting UPPER_SNAKE constants at module or class scope."""

    _skip_dir_names: ClassVar[frozenset[str]] = frozenset(
        {"tests", ".venv", "venv", "__pycache__", ".ruff_cache", ".tox"}
    )
    # Require at least 2 uppercase chars so bare type vars (`T`, `K`) are not flagged.
    _min_caps_length: ClassVar[int] = 2
    _enum_bases: ClassVar[frozenset[str]] = frozenset(
        {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}
    )
    _typevar_calls: ClassVar[frozenset[str]] = frozenset(
        {"TypeVar", "ParamSpec", "TypeVarTuple", "NewType"}
    )

    @staticmethod
    def _is_all_caps(name: str) -> bool:
        if name.startswith("__") and name.endswith("__"):
            return False
        if len(name) < CheckNoCapsConstants._min_caps_length:
            return False
        return (name == name.upper() and "_" in name) or (
            name.isupper() and len(name) >= CheckNoCapsConstants._min_caps_length
        )

    @staticmethod
    def _base_names(bases: list[ast.expr]) -> list[str]:
        names: list[str] = []
        for base in bases:
            if isinstance(base, ast.Name):
                names.append(base.id)
            elif isinstance(base, ast.Attribute):
                names.append(base.attr)
        return names

    @staticmethod
    def _is_enum_class(node: ast.ClassDef) -> bool:
        return bool(
            set(CheckNoCapsConstants._base_names(node.bases)) & CheckNoCapsConstants._enum_bases
        )

    @staticmethod
    def _is_typevar_assignment(node: ast.stmt) -> bool:
        """Return True if the node is `X = TypeVar(...)` or similar typing constructs."""
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
        if value is None:
            return False
        if isinstance(value, ast.Call):
            func = value.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else (func.attr if isinstance(func, ast.Attribute) else None)
            )
            return name in CheckNoCapsConstants._typevar_calls
        return False

    @staticmethod
    def _assignment_names(node: ast.stmt) -> list[str]:
        names: list[str] = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.append(elt.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
        return names

    @staticmethod
    def _caps_names(statements: list[ast.stmt]) -> list[tuple[ast.stmt, str]]:
        """Every ``(statement, name)`` pair that binds an UPPER_SNAKE name."""
        found: list[tuple[ast.stmt, str]] = []
        for stmt in statements:
            if CheckNoCapsConstants._is_typevar_assignment(stmt):
                continue
            for name in CheckNoCapsConstants._assignment_names(stmt):
                if CheckNoCapsConstants._is_all_caps(name):
                    found.append((stmt, name))
        return found

    @staticmethod
    def check_file(path: Path) -> list[str]:
        """Every UPPER_SNAKE binding at module or class scope in *path*.

        A file that cannot be read or parsed is itself a violation: a gate that
        silently skips a file it does not understand reports success for code it
        never checked.
        """
        violations: list[str] = []
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return [f"{path}: could not read the file ({error}) — the gate cannot check it"]
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as error:
            line = error.lineno or 0
            return [
                f"{path}:{line}: could not parse the file ({error.msg}) — "
                "the gate cannot check a file that does not parse"
            ]

        for stmt, name in CheckNoCapsConstants._caps_names(
            AstShapes.module_scope_statements(tree.body)
        ):
            violations.append(
                f"{path}:{stmt.lineno}: module-level constant {name!r} — "
                "use pydantic-settings or a config class instead of UPPER_SNAKE constants"
            )

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or CheckNoCapsConstants._is_enum_class(node):
                continue
            for stmt, name in CheckNoCapsConstants._caps_names(
                AstShapes.module_scope_statements(node.body)
            ):
                violations.append(
                    f"{path}:{stmt.lineno}: class-level constant {name!r} in {node.name!r} — "
                    "use instance attributes or a config class instead of UPPER_SNAKE constants"
                )

        return violations

    @staticmethod
    def resolve_paths(args: list[str]) -> tuple[list[Path], list[str]]:
        """Expand CLI arguments into ``.py`` files, reporting unusable arguments.

        A directory is walked recursively for ``*.py``, skipping ``tests/``,
        ``.venv``/``venv``, ``__pycache__``, and any ``conftest.py`` — the "source
        only" contract CI uses (``packages/*/pirn*``). A directory matching zero
        ``.py`` files and a path that does not exist are errors, so a miswired
        invocation fails loudly instead of passing vacuously. An existing
        non-``.py`` file is skipped: pre-commit hands hooks whatever it staged.
        """
        files: list[Path] = []
        errors: list[str] = []
        seen: set[Path] = set()
        for arg in args:
            path = Path(arg)
            if not path.exists():
                errors.append(f"{arg}: no such file or directory")
                continue
            if path.is_dir():
                matched = 0
                for candidate in sorted(path.rglob("*.py")):
                    if candidate.name == "conftest.py":
                        continue
                    if any(
                        part in CheckNoCapsConstants._skip_dir_names for part in candidate.parts
                    ):
                        continue
                    matched += 1
                    if candidate not in seen:
                        seen.add(candidate)
                        files.append(candidate)
                if matched == 0:
                    errors.append(
                        f"{arg}: directory matched no .py files — refusing to report "
                        "success for a scan that checked nothing"
                    )
            elif path.suffix == ".py" and path not in seen:
                seen.add(path)
                files.append(path)
        return files, errors

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        """Check the paths named by *argv*; return the process exit code."""
        parser = argparse.ArgumentParser(
            description="Reject UPPER_SNAKE_CASE constants at module/class scope."
        )
        parser.add_argument(
            "paths", nargs="*", help="Files (pre-commit) or directories (CI) to scan"
        )
        args = parser.parse_args(argv)

        if not args.paths:
            print(
                "usage: check_no_caps_constants.py <file-or-directory>...",
                file=sys.stderr,
            )
            return 2

        files, errors = CheckNoCapsConstants.resolve_paths(args.paths)
        for error in errors:
            print(error, file=sys.stderr)
        if errors:
            return 2

        violations = [v for path in files for v in CheckNoCapsConstants.check_file(path)]
        for violation in violations:
            print(violation)
        return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(CheckNoCapsConstants.main())
