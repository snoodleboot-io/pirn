"""Resolve pirn import paths statically against the repository source tree."""

from __future__ import annotations

import ast
from pathlib import Path


class SourceImportResolver:
    """Answer "does this pirn module / name / dotted path exist?" by reading source.

    Nothing is imported: modules are located as ``packages/<dist>/<root>/.../mod.py``
    or a package directory carrying ``__init__.py``, and names are the top-level
    bindings (class, def, assignment, import) of the parsed module.
    """

    def __init__(self, repo_root: Path) -> None:
        self._roots: dict[str, Path] = {}
        self._bindings: dict[Path, dict[str, ast.stmt]] = {}
        packages = repo_root / "packages"
        if packages.is_dir():
            for dist in sorted(packages.iterdir()):
                root = self.import_root(dist.name)
                if dist.is_dir() and (dist / root).is_dir():
                    self._roots[root] = dist / root

    @staticmethod
    def import_root(dist_name: str) -> str:
        """``pirn-core`` imports as ``pirn``; every other ``pirn-<x>`` as ``pirn_<x>``."""
        if dist_name == "pirn-core":
            return "pirn"
        return "pirn_" + dist_name.removeprefix("pirn-").replace("-", "_")

    @staticmethod
    def is_pirn_root(name: str) -> bool:
        """Whether ``name`` is shaped like a pirn import root (``pirn`` or ``pirn_<x>``)."""
        return name == "pirn" or (name.startswith("pirn_") and len(name) > len("pirn_"))

    def module_file(self, module: str) -> Path | None:
        """The source file of ``module``, or ``None`` when no such module exists."""
        parts = module.split(".")
        base = self._roots.get(parts[0])
        if base is None:
            return None
        target = base.joinpath(*parts[1:])
        package_init = target / "__init__.py"
        if package_init.is_file():
            return package_init
        if len(parts) > 1 and target.with_suffix(".py").is_file():
            return target.with_suffix(".py")
        return None

    def has_name(self, module: str, name: str) -> bool:
        """Whether ``from module import name`` finds a top-level binding or submodule."""
        source = self.module_file(module)
        if source is None:
            return False
        return name in self._module_bindings(source) or (
            self.module_file(f"{module}.{name}") is not None
        )

    def resolves_path(self, dotted: str) -> bool:
        """Whether ``dotted`` names a module, a module attribute, or a class member."""
        parts = dotted.split(".")
        for split in range(len(parts), 0, -1):
            module = ".".join(parts[:split])
            source = self.module_file(module)
            if source is not None:
                return self._resolves_attributes(source, parts[split:], depth=0)
        return False

    def _resolves_attributes(self, source: Path, rest: list[str], depth: int) -> bool:
        if not rest:
            return True
        node = self._module_bindings(source).get(rest[0])
        if node is None:
            return False
        return self._resolves_member(source, node, rest[0], rest[1:], depth)

    def _resolves_member(
        self, source: Path, node: ast.stmt, name: str, rest: list[str], depth: int
    ) -> bool:
        if not rest:
            return True
        if depth > 10:
            return False
        if isinstance(node, ast.ClassDef):
            return self._class_has(source, node, rest, depth + 1)
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                return False
            original = self._imported_original(node, name)
            if not self.is_pirn_root(node.module.split(".")[0]):
                return True
            return self.resolves_path(".".join([node.module, original, *rest]))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return False
        return True

    def _class_has(
        self, source: Path, cls: ast.ClassDef, rest: list[str], depth: int
    ) -> bool:
        members = self._body_bindings(cls.body)
        member = members.get(rest[0])
        if member is not None:
            return self._resolves_member(source, member, rest[0], rest[1:], depth)
        bindings = self._module_bindings(source)
        for base in cls.bases:
            if not isinstance(base, ast.Name):
                continue
            base_node = bindings.get(base.id)
            if base_node is None or base_node is cls:
                continue
            if self._resolves_member(source, base_node, base.id, rest, depth):
                return True
        return False

    @staticmethod
    def _imported_original(node: ast.ImportFrom, bound: str) -> str:
        for alias in node.names:
            if (alias.asname or alias.name) == bound:
                return alias.name
        return bound

    def _module_bindings(self, source: Path) -> dict[str, ast.stmt]:
        cached = self._bindings.get(source)
        if cached is None:
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except SyntaxError:
                tree = ast.Module(body=[], type_ignores=[])
            cached = self._body_bindings(tree.body)
            self._bindings[source] = cached
        return cached

    @classmethod
    def _body_bindings(cls, body: list[ast.stmt]) -> dict[str, ast.stmt]:
        bindings: dict[str, ast.stmt] = {}
        for statement in body:
            if isinstance(
                statement, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ):
                bindings[statement.name] = statement
            elif isinstance(statement, ast.Assign):
                for target in statement.targets:
                    for name in cls._target_names(target):
                        bindings[name] = statement
            elif isinstance(statement, ast.AnnAssign | ast.AugAssign):
                for name in cls._target_names(statement.target):
                    bindings[name] = statement
            elif isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    bindings[alias.asname or alias.name] = statement
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    bindings[alias.asname or alias.name.split(".")[0]] = statement
            elif isinstance(statement, ast.If | ast.Try | ast.With):
                nested = [*statement.body]
                if isinstance(statement, ast.If | ast.Try):
                    nested.extend(statement.orelse)
                if isinstance(statement, ast.Try):
                    for handler in statement.handlers:
                        nested.extend(handler.body)
                    nested.extend(statement.finalbody)
                bindings.update(cls._body_bindings(nested))
        return bindings

    @staticmethod
    def _target_names(target: ast.expr) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Tuple | ast.List):
            return [elt.id for elt in target.elts if isinstance(elt, ast.Name)]
        return []
