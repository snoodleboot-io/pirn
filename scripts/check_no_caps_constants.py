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

Invocation modes (PIR-856)
---------------------------
Pre-commit passes explicit changed ``.py`` file paths and no ``--baseline``:
behaviour is unchanged from before this option existed — any violation fails
(exit 1), no files given exits 0.

CI (``workspace.yml``) passes package import root directories (``packages/*/
pirn*``, i.e. source only — a directory argument is walked for ``*.py``,
skipping ``tests/``, ``.venv``/``venv``, ``__pycache__``, and any
``conftest.py``) together with ``--baseline scripts/caps_constants_baseline.json``.
With ``--baseline``, violations are counted per package (the ``packages/<dist>/``
path segment; a file outside any ``packages/`` tree buckets under ``""``) and
compared against that file's ``{package: count}`` ratchet: the gate FAILS only
when a package's count *exceeds* its baseline, and prints a "baseline can be
lowered" note when a count is strictly below it. ``--write-baseline``
regenerates the file from the current tree and exits 0.

At the time this baseline was introduced, pirn-agents carried 19 UPPER_SNAKE
constants that the agents-rules PIR-856 lane is fixing concurrently. The
integrator is expected to run ``--write-baseline`` again after every lane
merges so the ratchet reflects the post-merge state.
"""

from __future__ import annotations

import argparse
import ast
import json
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


def _package_of(path: Path) -> str:
    """The ``packages/<dist>/`` segment a file lives under, or ``""``."""
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "packages" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _load_baseline(baseline_path: Path) -> dict[str, int]:
    if not baseline_path.exists():
        return {}
    with baseline_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_baseline(baseline_path: Path, counts: dict[str, int]) -> None:
    with baseline_path.open("w", encoding="utf-8") as fh:
        json.dump(counts, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reject UPPER_SNAKE_CASE constants at module/class scope."
    )
    parser.add_argument("paths", nargs="*", help="Files (pre-commit) or directories (CI) to scan")
    parser.add_argument(
        "--baseline",
        default=None,
        help="Ratchet baseline JSON ({package: count}). Omit for pre-commit's any-violation-fails mode.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Regenerate the baseline file from the current tree and exit 0.",
    )
    args = parser.parse_args(argv)

    files = _resolve_paths(args.paths)
    violations_by_package: dict[str, list[str]] = {}
    for path in files:
        violations_by_package.setdefault(_package_of(path), []).extend(check_file(path))

    if args.write_baseline:
        baseline_path = Path(args.baseline or "scripts/caps_constants_baseline.json")
        counts = {pkg: len(vs) for pkg, vs in violations_by_package.items()}
        _write_baseline(baseline_path, counts)
        print(f"wrote baseline for {len(counts)} package(s) to {baseline_path}")
        return 0

    all_violations = [v for vs in violations_by_package.values() for v in vs]
    for v in all_violations:
        print(v)

    if args.baseline is None:
        # Pre-commit contract, unchanged: any violation fails.
        return 1 if all_violations else 0

    baseline = _load_baseline(Path(args.baseline))
    failed = False
    for package, vs in sorted(violations_by_package.items()):
        count = len(vs)
        baseline_count = baseline.get(package, 0)
        if count > baseline_count:
            failed = True
            print(
                f"{package or '(unscoped)'}: constant count {count} exceeds baseline {baseline_count}"
            )
        elif count < baseline_count:
            print(
                f"baseline can be lowered: {package or '(unscoped)'}: is {count}, baseline says {baseline_count}"
            )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
