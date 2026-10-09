"""``DeprecationChecker`` — every spelling of "kept around a while longer".

pirn is alpha: a replaced name is deleted in the same change that replaces it, and
every caller is moved. Rule ``deprecation_reference`` therefore rejects, as code (not
as text inside a string or a comment):

* ``DeprecationWarning`` and ``PendingDeprecationWarning`` — the classic spelling;
* ``FutureWarning`` — the same promise under a different class, which the old gate's
  two-name list did not cover;
* ``@deprecated(...)`` (PEP 702, ``warnings.deprecated`` / ``typing_extensions.deprecated``)
  on a class, function or method — a decorator the old gate never looked at;
* the ``_deprecated_since`` marker used as an *identifier* — an attribute, a
  parameter, a bound name, an imported name. Prose that merely mentions the marker
  (this docstring, the rule's own definition) names nothing and is not a finding.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from gatekit.ast_shapes import AstShapes
from gatekit.source_file import SourceFile
from gatekit.violation import Violation


class DeprecationChecker:
    """Finds deprecation machinery of any spelling."""

    _warning_names: ClassVar[frozenset[str]] = frozenset(
        {"DeprecationWarning", "PendingDeprecationWarning", "FutureWarning"}
    )
    _decorator_name: ClassVar[str] = "deprecated"
    _since_marker: ClassVar[str] = "_deprecated_since"

    def check(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        for node in ast.walk(source_file.tree):
            name = self._referenced_warning(node)
            if name is not None:
                violations.append(
                    Violation(
                        "deprecation_reference",
                        source_file.path,
                        node.lineno if isinstance(node, ast.expr) else 1,
                        f"{name} referenced — pirn is alpha: delete the name and move "
                        "every caller, never deprecate it",
                    )
                )
            violations.extend(self._check_decorators(source_file, node))
            violations.extend(self._check_since_marker(source_file, node))
        return violations

    @classmethod
    def _check_since_marker(cls, source_file: SourceFile, node: ast.AST) -> list[Violation]:
        if cls._since_marker not in cls._bound_identifiers(node):
            return []
        return [
            Violation(
                "deprecation_reference",
                source_file.path,
                getattr(node, "lineno", 1),
                f"{cls._since_marker} marker — pirn is alpha: delete the name and move "
                "every caller, never deprecate it",
            )
        ]

    @staticmethod
    def _bound_identifiers(node: ast.AST) -> set[str]:
        """Every identifier ``node`` itself introduces or reads — never string text."""
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, ast.Attribute):
            return {node.attr}
        if isinstance(node, ast.arg):
            return {node.arg}
        if isinstance(node, ast.keyword):
            return {node.arg} if node.arg is not None else set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return {node.name}
        if isinstance(node, ast.alias):
            return {node.asname or node.name}
        return set()

    @classmethod
    def _referenced_warning(cls, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name) and node.id in cls._warning_names:
            return node.id
        if isinstance(node, ast.Attribute) and node.attr in cls._warning_names:
            return node.attr
        return None

    @classmethod
    def _check_decorators(cls, source_file: SourceFile, node: ast.AST) -> list[Violation]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return []
        violations: list[Violation] = []
        for decorator in node.decorator_list:
            dotted = AstShapes.dotted_name(AstShapes.decorator_expr(decorator))
            if dotted.rsplit(".", 1)[-1] != cls._decorator_name:
                continue
            violations.append(
                Violation(
                    "deprecation_reference",
                    source_file.path,
                    decorator.lineno,
                    f"@{dotted} on {node.name!r} (PEP 702) — pirn is alpha: delete the "
                    "name and move every caller, never deprecate it",
                )
            )
        return violations
