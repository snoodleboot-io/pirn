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

Allowlist
---------
Empty. pirn-core's ``__init__.py`` façade previously re-exported its framework
primitives behind a "users may import from pirn directly" contract; PIR-744
resolved that contradiction by stripping the façade, so the convention now applies
uniformly across every package with no exemptions. Add an entry only with a named,
reviewed justification.

CLI contract
------------
Arguments may be individual files (how pre-commit invokes this, one path per
changed file) or directories, which are walked for ``__init__.py`` (how CI
invokes it, e.g. ``packages/``). Exit codes:

* ``0`` — files were scanned and no forwarding was found.
* ``1`` — forwarding violations found (listed on stdout).
* ``2`` — the invocation itself was unusable: a path that does not exist, a
  non-Python file, no arguments, or a set of paths matching zero ``__init__.py``.

The last case matters: an earlier version silently dropped any argument not
ending in ``.py``, so ``check_no_import_forwarding.py packages/`` scanned nothing
and exited ``0``. A gate that passes vacuously is worse than no gate, so a scan
that checked nothing is now an error.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# No exemptions. The former pirn-core entries were resolved in PIR-744 — the core
# façade was stripped so the convention now applies uniformly. Keep this empty:
# add an entry only with a named, reviewed justification.
_ALLOWLIST: frozenset[str] = frozenset()


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


def resolve_paths(args: list[str]) -> tuple[list[Path], list[str]]:
    """Expand CLI arguments into ``__init__.py`` files, reporting unusable paths.

    Directories are walked; individual Python files are taken as given. Anything
    else — a missing path, a non-Python file — is an error rather than a silent
    skip, so a miswired invocation fails loudly instead of scanning nothing.
    """
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".ruff_cache"}
    files: list[Path] = []
    errors: list[str] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        if path not in seen:
            seen.add(path)
            files.append(path)

    for arg in args:
        path = Path(arg)
        if not path.exists():
            errors.append(f"{arg}: no such file or directory")
        elif path.is_dir():
            for found in sorted(path.rglob("__init__.py")):
                if not any(part in skip for part in found.parts):
                    _add(found)
        elif path.suffix != ".py":
            errors.append(f"{arg}: not a Python file")
        else:
            _add(path)
    return files, errors


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(
            "usage: check_no_import_forwarding.py <file-or-directory>...",
            file=sys.stderr,
        )
        return 2

    files, errors = resolve_paths(args)
    for err in errors:
        print(err, file=sys.stderr)
    if errors:
        return 2
    if not files:
        print(
            "no __init__.py matched the given paths — refusing to report success "
            "for a scan that checked nothing",
            file=sys.stderr,
        )
        return 2

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))
    for v in violations:
        print(v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
