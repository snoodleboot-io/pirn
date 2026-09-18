"""No module-scope constants in pirn_ml (PIR-873).

``.claude/conventions/languages/python.md`` forbids module-level constants: a
value shared by a class's methods belongs to that class as a private
``ClassVar``, where it is namespaced, overridable in a subclass and visible in
the class's own documentation. This walks the package's own source (not its
tests) and fails on any module-scope assignment whose target is not a dunder
such as ``__all__``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pirn_ml


def _module_scope_assignments() -> list[str]:
    """Every ``<name> = ...`` / ``<name>: T = ...`` at module scope in the package."""
    offenders: list[str] = []
    root = Path(next(iter(pirn_ml.__path__)))
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and not (
                    target.id.startswith("__") and target.id.endswith("__")
                ):
                    offenders.append(f"{path.relative_to(root.parent)}:{node.lineno}: {target.id}")
    return offenders


def test_package_declares_no_module_scope_constants() -> None:
    offenders = _module_scope_assignments()
    assert not offenders, (
        "module-scope constants — move each onto the class that uses it as a "
        "private ClassVar: " + ", ".join(offenders)
    )
