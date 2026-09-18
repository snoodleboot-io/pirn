"""``ClassHierarchyIndex`` — resolve class bases across the whole workspace from source.

A gate that recognises a knot by the *name* of its base (``Knot``, ``Source``, …) misses
every class whose base is an intermediate class the list does not name (``Check``,
``Router``, ``Retriever``, a subscripted ``Base[T]``) and wrongly trusts any class that
merely reuses a listed name. This index reads every module's imports and class
definitions, resolves each base expression to the fully qualified class it names, and
answers ``is_subclass`` by walking the resolved hierarchy — no import of the code under
inspection, stdlib only.

Resolution follows ``import``/``from … import`` bindings (absolute and relative), class
definitions at any depth, and names re-bound by another module's import. A base the
workspace does not define (``typing.Protocol``, ``abc.ABC``, a third-party class)
resolves to its dotted import path, so callers can still match it; an expression that
is not a name chain (``make_base()``) resolves to ``None``.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from gatekit.ast_shapes import AstShapes
from gatekit.source_file import SourceFile


class ClassHierarchyIndex:
    """Qualified class ids, their resolved bases and module-level name bindings."""

    _max_depth: ClassVar[int] = 32

    def __init__(self) -> None:
        self._bindings: dict[str, dict[str, str]] = {}
        self._module_scope: dict[str, str] = {}
        self._module_classes: dict[str, dict[str, str]] = {}
        self._class_bases: dict[str, tuple[str, list[ast.expr]]] = {}
        self._class_ids_by_node: dict[int, str] = {}
        self._files_by_key: dict[str, SourceFile] = {}
        self._ancestors: dict[str, frozenset[str]] = {}

    # -- building ---------------------------------------------------------------

    def add_file(self, source_file: SourceFile) -> None:
        key = source_file.module_key
        if key in self._files_by_key:
            return
        self._files_by_key[key] = source_file
        self._module_scope[key] = str(source_file.scope)
        bindings: dict[str, str] = {}
        classes: dict[str, str] = {}
        self._bindings[key] = bindings
        self._module_classes[key] = classes
        package = self._package_of(source_file)
        # Imports anywhere in the file bind (a function-local import is still how a
        # function-local class names its base); module-scope bindings win.
        for node in ast.walk(source_file.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._bind_import(node, package, bindings, overwrite=False)
        for stmt in AstShapes.module_scope_statements(source_file.tree.body):
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self._bind_import(stmt, package, bindings, overwrite=True)
        self._register_classes(key, source_file.tree, "", bindings, classes, top=True)
        self._ancestors.clear()

    def _register_classes(
        self,
        key: str,
        node: ast.AST,
        qualifier: str,
        bindings: dict[str, str],
        classes: dict[str, str],
        *,
        top: bool,
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = f"{qualifier}{child.name}"
                class_id = f"{key}.{qualname}"
                self._class_bases[class_id] = (key, list(child.bases))
                self._class_ids_by_node[id(child)] = class_id
                if top:
                    classes[child.name] = class_id
                    bindings[child.name] = class_id
                else:
                    bindings.setdefault(child.name, class_id)
                self._register_classes(
                    key, child, f"{qualname}.", bindings, classes, top=False
                )
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if top:
                    bindings[child.name] = f"{key}.{qualifier}{child.name}"
                self._register_classes(
                    key,
                    child,
                    f"{qualifier}{child.name}.<locals>.",
                    bindings,
                    classes,
                    top=False,
                )
            elif isinstance(child, ast.stmt) and top:
                # if/try/with/for/while/match blocks at module scope stay "top".
                self._register_classes(key, child, qualifier, bindings, classes, top=True)
            else:
                self._register_classes(key, child, qualifier, bindings, classes, top=False)

    @staticmethod
    def _package_of(source_file: SourceFile) -> str:
        if source_file.is_package_init:
            return source_file.module_name
        return source_file.module_name.rpartition(".")[0]

    @staticmethod
    def _bind_import(
        node: ast.Import | ast.ImportFrom,
        package: str,
        bindings: dict[str, str],
        *,
        overwrite: bool,
    ) -> None:
        pairs: list[tuple[str, str]] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    pairs.append((alias.asname, alias.name))
                else:
                    head = alias.name.split(".", 1)[0]
                    pairs.append((head, head))
        else:
            base = node.module or ""
            if node.level:
                parent = package.split(".") if package else []
                keep = len(parent) - (node.level - 1)
                prefix = ".".join(parent[: max(keep, 0)])
                base = ".".join(part for part in (prefix, base) if part)
            for alias in node.names:
                if alias.name == "*":
                    continue
                pairs.append((alias.asname or alias.name, f"{base}.{alias.name}"))
        for name, target in pairs:
            if overwrite or name not in bindings:
                bindings[name] = target

    # -- querying ---------------------------------------------------------------

    def class_id(self, class_node: ast.ClassDef) -> str | None:
        return self._class_ids_by_node.get(id(class_node))

    def resolve(self, source_file: SourceFile, expr: ast.expr) -> str | None:
        """The qualified id the name chain ``expr`` refers to inside ``source_file``."""
        return self._resolve_in(source_file.module_key, expr)

    def _resolve_in(self, key: str, expr: ast.expr) -> str | None:
        dotted = AstShapes.dotted_name(expr)
        if not dotted:
            return None
        head, _, rest = dotted.partition(".")
        target = self._bindings.get(key, {}).get(head)
        if target is None:
            target = f"builtins.{head}"
        full = f"{target}.{rest}" if rest else target
        return self._canonical(full, key, 0)

    def _canonical(self, dotted: str, context_key: str, depth: int) -> str:
        if dotted in self._class_bases or depth > self._max_depth:
            return dotted
        parts = dotted.split(".")
        scope = self._module_scope.get(context_key)
        for cut in range(len(parts), 0, -1):
            prefix = ".".join(parts[:cut])
            module_key = None
            if scope is not None and f"{scope}|{prefix}" in self._bindings:
                module_key = f"{scope}|{prefix}"
            elif prefix in self._bindings:
                module_key = prefix
            if module_key is None:
                continue
            remaining = parts[cut:]
            if not remaining:
                return module_key
            nested = f"{module_key}.{'.'.join(remaining)}"
            if nested in self._class_bases:
                return nested
            binding = self._bindings[module_key].get(remaining[0])
            if binding is not None and binding != dotted:
                tail = ".".join(remaining[1:])
                return self._canonical(
                    f"{binding}.{tail}" if tail else binding, module_key, depth + 1
                )
            return nested
        return dotted

    def ancestors(self, class_id: str) -> frozenset[str]:
        """Every resolved base id of ``class_id``, transitively (not including itself)."""
        cached = self._ancestors.get(class_id)
        if cached is not None:
            return cached
        self._ancestors[class_id] = frozenset()  # cycle guard
        found: set[str] = set()
        entry = self._class_bases.get(class_id)
        if entry is not None:
            key, bases = entry
            for base in bases:
                resolved = self._resolve_in(key, base)
                if resolved is None or resolved == class_id:
                    continue
                found.add(resolved)
                found |= self.ancestors(resolved)
        result = frozenset(found)
        self._ancestors[class_id] = result
        return result

    def is_subclass(self, class_id: str | None, root_ids: frozenset[str]) -> bool:
        if class_id is None:
            return False
        return class_id in root_ids or bool(self.ancestors(class_id) & root_ids)

    def base_ids(self, source_file: SourceFile, class_node: ast.ClassDef) -> list[str]:
        """The direct bases of ``class_node``, resolved (unresolvable ones omitted)."""
        resolved = (self.resolve(source_file, base) for base in class_node.bases)
        return [base for base in resolved if base is not None]
