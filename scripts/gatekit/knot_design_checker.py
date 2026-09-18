"""``KnotDesignChecker`` — the knot-design rules, over classes resolved by hierarchy.

Every rule here is keyed on ``ClassHierarchyIndex``: a class is a knot because its
bases *resolve* to ``pirn.core.knot.Knot``, not because one of its base expressions
happens to spell a name on a list. The name list missed 61 real knots — every class
whose base is an intermediate the list did not name (``Check``, ``Router``,
``Retriever``, ``Tool``, ``PoolMergeKnot``, ``KFoldValidatorBase``) and every class
written ``class Loop(LoopSubTapestry[State])``, whose subscripted base the old
``_dotted_name`` reduced to the empty string.

Rules
-----
``gate_wrong_base``
    A class whose name ends in ``Gate`` that does not resolve to
    ``pirn.nodes.gate.gate.Gate``. Pytest suites (a ``Test``-prefixed class with no
    ``__init__``) are test *descriptions* of a gate, not gates, and are skipped.
``knot_init_impure``
    A knot's ``__init__`` does something other than guard its inputs, wire them and
    hand the wiring to the framework — it *reaches out*: opens a file, queries a
    store, asks a provider. See ``_check_init`` for the exact accepted shapes.
``knot_super_init_argument``
    An argument *of* the ``super().__init__(...)`` call that is not wiring, so the
    constructor stayed "one statement" while the work moved inside the parentheses.
    ``cache={k: open(k).read() for k in paths}`` is the shape the old rule accepted,
    because it counted *any* dict comprehension as fan-in wiring.
``knot_self_assignment``
    An ``__init__`` that stores a constructor *input* as instance state. The test is
    on the value, not the attribute name: ``self._llm = llm`` is a finding,
    ``self._frozen = True`` is the framework's immutability latch and is not, and
    ``_mutable_``-prefixed attributes are the sanctioned run-scoped slots.
``knot_property``
    A ``@property``/``@cached_property`` on a knot.
``knot_process_kwargs_name``
    ``process(**kwargs)`` whose catch-all is not named ``_``.

Framework roots
---------------
A root is named by its fully qualified class id, never by file name or class name, so a
class that merely reuses ``Knot`` or ``Aggregator`` as its name in another file or
package is an ordinary knot and is checked. See ``framework_root_ids`` for the three
roots and why each one is one, and ``_check_init`` for the one further, *evidence-based*
exemption: a pirn-core knot that wires itself through ``Knot``'s private ``_bootstrap``
seam is defining a primitive rather than being wired by the framework.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from gatekit.ast_shapes import AstShapes
from gatekit.class_hierarchy_index import ClassHierarchyIndex
from gatekit.source_file import SourceFile
from gatekit.violation import Violation


class KnotDesignChecker:
    """Applies the knot-design rules to every class in a file."""

    knot_root_id: ClassVar[str] = "pirn.core.knot.Knot"
    gate_root_id: ClassVar[str] = "pirn.nodes.gate.gate.Gate"
    payload_root_ids: ClassVar[frozenset[str]] = frozenset(
        {"pirn.core.payload.Payload", "pirn.core.pirn_opaque_value.PirnOpaqueValue"}
    )
    # Framework roots, by qualified class id. Each one is the definition of the
    # primitive the rules describe, so the rules cannot apply to it; see the module
    # docstring. Nothing else is exempt — there is no path allowlist.
    framework_root_ids: ClassVar[frozenset[str]] = frozenset(
        {
            # Knot.__init__ *is* the introspection that turns a subclass's constructor
            # kwargs into parents, and Knot.knot_id/config/parents are the framework's
            # read-only accessors over its own _mutable_ state.
            "pirn.core.knot.Knot",
            # Aggregator.process(**inputs) is the variadic fan-in primitive whose
            # parents are named at construction rather than in a signature.
            "pirn.nodes.aggregator.Aggregator",
            # Parameter is the core vocabulary's named, typed input holder: its whole
            # purpose is to *be* a declared input, so the spec it is constructed with is
            # exposed through read-only accessors rather than arriving in process().
            "pirn.core.parameter.Parameter",
        }
    )
    _fan_in_node_names: ClassVar[frozenset[str]] = frozenset(
        {"Aggregator", "Reduce", "Parameter", "Map", "ZipMap", "DictMap"}
    )
    _property_decorators: ClassVar[frozenset[str]] = frozenset({"property", "cached_property"})
    _max_wiring_depth: ClassVar[int] = 8
    _bootstrap_seam: ClassVar[str] = "_bootstrap"
    _mutable_prefix: ClassVar[str] = "_mutable_"
    _core_module_prefix: ClassVar[str] = "pirn."
    # Calls that only rearrange values already in hand. Wiring may reshape its inputs;
    # what it may not do is reach out — open a file, query a store, ask a provider.
    _structural_calls: ClassVar[frozenset[str]] = frozenset(
        {
            "abs",
            "all",
            "any",
            "bool",
            "callable",
            "dict",
            "enumerate",
            "float",
            "format",
            "frozenset",
            "hash",
            "int",
            "isinstance",
            "issubclass",
            "len",
            "list",
            "max",
            "min",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "sorted",
            "str",
            "sum",
            "tuple",
            "type",
            "zip",
        }
    )
    # Reads on a value the constructor already holds, with no side effect.
    _structural_reads: ClassVar[frozenset[str]] = frozenset(
        {"copy", "count", "get", "index", "items", "keys", "values"}
    )

    def __init__(self, index: ClassHierarchyIndex) -> None:
        self._index = index

    # -- entry point ---------------------------------------------------------

    def check(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        for node in ast.walk(source_file.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            violations.extend(self._check_gate_base(source_file, node))
            class_id = self._index.class_id(node)
            if class_id in self.framework_root_ids:
                continue
            if not self._index.is_subclass(class_id, frozenset({self.knot_root_id})):
                continue
            violations.extend(self._check_init(source_file.path, node))
            violations.extend(self._check_self_assignment(source_file.path, node))
            violations.extend(self._check_property(source_file.path, node))
            violations.extend(self._check_process_kwargs(source_file.path, node))
        return violations

    def is_knot(self, class_node: ast.ClassDef) -> bool:
        return self._index.is_subclass(
            self._index.class_id(class_node), frozenset({self.knot_root_id})
        )

    def is_payload(self, class_node: ast.ClassDef) -> bool:
        return self._index.is_subclass(self._index.class_id(class_node), self.payload_root_ids)

    # -- gate ----------------------------------------------------------------

    def _check_gate_base(self, source_file: SourceFile, node: ast.ClassDef) -> list[Violation]:
        if not node.name.endswith("Gate"):
            return []
        class_id = self._index.class_id(node)
        if class_id == self.gate_root_id:
            return []
        if self._is_pytest_suite(node):
            return []
        if self._index.is_subclass(class_id, frozenset({self.gate_root_id})):
            return []
        return [
            Violation(
                "gate_wrong_base",
                source_file.path,
                node.lineno,
                f"class {node.name!r} ends in 'Gate' but does not extend "
                f"{self.gate_root_id} (resolved bases: "
                f"{self._index.base_ids(source_file, node) or 'none'})",
            )
        ]

    @staticmethod
    def _is_pytest_suite(node: ast.ClassDef) -> bool:
        """A ``Test``-prefixed class with no ``__init__`` — what pytest collects."""
        return node.name.startswith("Test") and AstShapes.find_method(node, "__init__") is None

    # -- __init__ ------------------------------------------------------------

    def _check_init(self, path: Path, node: ast.ClassDef) -> list[Violation]:
        """Every statement of ``__init__`` is a guard, a wiring assignment or the
        one call that hands the wiring to the framework.

        Accepted, in any order but with exactly one wiring call:

        * the docstring;
        * a *guard* — ``if <condition>: raise <Error>(...)`` — which
          ``.claude/conventions/languages/python.md`` ("Type Checking Enforcement")
          requires of a constructor that takes runtime-bound inputs;
        * an assignment of a wiring value to a local name or to ``self.<attr>``
          (whether that attribute may hold an *input* is ``knot_self_assignment``'s
          question, not this rule's);
        * exactly one ``super().__init__(...)``.

        A pirn-core knot whose ``__init__`` instead goes through ``Knot``'s private
        ``_bootstrap`` seam is *defining* a framework primitive rather than being wired
        by the framework: it proves, in code, that ``Knot.__init__``'s kwargs
        introspection cannot describe its shape (``Branch`` builds one child knot per
        branch name; ``Reduce`` reads ``combine``'s signature to choose its form). Those
        two rules do not apply to it — the others still do. This is a *criterion*, not a
        list of blessed files: the ``pirn/nodes/`` path allowlist it replaces covered 21
        files and hid 28 findings, including one in ``nested_run_knot.py``, and
        ``_bootstrap`` being private is what keeps the criterion inside pirn-core.
        """
        init = AstShapes.find_method(node, "__init__")
        if init is None:
            return []
        body = AstShapes.without_docstring(init.body)
        if not body:
            return []
        in_core = (self._index.class_id(node) or "").startswith(self._core_module_prefix)
        if in_core and self._uses_bootstrap_seam(init):
            return []
        wiring_call: ast.Call | None = None
        for stmt in body:
            call = self._wiring_call(stmt, in_core=False)
            if call is not None and wiring_call is None:
                wiring_call = call
                continue
            if self._is_wiring_statement(stmt):
                continue
            return [
                Violation(
                    "knot_init_impure",
                    path,
                    stmt.lineno,
                    f"{node.name}.__init__ does more than guard and wire its inputs: "
                    f"{ast.unparse(stmt).splitlines()[0]!r}",
                )
            ]
        if wiring_call is None:
            return [
                Violation(
                    "knot_init_impure",
                    path,
                    init.lineno,
                    f"{node.name}.__init__ never calls super().__init__(...) — the "
                    "framework never learns this knot's parents or config",
                )
            ]
        unwired = [
            ast.unparse(argument)
            for argument in self._call_arguments(wiring_call)
            if not self._is_wiring(argument, 0)
        ]
        if unwired:
            return [
                Violation(
                    "knot_super_init_argument",
                    path,
                    wiring_call.lineno,
                    f"{node.name}.__init__ computes {unwired[0]!r} inside "
                    "super().__init__(...) — the constructor is wiring only, so the "
                    "value belongs in a parent node or in process()",
                )
            ]
        return []

    def _is_wiring_statement(self, stmt: ast.stmt) -> bool:
        """A guard, a wiring assignment, or an ``if`` whose branches are only those.

        ``if check is not None: parents["check"] = check`` wires an optional parent; the
        rule is about what a constructor *does*, and a branch over wiring is wiring.
        """
        if isinstance(stmt, ast.Raise):
            return True
        if isinstance(stmt, ast.If):
            if not self._is_wiring(stmt.test, 0):
                return False
            return all(
                self._is_wiring_statement(inner)
                for block in AstShapes.nested_blocks(stmt)
                for inner in block
            )
        return self._is_wiring_assignment(stmt)

    @staticmethod
    def _call_arguments(call: ast.Call) -> list[ast.expr]:
        return [*call.args, *(keyword.value for keyword in call.keywords)]

    @staticmethod
    def _parameter_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        arguments = function.args
        names = {
            argument.arg
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            )
        }
        if arguments.vararg is not None:
            names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            names.add(arguments.kwarg.arg)
        return names

    @classmethod
    def _uses_bootstrap_seam(cls, init: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """``__init__`` wires itself through ``Knot``'s private ``_bootstrap`` seam."""
        return any(
            isinstance(node, ast.Attribute)
            and node.attr == cls._bootstrap_seam
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            for node in ast.walk(init)
        )

    @classmethod
    def _wiring_call(cls, stmt: ast.stmt, *, in_core: bool) -> ast.Call | None:
        """``super().__init__(...)``, or ``self._bootstrap(...)`` inside pirn-core."""
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
            return None
        call = stmt.value
        func = call.func
        if not isinstance(func, ast.Attribute):
            return None
        if (
            func.attr == "__init__"
            and isinstance(func.value, ast.Call)
            and isinstance(func.value.func, ast.Name)
            and func.value.func.id == "super"
        ):
            return call
        if (
            in_core
            and func.attr == cls._bootstrap_seam
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
        ):
            return call
        return None

    def _is_wiring_assignment(self, stmt: ast.stmt) -> bool:
        """An assignment of a wiring value to a local name or to ``self.<attr>``."""
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            return False
        value = AstShapes.assigned_value(stmt)
        if value is None or not self._is_wiring(value, 0):
            return False
        targets = AstShapes.assignment_targets(stmt)
        return all(
            isinstance(target, ast.Name)
            or (
                isinstance(target, (ast.Attribute, ast.Subscript))
                and AstShapes.root_name(AstShapes.chain_root(target)) is not None
            )
            for target in targets
        )

    def _is_wiring(self, node: ast.expr, depth: int) -> bool:
        """True when ``node`` only names inputs, literals and fan-in nodes.

        This is what makes ``knot_super_init_argument`` real: a dict *comprehension*
        used to number parents is wiring only when the values it collects are
        themselves wiring, so ``{k: open(k).read() for k in paths}`` — which the old
        gate accepted because "any dict comprehension counts as fan-in" — is not.
        """
        if depth > self._max_wiring_depth:
            return False
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            inner = AstShapes.chain_root(node)
            if isinstance(inner, ast.Call):
                return self._is_wiring(inner, depth + 1)
            # An attribute read — of an input, of a class attribute, of an imported
            # name — computes nothing and reaches nowhere.
            return isinstance(inner, ast.Name)
        if isinstance(node, (ast.BoolOp, ast.IfExp, ast.Compare, ast.UnaryOp, ast.BinOp)):
            return all(
                self._is_wiring(child, depth + 1)
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.expr)
            )
        if isinstance(node, ast.JoinedStr):
            return all(
                self._is_wiring(value.value, depth + 1)
                for value in node.values
                if isinstance(value, ast.FormattedValue)
            )
        if isinstance(node, ast.Starred):
            return self._is_wiring(node.value, depth + 1)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return all(self._is_wiring(element, depth + 1) for element in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                (key is None or self._is_wiring(key, depth + 1))
                and self._is_wiring(value, depth + 1)
                for key, value in zip(node.keys, node.values, strict=True)
            )
        if isinstance(node, (ast.DictComp, ast.SetComp, ast.ListComp, ast.GeneratorExp)):
            return self._is_wiring_comprehension(node, depth)
        if isinstance(node, ast.Call):
            return self._is_structural_call(node, depth)
        return False

    def _is_wiring_comprehension(
        self,
        node: ast.DictComp | ast.SetComp | ast.ListComp | ast.GeneratorExp,
        depth: int,
    ) -> bool:
        for generator in node.generators:
            if not self._is_wiring(generator.iter, depth + 1):
                return False
            if not all(self._is_wiring(test, depth + 1) for test in generator.ifs):
                return False
        if isinstance(node, ast.DictComp):
            return self._is_wiring(node.key, depth + 1) and self._is_wiring(node.value, depth + 1)
        return self._is_wiring(node.elt, depth + 1)

    def _is_structural_call(self, node: ast.Call, depth: int) -> bool:
        """A call that only rearranges values: a fan-in node, a config, a pure builtin.

        ``open(path).read()`` and ``client.fetch()`` are not among them, which is what
        makes ``cache={k: open(k).read() for k in paths}`` — accepted by the old rule
        because "any dict comprehension counts as fan-in" — a finding.
        """
        name = AstShapes.dotted_name(node.func).rsplit(".", 1)[-1]
        structural = (
            name in self._fan_in_node_names
            or name in self._structural_calls
            or name.endswith("Config")
        )
        if not structural and isinstance(node.func, ast.Attribute):
            structural = name in self._structural_reads and self._is_wiring(
                node.func.value, depth + 1
            )
        if not structural:
            return False
        return all(self._is_wiring(argument, depth + 1) for argument in self._call_arguments(node))

    # -- instance state, properties, process ---------------------------------

    @classmethod
    def _check_self_assignment(cls, path: Path, node: ast.ClassDef) -> list[Violation]:
        """Rule 4: a constructor *input* must not become instance state.

        What the rule is about is the input, so the test is on the value, not on the
        attribute: ``self._task = task`` stores an input and is a finding, while
        ``self._frozen = True`` is the framework's own immutability latch and stores
        nothing the caller passed. ``_mutable_``-prefixed attributes are the sanctioned
        run-scoped slots and are never findings.
        """
        init = AstShapes.find_method(node, "__init__")
        if init is None:
            return []
        parameters = cls._parameter_names(init) - {"self"}
        violations: list[Violation] = []
        for child in ast.walk(init):
            if not isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            value = AstShapes.assigned_value(child)
            if value is None or not (cls._names_read(value) & parameters):
                continue
            for target in AstShapes.assignment_targets(child):
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and not target.attr.startswith(cls._mutable_prefix)
                ):
                    violations.append(
                        Violation(
                            "knot_self_assignment",
                            path,
                            child.lineno,
                            f"{node.name}.__init__ stores the input "
                            f"{ast.unparse(value)!r} as self.{target.attr} — an input "
                            "arrives in process(), it is not instance state",
                        )
                    )
        return violations

    @staticmethod
    def _names_read(node: ast.expr) -> set[str]:
        return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}

    @classmethod
    def _check_property(cls, path: Path, node: ast.ClassDef) -> list[Violation]:
        violations: list[Violation] = []
        for stmt in node.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = {
                AstShapes.dotted_name(AstShapes.decorator_expr(decorator)).rsplit(".", 1)[-1]
                for decorator in stmt.decorator_list
            }
            if names & cls._property_decorators:
                violations.append(
                    Violation(
                        "knot_property",
                        path,
                        stmt.lineno,
                        f"{node.name}.{stmt.name} is a @property/@cached_property on a knot",
                    )
                )
        return violations

    @staticmethod
    def _check_process_kwargs(path: Path, node: ast.ClassDef) -> list[Violation]:
        process = AstShapes.find_method(node, "process")
        if process is None or process.args.kwarg is None:
            return []
        if process.args.kwarg.arg == "_":
            return []
        return [
            Violation(
                "knot_process_kwargs_name",
                path,
                process.lineno,
                f"{node.name}.process(**{process.args.kwarg.arg}) — the catch-all is **_",
            )
        ]
