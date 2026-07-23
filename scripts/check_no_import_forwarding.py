#!/usr/bin/env python3
"""Reject import forwarding (re-export) in ``__init__.py`` files.

The house convention (``.claude/conventions/languages/python.md``) forbids
re-exporting imported symbols — an ``__init__.py`` that does ``from .foo import
Bar`` purely to expose ``Bar`` at the package root. Public API must be defined
explicitly at the module that owns it, and consumers import from the concrete path.

What counts as forwarding
-------------------------
An ``__init__.py`` statement ``from <own-package>.<...> import <Name>`` where the
imported name is not used within the file. "Own-package" means the import target
starts with the top-level package the ``__init__.py`` belongs to (e.g. an
``__init__.py`` under ``pirn_agents/`` importing from ``pirn_agents.*``).

What is allowed
---------------
* Importing a symbol the ``__init__.py`` actually *uses* (e.g. a ``CapabilityProbe``
  it instantiates, or a registry helper it calls) — that is consumption, not
  forwarding.
* Importing from a *third-party* or *sibling top-level* package.
* ``from __future__ import annotations``.
* A ``__getattr__``-based lazy/deprecation shim (PEP 562) — flagged only if the
  file also has bare forwarding imports.

Core allowlist
--------------
``packages/pirn-core/pirn/__init__.py`` deliberately re-exports its framework
primitives behind a documented "users may import from pirn directly" contract.
That contradiction between the convention and core's public API is a core-owner
decision tracked in PIR-744, not something this gate resolves unilaterally. The
allowlist below names that exemption explicitly rather than scoping the gate to
skip core silently. Remove entries here only when PIR-744 is resolved.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Paths (POSIX, repo-relative) exempted pending PIR-744. Keep this list minimal and
# named — every entry is a known convention violation awaiting a core-owner ruling.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "packages/pirn-core/pirn/__init__.py",
        "packages/pirn-core/pirn/core/identity/__init__.py",
        "packages/pirn-core/pirn/backends/postgres/__init__.py",
        "packages/pirn-core/pirn/backends/sqlite/__init__.py",
        "packages/pirn-core/pirn/backends/valkey/__init__.py",
    }
)


def _own_top_package(path: Path) -> str | None:
    """The outermost package dir in the chain of ``__init__.py`` directories."""
    pkg_dir = path.parent
    top = pkg_dir
    while (top.parent / "__init__.py").exists():
        top = top.parent
    return top.name


def _used_names(tree: ast.Module, exclude: ast.ImportFrom) -> set[str]:
    """Every ``Name`` referenced in the module outside the excluded import."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if node is exclude:
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
    # __all__ string entries also count as "declared public", though the convention
    # wants those defined at the owning module — a re-export listed in __all__ is
    # still forwarding, so we do NOT treat __all__ membership as usage.
    return used


def _forwarding_candidates(tree: ast.Module) -> list[ast.ImportFrom]:
    """Every ``from ... import`` that could be a re-export.

    Includes imports nested under ``if TYPE_CHECKING:`` / ``if ...:`` blocks — a
    re-export hidden there is still forwarding — but excludes ``try`` bodies, where
    ``from .backend import X`` guarded by ``except ImportError`` is a legitimate
    optional-dependency fallback, not a public re-export.
    """
    candidates: list[ast.ImportFrom] = []

    def _visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ImportFrom):
                candidates.append(node)
            elif isinstance(node, ast.If):
                _visit(node.body)
                _visit(node.orelse)
            # ast.Try bodies are intentionally not descended into.

    _visit(tree.body)
    return candidates


def check_file(path: Path) -> list[str]:
    if path.name != "__init__.py":
        return []
    posix = path.as_posix()
    if posix in _ALLOWLIST:
        return []
    top = _own_top_package(path)
    if top is None:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        return [f"{path}: could not parse ({exc})"]

    violations: list[str] = []
    for node in _forwarding_candidates(tree):
        if node.module is None:
            continue
        if not (node.module == top or node.module.startswith(f"{top}.")):
            continue
        used = _used_names(tree, exclude=node)
        for alias in node.names:
            local = alias.asname or alias.name
            if local == "*":
                violations.append(
                    f"{path}:{node.lineno}: star re-export from {node.module!r} — "
                    "define public API explicitly, do not forward"
                )
                continue
            if local not in used:
                violations.append(
                    f"{path}:{node.lineno}: re-exports {local!r} from {node.module!r} "
                    "without using it — import forwarding is not allowed; consumers "
                    "must import from the concrete module"
                )
    return violations


def main() -> int:
    files = [Path(p) for p in sys.argv[1:] if p.endswith(".py")]
    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))
    for v in violations:
        print(v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
