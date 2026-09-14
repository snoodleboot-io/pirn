#!/usr/bin/env python3
"""Pre-commit hook / CI gate: reject UPPER_SNAKE_CASE assignments at module or class scope.

Disallowed
----------
Module-level constants:      MY_CONST = 42
Class-level constants:       class Foo: MY_CONST = 42

Allowed
-------
Enum / IntEnum members:      class Color(Enum): RED = 1
Dunder names:                __all__, __version__, etc.
Single-letter type vars:     T, K, V  (not ALL_CAPS, so not matched)
TypeVar / ParamSpec:         _T = TypeVar("T")  (value is a TypeVar call)
Annotated type aliases:      MyType = Union[int, str]  (PascalCase — not matched)

Invocation
----------
Pre-commit passes explicit changed ``.py`` file paths; CI (``workspace.yml``)
passes package import root directories (``packages/*/pirn*``, i.e. source
only — a directory argument is walked for ``*.py``, skipping ``tests/``,
``.venv``/``venv``, ``__pycache__``, and any ``conftest.py``). There is no
baseline: any violation fails (exit 1); no violation, or no files, exits 0.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_SKIP_DIR_NAMES = frozenset({"tests", ".venv", "venv", "__pycache__", ".ruff_cache", ".tox"})

_CAPS_RE_MIN_LEN = 2  # require at least 2 uppercase chars to avoid flagging `T`, `K`


def _is_all_caps(name: str) -> bool:
    if name.startswith("__") and name.endswith("__"):
        return False
    if len(name) < _CAPS_RE_MIN_LEN:
        return False
    return (name == name.upper() and "_" in name) or (
        name.isupper() and len(name) >= _CAPS_RE_MIN_LEN
    )


def _base_names(bases: list[ast.expr]) -> list[str]:
    names: list[str] = []
    for base in bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _is_enum_class(node: ast.ClassDef) -> bool:
    enum_bases = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}
    return bool(set(_base_names(node.bases)) & enum_bases)


_TYPEVAR_CALLS = {"TypeVar", "ParamSpec", "TypeVarTuple", "NewType"}


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
        return name in _TYPEVAR_CALLS
    return False


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


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            for stmt in node.body:
                if _is_typevar_assignment(stmt):
                    continue
                for name in _assignment_names(stmt):
                    if _is_all_caps(name):
                        violations.append(
                            f"{path}:{stmt.lineno}: module-level constant {name!r} — "
                            "use pydantic-settings or a config class instead of UPPER_SNAKE constants"
                        )

        elif isinstance(node, ast.ClassDef):
            if _is_enum_class(node):
                continue
            for stmt in node.body:
                if _is_typevar_assignment(stmt):
                    continue
                for name in _assignment_names(stmt):
                    if _is_all_caps(name):
                        violations.append(
                            f"{path}:{stmt.lineno}: class-level constant {name!r} in {node.name!r} — "
                            "use instance attributes or a config class instead of UPPER_SNAKE constants"
                        )

    return violations


def _resolve_paths(args: list[str]) -> list[Path]:
    """Expand CLI arguments into ``.py`` files.

    A directory is walked recursively for ``*.py``, skipping ``tests/``,
    ``.venv``/``venv``, ``__pycache__``, and any ``conftest.py`` — the "source
    only" contract CI uses (``packages/*/pirn*``). A file argument is taken
    as given, matching pre-commit's one-changed-file-per-argument invocation;
    a non-``.py`` file argument is silently ignored, matching this script's
    behaviour before directory arguments were supported.
    """
    files: list[Path] = []
    for arg in args:
        path = Path(arg)
        if path.is_dir():
            for candidate in sorted(path.rglob("*.py")):
                if candidate.name == "conftest.py":
                    continue
                if any(part in _SKIP_DIR_NAMES for part in candidate.parts):
                    continue
                files.append(candidate)
        elif path.suffix == ".py":
            files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reject UPPER_SNAKE_CASE constants at module/class scope."
    )
    parser.add_argument("paths", nargs="*", help="Files (pre-commit) or directories (CI) to scan")
    args = parser.parse_args(argv)

    violations = [v for path in _resolve_paths(args.paths) for v in check_file(path)]
    for v in violations:
        print(v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
