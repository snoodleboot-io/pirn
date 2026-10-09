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
from typing import ClassVar


class CheckNoImportForwarding:
    """AST gate rejecting unused re-exports in ``__init__.py`` files."""

    # No exemptions. The former pirn-core entries were resolved in PIR-744 — the core
    # façade was stripped so the convention now applies uniformly. Keep this empty:
    # add an entry only with a named, reviewed justification.
    _allowlist: ClassVar[frozenset[str]] = frozenset()

    _skip_dir_names: ClassVar[frozenset[str]] = frozenset(
        {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".ruff_cache"}
    )

    @staticmethod
    def _own_top_package(path: Path) -> str | None:
        """The outermost package dir in the chain of ``__init__.py`` directories."""
        top = path.parent
        while (top.parent / "__init__.py").exists():
            top = top.parent
        return top.name

    @staticmethod
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

    @staticmethod
    def _collect_candidates(body: list[ast.stmt], candidates: list[ast.ImportFrom]) -> None:
        """Append every ``from ... import`` in *body* (descending into ``if`` blocks)."""
        for node in body:
            if isinstance(node, ast.ImportFrom):
                candidates.append(node)
            elif isinstance(node, ast.If):
                CheckNoImportForwarding._collect_candidates(node.body, candidates)
                CheckNoImportForwarding._collect_candidates(node.orelse, candidates)
            # ast.Try bodies are intentionally not descended into.

    @staticmethod
    def _forwarding_candidates(tree: ast.Module) -> list[ast.ImportFrom]:
        """Every ``from ... import`` that could be a re-export.

        Includes imports nested under ``if TYPE_CHECKING:`` / ``if ...:`` blocks — a
        re-export hidden there is still forwarding — but excludes ``try`` bodies, where
        ``from .backend import X`` guarded by ``except ImportError`` is a legitimate
        optional-dependency fallback, not a public re-export.
        """
        candidates: list[ast.ImportFrom] = []
        CheckNoImportForwarding._collect_candidates(tree.body, candidates)
        return candidates

    @staticmethod
    def check_file(path: Path) -> list[str]:
        """Every forwarding re-export in *path* (non-``__init__.py`` files are skipped)."""
        if path.name != "__init__.py":
            return []
        if path.as_posix() in CheckNoImportForwarding._allowlist:
            return []
        top = CheckNoImportForwarding._own_top_package(path)
        if top is None:
            return []
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            return [f"{path}: could not parse ({exc})"]

        violations: list[str] = []
        for node in CheckNoImportForwarding._forwarding_candidates(tree):
            if node.module is None:
                continue
            if not (node.module == top or node.module.startswith(f"{top}.")):
                continue
            used = CheckNoImportForwarding._used_names(tree, exclude=node)
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

    @staticmethod
    def resolve_paths(args: list[str]) -> tuple[list[Path], list[str]]:
        """Expand CLI arguments into ``__init__.py`` files, reporting unusable paths.

        Directories are walked; individual Python files are taken as given. Anything
        else — a missing path, a non-Python file — is an error rather than a silent
        skip, so a miswired invocation fails loudly instead of scanning nothing.
        """
        files: list[Path] = []
        errors: list[str] = []
        seen: set[Path] = set()

        for arg in args:
            path = Path(arg)
            if not path.exists():
                errors.append(f"{arg}: no such file or directory")
            elif path.is_dir():
                for found in sorted(path.rglob("__init__.py")):
                    skip = CheckNoImportForwarding._skip_dir_names
                    if not any(part in skip for part in found.parts) and found not in seen:
                        seen.add(found)
                        files.append(found)
            elif path.suffix != ".py":
                errors.append(f"{arg}: not a Python file")
            elif path not in seen:
                seen.add(path)
                files.append(path)
        return files, errors

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        """Scan the paths named by *argv*; return the process exit code."""
        args = sys.argv[1:] if argv is None else argv
        if not args:
            print(
                "usage: check_no_import_forwarding.py <file-or-directory>...",
                file=sys.stderr,
            )
            return 2

        files, errors = CheckNoImportForwarding.resolve_paths(args)
        for error in errors:
            print(error, file=sys.stderr)
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
            violations.extend(CheckNoImportForwarding.check_file(path))
        for violation in violations:
            print(violation)
        return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(CheckNoImportForwarding.main())
