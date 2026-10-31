"""``AgentsSourceIndex`` — one cached walk of ``pirn_agents`` shared by every ratchet.

Every shape ratchet in this test tree asks the same two questions of the
package: *which classes exist* (and, for a ``Knot`` question, which of them are
``Knot`` subclasses at runtime) and *what does each class's source look like*.
Answering them once here keeps the ratchets consistent — they cannot disagree
about scope — and keeps a full-package walk from being repeated per test.

Membership is decided at runtime: every module under ``pirn_agents`` is
imported and every class whose ``__module__`` is that module is indexed, so a
renamed or re-parented base cannot silently drop a class out of a ``Knot``
scan. The body is read from the module's AST, because a shape is only visible
there. No module list, directory list or class-name list scopes any scan.
"""

from __future__ import annotations

import ast
import functools
import importlib
import pkgutil
from pathlib import Path

from pirn.core.knot import Knot

import pirn_agents
from tests.source_shapes import SourceShapes


class AgentsSourceIndex:
    """Cached runtime + AST index of every module and class in ``pirn_agents``."""

    @staticmethod
    def package_root() -> Path:
        """Return the ``pirn_agents`` source directory."""
        return Path(pirn_agents.__path__[0])

    @staticmethod
    @functools.cache
    def modules() -> dict[str, ast.Module]:
        """Return ``{"relative/path.py": module_ast}`` for every source file."""
        root = AgentsSourceIndex.package_root()
        found: dict[str, ast.Module] = {}
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            found[relative] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return found

    @staticmethod
    @functools.cache
    def classes() -> dict[str, tuple[type, ast.ClassDef]]:
        """Return ``{"relative/path.py::Name": (cls, class_ast)}`` for every class.

        Only classes defined at a module's top level are indexed: a class
        built inside a function body is part of that function's shape and is
        scanned with it.
        """
        root = AgentsSourceIndex.package_root()
        trees = AgentsSourceIndex.modules()
        found: dict[str, tuple[type, ast.ClassDef]] = {}
        for info in pkgutil.walk_packages(pirn_agents.__path__, pirn_agents.__name__ + "."):
            module = importlib.import_module(info.name)
            module_file = module.__file__
            if module_file is None:
                continue
            relative = Path(module_file).relative_to(root).as_posix()
            nodes = {
                node.name: node for node in trees[relative].body if isinstance(node, ast.ClassDef)
            }
            for name, node in nodes.items():
                obj = vars(module).get(name)
                if isinstance(obj, type) and obj.__module__ == info.name:
                    found[f"{relative}::{name}"] = (obj, node)
        return dict(sorted(found.items()))

    @staticmethod
    def knots() -> dict[str, tuple[type, ast.ClassDef]]:
        """Return the subset of :meth:`classes` that are ``Knot`` subclasses.

        Membership is runtime ``issubclass``, so a renamed or re-parented base
        cannot drop a knot out of a scan.
        """
        return {
            label: entry
            for label, entry in AgentsSourceIndex.classes().items()
            if issubclass(entry[0], Knot)
        }

    @staticmethod
    def classes_by_type() -> dict[type, tuple[str, ast.ClassDef]]:
        """Return ``{cls: (label, class_ast)}`` — the inverse of :meth:`classes`."""
        return {cls: (label, node) for label, (cls, node) in AgentsSourceIndex.classes().items()}

    @staticmethod
    def classes_by_name() -> dict[str, tuple[str, type, ast.ClassDef]]:
        """Return ``{ClassName: (label, cls, class_ast)}``.

        Class names are unique across the workspace (the registry-uniqueness
        gate), so a bare name found in an annotation resolves to one class.
        """
        return {
            node.name: (label, cls, node)
            for label, (cls, node) in AgentsSourceIndex.classes().items()
        }

    @staticmethod
    def own_methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
        """Return the methods defined directly in ``node``'s body, by name."""
        return SourceShapes.methods_of(node)

    @staticmethod
    def inherited_method_names(subject: type, node: ast.ClassDef) -> frozenset[str]:
        """Return the names in ``node``'s body that override an inherited method.

        A method a base already defines is an *override* of that base's seam;
        a method no base defines is a surface this class adds of its own.
        """
        own = frozenset(SourceShapes.methods_of(node))
        inherited = {name for base in subject.__mro__[1:] for name in vars(base)}
        return own & frozenset(inherited)

    @staticmethod
    def agents_mro_nodes(subject: type) -> list[tuple[str, type, ast.ClassDef]]:
        """Return ``(label, cls, class_ast)`` for ``subject`` and every ``pirn_agents`` base.

        Ordered as the MRO, so a method defined on a mixin that ``subject``
        does not override is still attributed to (and scanned with) it.
        """
        by_type = AgentsSourceIndex.classes_by_type()
        found: list[tuple[str, type, ast.ClassDef]] = []
        for base in subject.__mro__:
            entry = by_type.get(base)
            if entry is not None:
                label, node = entry
                found.append((label, base, node))
        return found
