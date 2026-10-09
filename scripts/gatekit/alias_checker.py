"""``AliasChecker`` — a second name for something that already has one.

pirn is alpha: a replaced name is deleted and every caller moved to the real one. An
alias is how a rename survives as a shim, so every shape an alias can take is a
finding:

``module_alias_assignment``
    A module-scope assignment whose value names something the module defines or
    imports: ``OldName = NewName``, ``old_helper = Class.method``. Also the
    *call-rooted* form the old gate missed entirely —
    ``available_extras = CapabilityProbe().available_extras``, a bound method lifted to
    module scope so old call sites keep working. Type aliases
    (``JsonValue = dict[str, Any]``) and literals are declarations, not aliases.

``class_alias_assignment``
    The same shim at class scope: ``class Widget: old_method = new_method``. Only an
    alias *of a callable* counts — a class attribute holding an enum member or a
    default value (``seed_kind = PatternSeedKind.VALUE``) is a value, not a second
    name for a method, and is not flagged.

``payload_alias_property``
    A ``@property`` on a ``Payload``/``PirnOpaqueValue`` subclass whose body only reads
    the canonical field: ``return self.metadata["run_id"]``,
    ``return self._data.rows`` — and, which the old rule missed,
    ``return self.metadata.get("run_id")`` and ``return self.metadata.get("x", 0)``.
    The canonical ``metadata``/``data`` accessors themselves are not aliases.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from gatekit.ast_shapes import AstShapes
from gatekit.class_hierarchy_index import ClassHierarchyIndex
from gatekit.knot_design_checker import KnotDesignChecker
from gatekit.source_file import SourceFile
from gatekit.violation import Violation


class AliasChecker:
    """Finds module-scope, class-scope and payload-property aliases."""

    _payload_fields: ClassVar[frozenset[str]] = frozenset(
        {"metadata", "data", "_metadata", "_data"}
    )
    _mapping_readers: ClassVar[frozenset[str]] = frozenset({"get", "__getitem__"})

    def __init__(self, index: ClassHierarchyIndex, knots: KnotDesignChecker) -> None:
        self._index = index
        self._knots = knots

    def check(self, source_file: SourceFile) -> list[Violation]:
        violations = self._check_module_aliases(source_file)
        for node in ast.walk(source_file.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            violations.extend(self._check_class_aliases(source_file, node))
            if self._knots.is_payload(node):
                violations.extend(self._check_payload_properties(source_file.path, node))
        return violations

    # -- module scope --------------------------------------------------------

    def _check_module_aliases(self, source_file: SourceFile) -> list[Violation]:
        statements = AstShapes.module_scope_statements(source_file.tree.body)
        bound = self._module_bound_names(statements)
        violations: list[Violation] = []
        for stmt in statements:
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            value = AstShapes.assigned_value(stmt)
            targets = AstShapes.assignment_targets(stmt)
            if value is None or not all(isinstance(target, ast.Name) for target in targets):
                continue
            if not self._is_alias_of_callable(source_file, value, bound):
                continue
            names = ", ".join(ast.unparse(target) for target in targets)
            violations.append(
                Violation(
                    "module_alias_assignment",
                    source_file.path,
                    stmt.lineno,
                    f"module-scope alias {names} = {ast.unparse(value)} — delete the old "
                    "name and move every caller to the real one",
                )
            )
        return violations

    @staticmethod
    def _module_bound_names(statements: list[ast.stmt]) -> set[str]:
        bound: set[str] = set()
        for stmt in statements:
            if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                bound.add(stmt.name)
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound.add(alias.asname or alias.name.split(".", 1)[0])
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    bound.add(alias.asname or alias.name)
        return bound

    def _is_alias_of_callable(
        self, source_file: SourceFile, value: ast.expr, bound: set[str]
    ) -> bool:
        """True when ``value`` is a second name for a class or function of this workspace.

        The old rule flagged any module-scope ``x = <name chain>`` whose root was bound
        in the module, which made pytest's own ``pytestmark = pytest.mark.slow``
        protocol a "deprecation alias" 50 times over. What makes an alias an alias is
        that the thing on the right is *callable code this repository defines* — a
        class or a method — so a renamed class kept alive under its old name is caught
        and a marker, a setting or a captured builtin is not.
        """
        if self.is_call_rooted_alias(source_file, value):
            return True
        if not isinstance(value, (ast.Name, ast.Attribute)):
            return False
        root = AstShapes.root_name(value)
        if root is None or root not in bound:
            return False
        resolved = self._index.resolve(source_file, value)
        if resolved is None:
            return False
        if self._index.is_callable_id(resolved):
            return True
        if isinstance(value, ast.Attribute):
            owner = self._index.resolve(source_file, value.value)
            return owner is not None and self._index.has_method(owner, value.attr)
        return False

    def is_call_rooted_alias(self, source_file: SourceFile, value: ast.expr) -> bool:
        """``CapabilityProbe().available_extras`` — a bound method lifted to module scope.

        The chain is rooted in a *call*, so the old "value is a Name or Attribute"
        test never saw it. Only a chain whose final attribute is a real method of the
        constructed workspace class counts; ``Path(__file__).parent`` is a value.
        """
        if not isinstance(value, ast.Attribute):
            return False
        call = self._constructor_call(value)
        if call is None:
            return False
        class_id = self._index.resolve_call_target(source_file, call)
        return class_id is not None and self._index.has_method(class_id, value.attr)

    @staticmethod
    def _constructor_call(value: ast.Attribute) -> ast.Call | None:
        node: ast.expr = value.value
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        return node if isinstance(node, ast.Call) else None

    # -- class scope ---------------------------------------------------------

    def _check_class_aliases(self, source_file: SourceFile, node: ast.ClassDef) -> list[Violation]:
        violations: list[Violation] = []
        for stmt in node.body:
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            value = AstShapes.assigned_value(stmt)
            if value is None or not isinstance(value, (ast.Name, ast.Attribute)):
                continue
            if not self._names_a_callable(source_file, node, value):
                continue
            for target in AstShapes.assignment_targets(stmt):
                if not isinstance(target, ast.Name):
                    continue
                violations.append(
                    Violation(
                        "class_alias_assignment",
                        source_file.path,
                        stmt.lineno,
                        f"class-scope alias {node.name}.{target.id} = "
                        f"{AstShapes.dotted_name(value)} — delete the old name and move "
                        "every caller to the real one",
                    )
                )
        return violations

    def _names_a_callable(
        self, source_file: SourceFile, node: ast.ClassDef, value: ast.Name | ast.Attribute
    ) -> bool:
        """True when ``value`` is a second name for a method of *this* class.

        Only a same-class method alias is a shim. A class attribute pointing at some
        *other* class (``SQLAgent._executor_class = SQLExecutor``, a test base class's
        ``sub_type = _Sub``) is a wiring choice — the thing it names has one name, and
        this attribute is not a second one.
        """
        if isinstance(value, ast.Name):
            return AstShapes.find_method(node, value.id) is not None
        owner = self._index.resolve(source_file, value.value)
        return owner is not None and owner == self._index.class_id(node)

    # -- payload alias properties -------------------------------------------

    def _check_payload_properties(self, path: Path, node: ast.ClassDef) -> list[Violation]:
        violations: list[Violation] = []
        for stmt in node.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = {
                AstShapes.dotted_name(AstShapes.decorator_expr(decorator)).rsplit(".", 1)[-1]
                for decorator in stmt.decorator_list
            }
            if "property" not in decorators:
                continue
            body = AstShapes.without_docstring(stmt.body)
            if len(body) != 1 or not isinstance(body[0], ast.Return):
                continue
            returned = body[0].value
            if returned is None or not self._is_payload_field_read(returned, stmt.name):
                continue
            violations.append(
                Violation(
                    "payload_alias_property",
                    path,
                    stmt.lineno,
                    f"{node.name}.{stmt.name} only returns {ast.unparse(returned)} — "
                    "delete the alias and read the canonical field",
                )
            )
        return violations

    def _is_payload_field_read(self, node: ast.expr, property_name: str) -> bool:
        """``self.<field>`` optionally followed by one ``.name``/``[key]``/``.get(key)``."""
        inner = node
        indirect = False
        if isinstance(node, ast.Call):
            name = AstShapes.dotted_name(node.func).rsplit(".", 1)[-1]
            if name not in self._mapping_readers or not isinstance(node.func, ast.Attribute):
                return False
            if not all(isinstance(argument, ast.Constant) for argument in node.args):
                return False
            inner = node.func.value
            indirect = True
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            inner = node.value
            indirect = True
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            inner = node.value
            indirect = True
        if not (
            isinstance(inner, ast.Attribute)
            and isinstance(inner.value, ast.Name)
            and inner.value.id == "self"
            and inner.attr in self._payload_fields
        ):
            return False
        if not indirect and inner.attr.lstrip("_") == property_name:
            return False  # the canonical metadata/data accessor itself
        return True
