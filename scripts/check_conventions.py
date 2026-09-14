#!/usr/bin/env python3
"""AST gate over house style conventions for Knot source (PIR-856).

Checks the rules in ``.claude/conventions/languages/python.md`` and
``docs/contributing/knot-design-rules.md`` that are mechanically detectable
from source text, over ``packages/*/pirn*/**/*.py`` — production source only.
``tests/``, ``.venv``/``venv``, ``__pycache__``, and any file named
``conftest.py`` are never scanned.

Rules
-----
1. ``multi_class_file`` — a file defines more than one top-level class.
2. ``module_level_function`` — a module-level ``def``, excluding
   ``__dunder__``-named functions (PEP 562 ``__getattr__`` and similar) and
   functions decorated with ``@KnotFactory.knot`` (``pirn.core.knot_factory.KnotFactory.knot``
   turns a plain function into a Knot factory — it is not "a function", it is
   a Knot definition written in function syntax). Every other function is a
   ``@staticmethod`` on a class, whatever its name; a replaced public name is
   deleted outright, never kept as a bare alias (``name = Class.method``).
3. ``nested_def_missing_override`` — a ``def``/``class`` nested inside another
   function (a closure or a function-local class) with no
   ``# design-decision-override`` comment (with or without the space) on one of the three lines immediately
   above it. A class nested inside a *class* (an ordinary method) is not
   "nested" in this sense and is never flagged.
4. ``gate_wrong_base`` — a class named ``*Gate`` (other than the framework
   primitive ``Gate`` itself) whose bases do not resolve to
   ``pirn.nodes.gate.gate.Gate``. Detected by base-name heuristic (``Gate``,
   or a dotted path ending in ``gate.Gate``), since full import resolution is
   out of scope for a source-only AST pass.
5. ``knot_init_impure`` — a Knot-like class (see "Knot-like" below) whose
   ``__init__`` contains any statement other than a leading docstring and a
   single ``super().__init__(...)`` call (knot-design-rules.md Rule 1: the
   constructor is a pure wiring layer).
6. ``knot_self_assignment`` — a ``self.<x> = ...`` assignment inside a
   Knot-like class's ``__init__`` where ``x`` does not start with
   ``_mutable_`` (Rule 4: no instance state for inputs).
7. ``knot_property`` — a ``@property`` or ``@functools.cached_property`` /
   ``@cached_property`` method on a Knot-like class (Rule 4/5: no property
   fields).
8. ``knot_process_kwargs_name`` — a Knot-like class's ``process()`` method
   whose ``**kwargs`` parameter is not named ``_`` (Rule 2: the catch-all is
   always ``**_: Any``). Only checked when a ``**kwargs`` parameter is
   present; a ``process()`` with none is a different violation this rule does
   not cover.
9. ``filename_mismatch`` — a file's module filename does not match
   ``snake_case(first public top-level class)`` under an alnum-lowercase
   comparison (strip everything but letters/digits, lowercase, compare) — so
   ``OpenAIClient`` in ``openai_client.py`` passes even though naive
   snake-casing of ``OpenAIClient`` would not round-trip. Files with no public
   (non-``_``-prefixed) top-level class are not checked.
10. ``deprecation_reference`` — a code reference (a name, not text in a
    string or comment) to ``DeprecationWarning`` or
    ``PendingDeprecationWarning``, or any ``_deprecated_since`` identifier or
    string. pirn is alpha: a replaced name is deleted, never deprecated.
11. ``module_alias_assignment`` — a module-scope assignment (including inside
    a module-level ``if``/``try``) whose value is a bare name or an attribute
    of a class or function defined in the module or a name imported into it:
    ``name = Class.method``, ``OldName = NewName``. Calls, subscripts
    (``JsonValue = dict[str, Any]``) and literals are not aliases.
12. ``reexport_module`` — a module whose only statements, after its
    docstring, ``from __future__`` imports and an ``__all__`` assignment, are
    imports: a module that exists only to re-export names from another
    module under an old path.
13. ``suppression_without_rule_or_reason`` — a ``# type: ignore`` or
    ``# pyright: ignore`` comment that does not name a rule in brackets and
    carry a reason comment on the same line
    (``# pyright: ignore[reportPrivateUsage]  # <reason>``).
14. ``file_level_pyright_directive`` — any ``# pyright: <setting>`` comment
    other than a per-line ``ignore``: the type-checking mode and rule
    overrides live in each package's ``[tool.pyright]`` only.
15. ``payload_alias_property`` — a ``@property`` on a ``Payload`` /
    ``PirnOpaqueValue`` subclass (by base name, followed through subclasses
    defined in the scanned roots) whose body is only
    ``return self.<metadata|data>[.<field>]`` (or the same over
    ``self._metadata`` / ``self._data``): a field-name alias for the canonical
    access. The canonical ``metadata``/``data`` accessors returning
    ``self._metadata``/``self._data`` are not aliases.

"Knot-like" (rules 5-8)
-----------------------
A class whose bases include one of ``Knot``, ``SubTapestry``, ``Source``,
``Sink``, ``Assembler``, ``Disassembler``, ``AgentPipeline``,
``AgentLoopPipeline``, ``LoopSubTapestry`` (by base name, not full import
resolution), OR whose own name ends in ``Knot`` or ``Pipeline``.

Framework root definitions (rules 5-8)
---------------------------------------
Rules 5-8 are the contract a *subclass* of the knot framework must honour.
They do not apply to the framework's own definition of a root it describes:
``Knot.__init__`` *is* the introspection that turns a subclass's constructor
kwargs into parents (it cannot itself be "a single ``super().__init__``
call"), ``Knot.knot_id``/``config``/``parents`` are the framework's read-only
accessors over its ``_mutable_`` state rather than a stored input exposed as a
field, and ``Aggregator.process(**inputs)`` is the variadic fan-in primitive
whose parents are named at construction, not in a signature. A class is a root
definition only when all three hold: it lives in ``pirn-core``; its name is one
of the framework vocabulary names this gate already keys on
(``_KNOT_BASE_NAMES`` or ``_FAN_IN_NODE_NAMES``); and its module filename is
that name (``pirn/core/knot.py`` for ``Knot``, ``pirn/nodes/aggregator.py`` for
``Aggregator``). A subclass of a root (``class MyKnot(Knot)``,
``class MyAggregator(Aggregator)``), a class that merely reuses a root name in
another file or package, and every other knot are still checked.

Core-lane allowlist (rules 5-7 only)
-------------------------------------
``pirn-core``'s ``pirn/nodes/*`` and ``pirn/core/parameter.py`` bootstrap
Knot's own internals (e.g. ``Parameter.__init__`` populates instance state
directly because it bypasses the standard parent/config introspection by
design) and are exempted from rules 5-7 here. This allowlist is scoped to the
PIR-856 core lane's own framework primitives, not a general escape hatch —
add to it only for another framework-internal class with a similar,
documented reason. Rule 8 (process ``**kwargs`` naming) still applies to
these files.

Failure semantics
-----------------
There is no baseline: any finding of any rule fails the gate. Every
violation is printed with its file, line and rule, followed by a per-package
count of each rule that fired.

CLI contract
------------
Positional arguments are Knot **import root directories**
(``packages/<dist>/<import_pkg>``, e.g. ``packages/pirn-core/pirn`` —
typically supplied via the shell glob ``packages/*/pirn*``). The package name
a finding is reported under is the *parent* directory's name (``pirn-core`` for
``packages/pirn-core/pirn``).

* ``0`` — no finding.
* ``1`` — at least one finding; every violation is listed.
* ``2`` — the invocation itself was unusable: a path that does not exist, is
  not a directory, or no arguments were given.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

# Scoped to the PIR-856 core lane's own framework primitives (see module
# docstring "Core-lane allowlist"). Keys are package names (the distribution
# directory under ``packages/``); values are path prefixes/files relative to the package's import
# root's parent (i.e. relative to ``packages/<dist>/``).
_KNOT_PURITY_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "pirn-core": ("pirn/nodes/", "pirn/core/parameter.py"),
}

_KNOT_BASE_NAMES = frozenset(
    {
        "Knot",
        "NestedRunKnot",
        "SubTapestry",
        "Source",
        "Sink",
        "Assembler",
        "Disassembler",
        "AgentPipeline",
        "AgentLoopPipeline",
        "LoopSubTapestry",
    }
)

_SKIP_DIR_NAMES = frozenset(
    {"tests", ".venv", "venv", "__pycache__", ".ruff_cache", ".tox"}
)

_RULES = (
    "multi_class_file",
    "module_level_function",
    "nested_def_missing_override",
    "gate_wrong_base",
    "knot_init_impure",
    "knot_self_assignment",
    "knot_property",
    "knot_process_kwargs_name",
    "filename_mismatch",
    "deprecation_reference",
    "module_alias_assignment",
    "reexport_module",
    "suppression_without_rule_or_reason",
    "file_level_pyright_directive",
    "payload_alias_property",
)

_DEPRECATION_NAMES = frozenset({"DeprecationWarning", "PendingDeprecationWarning"})
_DEPRECATED_SINCE = "_deprecated_since"

_SUPPRESSION = re.compile(r"#\s*(?:type|pyright)\s*:\s*ignore\b")
_SUPPRESSION_WITH_RULE_AND_REASON = re.compile(
    r"#\s*(?:type|pyright)\s*:\s*ignore\[[^\]\s][^\]]*\]\s*#\s*\S"
)
_PYRIGHT_DIRECTIVE = re.compile(r"#\s*pyright\s*:\s*(?!ignore\b)\S")

_PAYLOAD_ROOT_NAMES = frozenset({"Payload", "PirnOpaqueValue"})
_PAYLOAD_FIELDS = frozenset({"metadata", "data", "_metadata", "_data"})


class _Violation:
    """One rule hit, carrying enough context to print a useful line."""

    __slots__ = ("rule", "path", "lineno", "detail")

    def __init__(self, rule: str, path: Path, lineno: int, detail: str) -> None:
        self.rule = rule
        self.path = path
        self.lineno = lineno
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno}: [{self.rule}] {self.detail}"


def _dotted_name(node: ast.expr) -> str:
    """Reconstruct a dotted name from a ``Name``/``Attribute`` chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted_name(node.value)}.{node.attr}"
    return ""


def _base_names(bases: list[ast.expr]) -> list[str]:
    """The trailing identifier of each base (``pirn.core.knot.Knot`` -> ``Knot``)."""
    return [
        _dotted_name(base).rsplit(".", 1)[-1] for base in bases if _dotted_name(base)
    ]


def _is_knot_like(node: ast.ClassDef) -> bool:
    if set(_base_names(node.bases)) & _KNOT_BASE_NAMES:
        return True
    return node.name.endswith("Knot") or node.name.endswith("Pipeline")


def _is_gate_base(bases: list[ast.expr]) -> bool:
    for base in bases:
        dotted = _dotted_name(base)
        if (
            dotted == "Gate"
            or dotted.endswith(".gate.Gate")
            or dotted.endswith(".Gate")
        ):
            return True
    return False


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _decorator_names(decorators: list[ast.expr]) -> list[str]:
    names: list[str] = []
    for dec in decorators:
        target = dec.func if isinstance(dec, ast.Call) else dec
        dotted = _dotted_name(target)
        if dotted:
            names.append(dotted.rsplit(".", 1)[-1])
    return names


# ``ruff format`` rewrites ``#design-decision-override`` as ``# design-decision-override``,
# so both spellings are the same marker.
_OVERRIDE_MARKER = re.compile(r"#\s*design-decision-override")


def _has_override_comment(source_lines: list[str], lineno: int) -> bool:
    """Look for the design-decision-override marker on one of the 3 lines above ``lineno``."""
    start = max(0, lineno - 4)  # lineno is 1-based; check up to 3 lines above it
    end = lineno - 1
    for line in source_lines[start:end]:
        if _OVERRIDE_MARKER.search(line):
            return True
    return False


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _is_bare_super_init_call(stmt: ast.stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    call = stmt.value
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "__init__"
        and isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    )


def _find_method(
    class_node: ast.ClassDef, name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for stmt in class_node.body:
        if (
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and stmt.name == name
        ):
            return stmt
    return None


# Core fan-in / marker nodes a Knot may construct in ``__init__`` to wire a
# variadic or scalar input before handing it to ``super().__init__``.  Building
# one of these from the constructor's own arguments is wiring (Rule 1), not
# logic: the node participates in the graph with full lineage and the value
# still arrives in ``process()`` as a resolved argument (Rule 2).  See
# knot-design-rules.md, Rule 1, "Fan-in wiring".
_FAN_IN_NODE_NAMES = frozenset(
    {"Aggregator", "Reduce", "Parameter", "Map", "ZipMap", "DictMap"}
)


def _is_fan_in_wiring(body: list[ast.stmt]) -> bool:
    """True when ``body`` only builds fan-in nodes and then calls ``super().__init__``.

    Accepted statements, in order: zero or more simple assignments whose value
    is a dict literal / dict comprehension (numbering the parents) or a call to
    one of ``_FAN_IN_NODE_NAMES``, followed by exactly one bare
    ``super().__init__(...)`` call as the last statement.
    """
    if not body or not _is_bare_super_init_call(body[-1]):
        return False
    for stmt in body[:-1]:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            return False
        if not isinstance(stmt.targets[0], ast.Name):
            return False
        value = stmt.value
        if isinstance(value, (ast.Dict, ast.DictComp)):
            continue
        if isinstance(value, ast.Call):
            func = value.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else (func.attr if isinstance(func, ast.Attribute) else None)
            )
            if name in _FAN_IN_NODE_NAMES:
                continue
        return False
    return True


def _check_knot_init_purity(class_node: ast.ClassDef, path: Path) -> list[_Violation]:
    init = _find_method(class_node, "__init__")
    if init is None:
        return []
    body = init.body
    if body and _is_docstring_stmt(body[0]):
        body = body[1:]
    if len(body) == 1 and _is_bare_super_init_call(body[0]):
        return []
    if not body:
        return []
    if _is_fan_in_wiring(body):
        return []
    return [
        _Violation(
            "knot_init_impure",
            path,
            init.lineno,
            f"{class_node.name}.__init__ does more than call super().__init__(...)",
        )
    ]


def _check_knot_self_assignment(
    class_node: ast.ClassDef, path: Path
) -> list[_Violation]:
    init = _find_method(class_node, "__init__")
    if init is None:
        return []
    violations: list[_Violation] = []
    for node in ast.walk(init):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and not target.attr.startswith("_mutable_")
            ):
                violations.append(
                    _Violation(
                        "knot_self_assignment",
                        path,
                        node.lineno,
                        f"{class_node.name}.__init__ sets self.{target.attr} "
                        "(inputs must not be stored as instance state)",
                    )
                )
    return violations


def _check_knot_property(class_node: ast.ClassDef, path: Path) -> list[_Violation]:
    violations: list[_Violation] = []
    for stmt in class_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorator_names = _decorator_names(stmt.decorator_list)
        if "property" in decorator_names or "cached_property" in decorator_names:
            violations.append(
                _Violation(
                    "knot_property",
                    path,
                    stmt.lineno,
                    f"{class_node.name}.{stmt.name} is a @property/@cached_property on a Knot-like class",
                )
            )
    return violations


def _check_knot_process_kwargs(
    class_node: ast.ClassDef, path: Path
) -> list[_Violation]:
    process = _find_method(class_node, "process")
    if process is None or process.args.kwarg is None:
        return []
    if process.args.kwarg.arg == "_":
        return []
    return [
        _Violation(
            "knot_process_kwargs_name",
            path,
            process.lineno,
            f"{class_node.name}.process(**{process.args.kwarg.arg}) — catch-all must be named **_",
        )
    ]


def _is_exempt_from_knot_purity(package: str, relative_posix: str) -> bool:
    for prefix in _KNOT_PURITY_ALLOWLIST.get(package, ()):
        if relative_posix == prefix or relative_posix.startswith(prefix):
            return True
    return False


def _check_nested_defs(
    tree: ast.Module, source_lines: list[str], path: Path
) -> list[_Violation]:
    violations: list[_Violation] = []

    def _visit(node: ast.AST, enclosing_function_depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            is_def = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
            is_function = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            if (
                is_def
                and enclosing_function_depth > 0
                and not _has_override_comment(source_lines, child.lineno)
            ):
                kind = "function" if is_function else "class"
                violations.append(
                    _Violation(
                        "nested_def_missing_override",
                        path,
                        child.lineno,
                        f"nested {kind} {child.name!r} has no #design-decision-override comment",
                    )
                )
            next_depth = (
                enclosing_function_depth + 1
                if is_function
                else enclosing_function_depth
            )
            _visit(child, next_depth)

    _visit(tree, 0)
    return violations


def _check_module_level_functions(tree: ast.Module, path: Path) -> list[_Violation]:
    violations: list[_Violation] = []
    for stmt in tree.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_dunder(stmt.name):
            continue
        if "knot" in _decorator_names(stmt.decorator_list):
            continue
        violations.append(
            _Violation(
                "module_level_function",
                path,
                stmt.lineno,
                f"module-level function {stmt.name!r} — use a @staticmethod inside a class",
            )
        )
    return violations


def _check_gate_naming(tree: ast.Module, path: Path) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == "Gate" or not node.name.endswith("Gate"):
            continue
        if not _is_gate_base(node.bases):
            violations.append(
                _Violation(
                    "gate_wrong_base",
                    path,
                    node.lineno,
                    f"class {node.name!r} ends in 'Gate' but does not extend pirn.nodes.gate.gate.Gate",
                )
            )
    return violations


def _check_multi_class_file(tree: ast.Module, path: Path) -> list[_Violation]:
    top_level_classes = [stmt for stmt in tree.body if isinstance(stmt, ast.ClassDef)]
    if len(top_level_classes) > 1:
        return [
            _Violation(
                "multi_class_file",
                path,
                top_level_classes[1].lineno,
                f"{len(top_level_classes)} top-level classes in one file — one class per file",
            )
        ]
    return []


def _check_filename(tree: ast.Module, path: Path) -> list[_Violation]:
    public_classes = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, ast.ClassDef) and not stmt.name.startswith("_")
    ]
    if not public_classes:
        return []
    first = public_classes[0]

    def _alnum_lower(text: str) -> str:
        return "".join(ch.lower() for ch in text if ch.isalnum())

    stem_norm = _alnum_lower(path.stem)
    class_norm = _alnum_lower(first.name)
    if stem_norm != class_norm:
        return [
            _Violation(
                "filename_mismatch",
                path,
                first.lineno,
                f"filename {path.stem!r} does not match first public class {first.name!r}",
            )
        ]
    return []


def _is_framework_root_definition(
    class_node: ast.ClassDef, package: str, relative_posix: str
) -> bool:
    """True for pirn-core's own definition of a framework root (see module docstring).

    ``Knot`` in ``pirn/core/knot.py``, ``Aggregator`` in
    ``pirn/nodes/aggregator.py``, ... — never a subclass of one, and never a
    same-named class in another file or package.
    """
    if package != "pirn-core":
        return False
    if class_node.name not in _KNOT_BASE_NAMES | _FAN_IN_NODE_NAMES:
        return False
    if class_node.name in _base_names(class_node.bases):
        return False
    stem = Path(relative_posix).stem
    return _alnum_lower(stem) == _alnum_lower(class_node.name)


def _alnum_lower(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _check_knot_purity_rules(
    tree: ast.Module, path: Path, package: str, relative_posix: str
) -> list[_Violation]:
    violations: list[_Violation] = []
    exempt = _is_exempt_from_knot_purity(package, relative_posix)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_knot_like(node):
            continue
        if _is_framework_root_definition(node, package, relative_posix):
            continue
        if not exempt:
            violations.extend(_check_knot_init_purity(node, path))
            violations.extend(_check_knot_self_assignment(node, path))
            violations.extend(_check_knot_property(node, path))
        violations.extend(_check_knot_process_kwargs(node, path))
    return violations


def _check_deprecation_references(
    tree: ast.Module, source: str, path: Path
) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name in _DEPRECATION_NAMES:
            violations.append(
                _Violation(
                    "deprecation_reference",
                    path,
                    node.lineno,
                    f"{name} referenced — pirn is alpha: delete the name, never deprecate it",
                )
            )
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _DEPRECATED_SINCE in line:
            violations.append(
                _Violation(
                    "deprecation_reference",
                    path,
                    lineno,
                    f"{_DEPRECATED_SINCE} marker — pirn is alpha: delete the name, never deprecate it",
                )
            )
    return violations


def _module_scope_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Module-level statements, descending into module-level ``if``/``try`` blocks."""
    statements: list[ast.stmt] = []
    for stmt in body:
        statements.append(stmt)
        if isinstance(stmt, ast.If):
            statements.extend(_module_scope_statements(stmt.body))
            statements.extend(_module_scope_statements(stmt.orelse))
        elif isinstance(stmt, ast.Try):
            statements.extend(_module_scope_statements(stmt.body))
            for handler in stmt.handlers:
                statements.extend(_module_scope_statements(handler.body))
            statements.extend(_module_scope_statements(stmt.orelse))
            statements.extend(_module_scope_statements(stmt.finalbody))
    return statements


def _root_name(node: ast.expr) -> str | None:
    """``a`` for ``a``, ``a.b`` or ``a.b.c``; ``None`` for anything else."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _check_module_alias_assignments(tree: ast.Module, path: Path) -> list[_Violation]:
    statements = _module_scope_statements(tree.body)
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
    violations: list[_Violation] = []
    for stmt in statements:
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
            value: ast.expr | None = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
            value = stmt.value
        else:
            continue
        if value is None or not isinstance(value, (ast.Name, ast.Attribute)):
            continue
        root = _root_name(value)
        if root is None or root not in bound:
            continue
        names = [_dotted_name(target) or "<target>" for target in targets]
        violations.append(
            _Violation(
                "module_alias_assignment",
                path,
                stmt.lineno,
                f"module-scope alias {', '.join(names)} = {_dotted_name(value)} — "
                "delete the old name and move callers to the real one",
            )
        )
    return violations


def _is_dunder_all_assignment(stmt: ast.stmt) -> bool:
    targets: list[ast.expr] = []
    if isinstance(stmt, ast.Assign):
        targets = stmt.targets
    elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        targets = [stmt.target]
    return any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets)


def _check_reexport_module(tree: ast.Module, path: Path) -> list[_Violation]:
    body = tree.body
    if body and _is_docstring_stmt(body[0]):
        body = body[1:]
    remaining = [
        stmt
        for stmt in body
        if not (isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__")
        and not _is_dunder_all_assignment(stmt)
    ]
    if not remaining or not all(
        isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in remaining
    ):
        return []
    return [
        _Violation(
            "reexport_module",
            path,
            remaining[0].lineno,
            "module only re-exports imported names — delete it and import from the real module",
        )
    ]


def _comments(source: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comments.append((token.start[0], token.string))
    except (tokenize.TokenError, SyntaxError):  # pragma: no cover - ast.parse already succeeded
        pass
    return comments


def _check_suppression_comments(source: str, path: Path) -> list[_Violation]:
    violations: list[_Violation] = []
    for lineno, comment in _comments(source):
        if _PYRIGHT_DIRECTIVE.search(comment):
            violations.append(
                _Violation(
                    "file_level_pyright_directive",
                    path,
                    lineno,
                    f"{comment.strip()!r} — pyright settings live in [tool.pyright], not in a file",
                )
            )
        if _SUPPRESSION.search(comment) and not _SUPPRESSION_WITH_RULE_AND_REASON.search(
            comment
        ):
            violations.append(
                _Violation(
                    "suppression_without_rule_or_reason",
                    path,
                    lineno,
                    f"{comment.strip()!r} — a suppression names its rule in brackets and "
                    "carries a '# reason' on the same line",
                )
            )
    return violations


def _subscript_base(base: ast.expr) -> ast.expr:
    return base.value if isinstance(base, ast.Subscript) else base


def _class_base_names(node: ast.ClassDef) -> list[str]:
    return _base_names([_subscript_base(base) for base in node.bases])


def payload_class_names(import_roots: list[Path]) -> frozenset[str]:
    """Every class name that derives, by base name, from ``Payload``/``PirnOpaqueValue``."""
    bases_by_class: dict[str, set[str]] = {}
    for import_root in import_roots:
        for file_path in _iter_source_files(import_root):
            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensive
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases_by_class.setdefault(node.name, set()).update(
                        _class_base_names(node)
                    )
    names = set(_PAYLOAD_ROOT_NAMES)
    changed = True
    while changed:
        changed = False
        for class_name, bases in bases_by_class.items():
            if class_name not in names and bases & names:
                names.add(class_name)
                changed = True
    return frozenset(names)


def _is_payload_field_access(node: ast.expr, property_name: str) -> bool:
    """``self.<metadata|data|_metadata|_data>`` optionally followed by one ``.field`` / ``[key]``."""
    inner = node
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
        inner = node.value
    elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        inner = node.value
    if not (
        isinstance(inner, ast.Attribute)
        and isinstance(inner.value, ast.Name)
        and inner.value.id == "self"
        and inner.attr in _PAYLOAD_FIELDS
    ):
        return False
    if inner is node and inner.attr.lstrip("_") == property_name:
        return False  # the canonical ``metadata``/``data`` accessor itself
    return True


def _check_payload_alias_properties(
    tree: ast.Module, path: Path, payload_names: frozenset[str]
) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not set(_class_base_names(node)) & payload_names:
            continue
        for stmt in node.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "property" not in _decorator_names(stmt.decorator_list):
                continue
            body = stmt.body
            if body and _is_docstring_stmt(body[0]):
                body = body[1:]
            if (
                len(body) == 1
                and isinstance(body[0], ast.Return)
                and body[0].value is not None
                and _is_payload_field_access(body[0].value, stmt.name)
            ):
                violations.append(
                    _Violation(
                        "payload_alias_property",
                        path,
                        stmt.lineno,
                        f"{node.name}.{stmt.name} only returns "
                        f"{ast.unparse(body[0].value)} — delete the alias and read the "
                        "canonical field",
                    )
                )
    return violations


def check_file(
    path: Path,
    package: str,
    relative_posix: str,
    payload_names: frozenset[str] = _PAYLOAD_ROOT_NAMES,
) -> list[_Violation]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        return [_Violation("parse_error", path, 1, str(exc))]

    source_lines = source.splitlines()
    violations: list[_Violation] = []
    violations.extend(_check_multi_class_file(tree, path))
    violations.extend(_check_module_level_functions(tree, path))
    violations.extend(_check_nested_defs(tree, source_lines, path))
    violations.extend(_check_gate_naming(tree, path))
    violations.extend(_check_knot_purity_rules(tree, path, package, relative_posix))
    violations.extend(_check_filename(tree, path))
    violations.extend(_check_deprecation_references(tree, source, path))
    violations.extend(_check_module_alias_assignments(tree, path))
    violations.extend(_check_reexport_module(tree, path))
    violations.extend(_check_suppression_comments(source, path))
    violations.extend(_check_payload_alias_properties(tree, path, payload_names))
    return violations


def _iter_source_files(import_root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in sorted(import_root.rglob("*.py")):
        if candidate.name == "conftest.py":
            continue
        if any(part in _SKIP_DIR_NAMES for part in candidate.parts):
            continue
        files.append(candidate)
    return files


def collect_counts(
    import_roots: list[Path],
) -> tuple[dict[str, dict[str, int]], list[_Violation]]:
    """Scan every package's import root; return (counts, all violations)."""
    counts: dict[str, dict[str, int]] = {}
    all_violations: list[_Violation] = []
    payload_names = payload_class_names(import_roots)
    for import_root in import_roots:
        package = import_root.parent.name
        package_root = import_root.parent
        rule_counts = counts.setdefault(package, dict.fromkeys(_RULES, 0))
        for file_path in _iter_source_files(import_root):
            relative_posix = file_path.relative_to(package_root).as_posix()
            violations = check_file(file_path, package, relative_posix, payload_names)
            for violation in violations:
                if violation.rule in rule_counts:
                    rule_counts[violation.rule] += 1
                all_violations.append(violation)
    return counts, all_violations


def resolve_import_roots(args: list[str]) -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    errors: list[str] = []
    for arg in args:
        path = Path(arg)
        if not path.exists():
            errors.append(f"{arg}: no such file or directory")
        elif not path.is_dir():
            errors.append(f"{arg}: not a directory")
        else:
            roots.append(path)
    return roots, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AST gate over house style conventions for Knot source (PIR-856)."
    )
    parser.add_argument(
        "import_roots",
        nargs="*",
        help="Knot import root directories, e.g. packages/*/pirn*",
    )
    args = parser.parse_args(argv)

    if not args.import_roots:
        print("usage: check_conventions.py <import-root>...", file=sys.stderr)
        return 2

    import_roots, errors = resolve_import_roots(args.import_roots)
    for err in errors:
        print(err, file=sys.stderr)
    if errors:
        return 2

    counts, violations = collect_counts(import_roots)
    for violation in violations:
        print(violation)
    for package, rule_counts in sorted(counts.items()):
        for rule, count in rule_counts.items():
            if count:
                print(f"{package}: {rule} {count}")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
