"""Guard: no ``test_*`` definition may be silently uncollectable (PIR-875).

pytest collects ``test_*`` functions only at module level or directly inside
a collectable class.  A ``def test_*`` nested in a function body (for
example left behind after a ``return``) or sitting in a plain helper class is
never collected, so it never runs and never fails.  This walks every test
file in the workspace with ``ast`` and names each offender by file and line.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _test_files() -> list[Path]:
    roots = [*sorted((_REPO_ROOT / "packages").glob("*/tests")), _REPO_ROOT / "scripts" / "tests"]
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                files.append(path)
    return sorted(files)


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return ""


def _collectable_classes(tree: ast.Module) -> set[str]:
    """Module classes whose tests run: Test*, TestCase-derived, or mixed into one."""
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    collectable = {name for name in classes if name.startswith("Test")}
    changed = True
    while changed:
        changed = False
        for name, node in classes.items():
            if name in collectable:
                continue
            for base in node.bases:
                base_name = _base_name(base)
                if base_name.endswith("TestCase") or base_name in collectable:
                    collectable.add(name)
                    changed = True
                    break
    # A mixin is fine when a collectable class inherits its tests.
    inherited = {_base_name(b) for name in collectable for b in classes[name].bases}
    return collectable | (inherited & classes.keys())


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    collectable = _collectable_classes(tree)
    found: list[str] = []

    def visit(node: ast.AST, in_function: bool, owner: ast.ClassDef | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _FUNCTION_NODES):
                if child.name.startswith("test"):
                    where = f"{path.relative_to(_REPO_ROOT)}:{child.lineno}"
                    if in_function:
                        found.append(f"{where} {child.name}: nested inside a function body")
                    elif owner is not None and owner.name not in collectable:
                        found.append(
                            f"{where} {child.name}: in class {owner.name}, "
                            "which pytest does not collect"
                        )
                visit(child, True, None)
            elif isinstance(child, ast.ClassDef):
                visit(child, in_function, child)
            else:
                visit(child, in_function, owner)

    visit(tree, False, None)
    return found


class NoDeadTestMethodsTests(unittest.TestCase):
    def test_no_test_definition_is_uncollectable(self) -> None:
        offenders: list[str] = []
        for path in _test_files():
            offenders.extend(_violations(path))
        assert not offenders, (
            "These test_* definitions can never run (nested in a function body "
            "or in a class pytest ignores); move them to module level or into "
            "a unittest.TestCase / Test* class:\n  " + "\n  ".join(offenders)
        )

    def test_guard_sees_the_workspace(self) -> None:
        assert len(_test_files()) > 1000
