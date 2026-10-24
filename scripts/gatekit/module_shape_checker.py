"""``ModuleShapeChecker`` — how a module is laid out: classes, functions, constants.

Rules
-----
``multi_class_file``
    More than one top-level class in a file.
``module_level_function``
    A module-level ``def``, excluding ``__dunder__`` names (PEP 562 ``__getattr__``
    and friends) and functions decorated with ``@KnotFactory.knot``, which is a knot
    definition written in function syntax. Everything else is a ``@staticmethod``.
``nested_def_missing_override``
    A ``def``/``class`` nested inside a *function* with no ``# design-decision-override``
    comment on one of the three lines above it. A class nested in a class is a method
    and is never flagged.
``filename_mismatch``
    The filename does not match the first public top-level class under an
    alnum-lowercase comparison, so ``OpenAIClient`` in ``openai_client.py`` passes.
``module_level_constant``
    A module-scope binding that is neither an import, a ``def``, a ``class``, a dunder
    (``__all__``), nor a type alias. ``.claude/conventions/languages/python.md``:
    "never define ``CONSTANT = value`` at module level" — whatever its case, so a
    lowercase ``_logger = logging.getLogger(__name__)`` or ``_gr_clean = 20.0`` is the
    same finding as an UPPER_SNAKE one. Module scope includes the body of a
    module-level ``if``/``try``/``for``/``while``/``with``/``match``.
``reexport_module``
    A module whose only statements, after its docstring, ``from __future__`` imports
    and an ``__all__``, are imports — including imports wrapped in a trivial
    ``if TYPE_CHECKING:`` or ``try: ... except ImportError:`` block, which is the same
    module wearing a hat.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from gatekit.ast_shapes import AstShapes
from gatekit.source_file import SourceFile
from gatekit.violation import Violation


class ModuleShapeChecker:
    """The structural rules about a module's own layout."""

    _knot_factory_decorator: ClassVar[str] = "knot"
    _type_constructor_calls: ClassVar[frozenset[str]] = frozenset(
        {"TypeVar", "ParamSpec", "TypeVarTuple", "NewType", "NamedTuple", "TypedDict"}
    )
    _override_marker: ClassVar[str] = "design-decision-override"
    _override_lookback: ClassVar[int] = 3

    def check(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        violations.extend(self._check_multi_class(source_file))
        violations.extend(self._check_module_level_functions(source_file))
        violations.extend(self._check_nested_defs(source_file))
        violations.extend(self._check_filename(source_file))
        violations.extend(self._check_module_constants(source_file))
        violations.extend(self._check_reexport(source_file))
        return violations

    # -- classes -------------------------------------------------------------

    @staticmethod
    def _top_level_classes(source_file: SourceFile) -> list[ast.ClassDef]:
        return [stmt for stmt in source_file.tree.body if isinstance(stmt, ast.ClassDef)]

    def _check_multi_class(self, source_file: SourceFile) -> list[Violation]:
        classes = self._top_level_classes(source_file)
        if len(classes) <= 1:
            return []
        return [
            Violation(
                "multi_class_file",
                source_file.path,
                classes[1].lineno,
                f"{len(classes)} top-level classes in one file — one class per file",
            )
        ]

    def _check_filename(self, source_file: SourceFile) -> list[Violation]:
        public = [
            node for node in self._top_level_classes(source_file) if not node.name.startswith("_")
        ]
        if not public:
            return []
        first = public[0]
        if AstShapes.alnum_lower(source_file.path.stem) == AstShapes.alnum_lower(first.name):
            return []
        return [
            Violation(
                "filename_mismatch",
                source_file.path,
                first.lineno,
                f"filename {source_file.path.stem!r} does not match first public class "
                f"{first.name!r}",
            )
        ]

    # -- functions -----------------------------------------------------------

    def _check_module_level_functions(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        for stmt in source_file.tree.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if AstShapes.is_dunder(stmt.name):
                continue
            decorators = {
                AstShapes.dotted_name(AstShapes.decorator_expr(decorator)).rsplit(".", 1)[-1]
                for decorator in stmt.decorator_list
            }
            if self._knot_factory_decorator in decorators:
                continue
            violations.append(
                Violation(
                    "module_level_function",
                    source_file.path,
                    stmt.lineno,
                    f"module-level function {stmt.name!r} — use a @staticmethod inside a class",
                )
            )
        return violations

    def _check_nested_defs(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        self._visit_nested(source_file, source_file.tree, 0, violations)
        return violations

    def _visit_nested(
        self,
        source_file: SourceFile,
        node: ast.AST,
        function_depth: int,
        violations: list[Violation],
    ) -> None:
        for child in ast.iter_child_nodes(node):
            is_function = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if function_depth > 0 and not self._has_override_comment(source_file, child.lineno):
                    kind = "function" if is_function else "class"
                    violations.append(
                        Violation(
                            "nested_def_missing_override",
                            source_file.path,
                            child.lineno,
                            f"nested {kind} {child.name!r} has no "
                            "#design-decision-override comment",
                        )
                    )
            self._visit_nested(
                source_file,
                child,
                function_depth + 1 if is_function else function_depth,
                violations,
            )

    def _has_override_comment(self, source_file: SourceFile, lineno: int) -> bool:
        """The marker on one of the three lines above ``lineno``.

        ``ruff format`` rewrites ``#design-decision-override`` as
        ``# design-decision-override``, so both spellings are the same marker.
        """
        first = max(0, lineno - self._override_lookback - 1)
        for line in source_file.lines[first : lineno - 1]:
            if self._override_marker in line:
                return True
        return False

    # -- constants -----------------------------------------------------------

    def _check_module_constants(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        for stmt in AstShapes.module_scope_statements(source_file.tree.body):
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            if self.is_type_alias(stmt):
                continue
            for target in AstShapes.assignment_targets(stmt):
                if not isinstance(target, ast.Name) or AstShapes.is_dunder(target.id):
                    continue
                violations.append(
                    Violation(
                        "module_level_constant",
                        source_file.path,
                        stmt.lineno,
                        f"module-level constant {target.id!r} — a value lives on the class "
                        "that uses it (a private ClassVar), in a config class or in YAML, "
                        "never at module scope",
                    )
                )
        return violations

    @classmethod
    def is_type_alias(cls, stmt: ast.stmt) -> bool:
        """True for a type alias, which is a declaration rather than a stored value."""
        if isinstance(stmt, ast.TypeAlias):
            return True
        if isinstance(stmt, ast.AnnAssign) and AstShapes.dotted_name(stmt.annotation).endswith(
            "TypeAlias"
        ):
            return True
        value = AstShapes.assigned_value(stmt)
        if value is None:
            return False
        if isinstance(value, ast.Call):
            return (
                AstShapes.dotted_name(value.func).rsplit(".", 1)[-1] in cls._type_constructor_calls
            )
        if isinstance(value, ast.Subscript):
            return True
        return isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr)

    # -- re-export modules ---------------------------------------------------

    def _check_reexport(self, source_file: SourceFile) -> list[Violation]:
        body = AstShapes.without_docstring(source_file.tree.body)
        remaining = [
            stmt
            for stmt in body
            if not (isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__")
            and not self._is_dunder_all(stmt)
        ]
        if not remaining or not all(self._is_import_only(stmt) for stmt in remaining):
            return []
        return [
            Violation(
                "reexport_module",
                source_file.path,
                remaining[0].lineno,
                "module only re-exports imported names — delete it and import from the "
                "module that defines them",
            )
        ]

    @staticmethod
    def _is_dunder_all(stmt: ast.stmt) -> bool:
        return any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in AstShapes.assignment_targets(stmt)
        )

    def _is_import_only(self, stmt: ast.stmt) -> bool:
        """An import, or a compound block whose every branch only imports.

        ``if TYPE_CHECKING: from x import Y`` and ``try: from x import Y except
        ImportError: raise`` are re-exports wearing a hat; the old rule saw a
        non-import statement and passed the module.
        """
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            return True
        if isinstance(stmt, (ast.Pass, ast.Raise)):
            return True
        if not isinstance(stmt, (ast.If, ast.Try, ast.TryStar)):
            return False
        return all(
            self._is_import_only(inner)
            for block in AstShapes.nested_blocks(stmt)
            for inner in AstShapes.without_docstring(block)
        )
