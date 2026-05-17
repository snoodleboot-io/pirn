#!/usr/bin/env python3
"""Pre-commit hook: reject UPPER_SNAKE_CASE assignments at module or class scope.

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
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_CAPS_RE_MIN_LEN = 2  # require at least 2 uppercase chars to avoid flagging `T`, `K`


def _is_all_caps(name: str) -> bool:
    if name.startswith("__") and name.endswith("__"):
        return False
    if len(name) < _CAPS_RE_MIN_LEN:
        return False
    return (name == name.upper() and "_" in name) or (name.isupper() and len(name) >= _CAPS_RE_MIN_LEN)


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
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
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


def main() -> int:
    files = [Path(p) for p in sys.argv[1:] if p.endswith(".py")]
    all_violations: list[str] = []
    for path in files:
        all_violations.extend(check_file(path))

    for v in all_violations:
        print(v)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
