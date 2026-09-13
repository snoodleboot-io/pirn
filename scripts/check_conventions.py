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
   ``__dunder__``-named functions (PEP 562 ``__getattr__`` shims and similar)
   and functions decorated with ``@knot`` (``pirn.core.knot_factory.knot``
   turns a plain function into a Knot factory — it is not "a function", it is
   a Knot definition written in function syntax).
3. ``nested_def_missing_override`` — a ``def``/``class`` nested inside another
   function (a closure or a function-local class) with no
   ``#design-decision-override`` comment on one of the three lines immediately
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

"Knot-like" (rules 5-8)
-----------------------
A class whose bases include one of ``Knot``, ``SubTapestry``, ``Source``,
``Sink``, ``Assembler``, ``Disassembler``, ``AgentPipeline``,
``AgentLoopPipeline``, ``LoopSubTapestry`` (by base name, not full import
resolution), OR whose own name ends in ``Knot`` or ``Pipeline``.

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

Ratchet semantics
------------------
Counts are compared against ``scripts/conventions_baseline.json``
(``{package: {rule: count}}``, package keyed by the distribution directory
name under ``packages/``, e.g. ``"pirn-core"``). The gate FAILS only when a
package/rule count *exceeds* its baseline value; a count at or below baseline
passes, and a count strictly below baseline prints a "baseline can be
lowered" note (so a fix is visible without requiring one). ``--write-baseline``
regenerates the file from the current tree unconditionally and always exits 0.

The baseline in this repository was generated from the PIR-856 docs-ci
lane's own branch. Other lanes are concurrently lowering several of these
counts in the same remediation effort; the integrator is expected to run
``--write-baseline`` again after every lane merges so the ratchet reflects
the post-merge state rather than freezing this lane's snapshot.

CLI contract
------------
Positional arguments are Knot **import root directories**
(``packages/<dist>/<import_pkg>``, e.g. ``packages/pirn-core/pirn`` —
typically supplied via the shell glob ``packages/*/pirn*``). The package name
used in the baseline is the *parent* directory's name (``pirn-core`` for
``packages/pirn-core/pirn``).

* ``0`` — no count exceeds its baseline.
* ``1`` — at least one count exceeds its baseline; violations are listed.
* ``2`` — the invocation itself was unusable: a path that does not exist, is
  not a directory, or no arguments were given.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# Scoped to the PIR-856 core lane's own framework primitives (see module
# docstring "Core-lane allowlist"). Keys are package names as used in the
# baseline; values are path prefixes/files relative to the package's import
# root's parent (i.e. relative to ``packages/<dist>/``).
_KNOT_PURITY_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "pirn-core": ("pirn/nodes/", "pirn/core/parameter.py"),
}

_KNOT_BASE_NAMES = frozenset(
    {
        "Knot",
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

_SKIP_DIR_NAMES = frozenset({"tests", ".venv", "venv", "__pycache__", ".ruff_cache", ".tox"})

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
)


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
    return [_dotted_name(base).rsplit(".", 1)[-1] for base in bases if _dotted_name(base)]


def _is_knot_like(node: ast.ClassDef) -> bool:
    if set(_base_names(node.bases)) & _KNOT_BASE_NAMES:
        return True
    return node.name.endswith("Knot") or node.name.endswith("Pipeline")


def _is_gate_base(bases: list[ast.expr]) -> bool:
    for base in bases:
        dotted = _dotted_name(base)
        if dotted == "Gate" or dotted.endswith(".gate.Gate") or dotted.endswith(".Gate"):
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


def _has_override_comment(source_lines: list[str], lineno: int) -> bool:
    """Look for ``#design-decision-override`` on one of the 3 lines above ``lineno``."""
    start = max(0, lineno - 4)  # lineno is 1-based; check up to 3 lines above it
    end = lineno - 1
    for line in source_lines[start:end]:
        if "#design-decision-override" in line:
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
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
            return stmt
    return None


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
    return [
        _Violation(
            "knot_init_impure",
            path,
            init.lineno,
            f"{class_node.name}.__init__ does more than call super().__init__(...)",
        )
    ]


def _check_knot_self_assignment(class_node: ast.ClassDef, path: Path) -> list[_Violation]:
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


def _check_knot_process_kwargs(class_node: ast.ClassDef, path: Path) -> list[_Violation]:
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


def _check_nested_defs(tree: ast.Module, source_lines: list[str], path: Path) -> list[_Violation]:
    violations: list[_Violation] = []

    def _visit(node: ast.AST, enclosing_function_depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            is_def = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
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
            next_depth = enclosing_function_depth + 1 if is_function else enclosing_function_depth
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


def _check_knot_purity_rules(
    tree: ast.Module, path: Path, package: str, relative_posix: str
) -> list[_Violation]:
    violations: list[_Violation] = []
    exempt = _is_exempt_from_knot_purity(package, relative_posix)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_knot_like(node):
            continue
        if not exempt:
            violations.extend(_check_knot_init_purity(node, path))
            violations.extend(_check_knot_self_assignment(node, path))
            violations.extend(_check_knot_property(node, path))
        violations.extend(_check_knot_process_kwargs(node, path))
    return violations


def check_file(path: Path, package: str, relative_posix: str) -> list[_Violation]:
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
    for import_root in import_roots:
        package = import_root.parent.name
        package_root = import_root.parent
        rule_counts = counts.setdefault(package, dict.fromkeys(_RULES, 0))
        for file_path in _iter_source_files(import_root):
            relative_posix = file_path.relative_to(package_root).as_posix()
            violations = check_file(file_path, package, relative_posix)
            for violation in violations:
                if violation.rule in rule_counts:
                    rule_counts[violation.rule] += 1
                all_violations.append(violation)
    return counts, all_violations


def _load_baseline(baseline_path: Path) -> dict[str, dict[str, int]]:
    if not baseline_path.exists():
        return {}
    with baseline_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_baseline(baseline_path: Path, counts: dict[str, dict[str, int]]) -> None:
    with baseline_path.open("w", encoding="utf-8") as fh:
        json.dump(counts, fh, indent=2, sort_keys=True)
        fh.write("\n")


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
        "import_roots", nargs="*", help="Knot import root directories, e.g. packages/*/pirn*"
    )
    parser.add_argument(
        "--baseline",
        default="scripts/conventions_baseline.json",
        help="Path to the ratchet baseline JSON (default: scripts/conventions_baseline.json)",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Regenerate the baseline file from the current tree and exit 0.",
    )
    args = parser.parse_args(argv)

    if not args.import_roots:
        print(
            "usage: check_conventions.py <import-root>... [--baseline PATH] [--write-baseline]",
            file=sys.stderr,
        )
        return 2

    import_roots, errors = resolve_import_roots(args.import_roots)
    for err in errors:
        print(err, file=sys.stderr)
    if errors:
        return 2

    counts, violations = collect_counts(import_roots)
    baseline_path = Path(args.baseline)

    if args.write_baseline:
        _write_baseline(baseline_path, counts)
        print(f"wrote baseline for {len(counts)} package(s) to {baseline_path}")
        return 0

    baseline = _load_baseline(baseline_path)
    failed = False
    notes: list[str] = []
    for package, rule_counts in sorted(counts.items()):
        baseline_for_package = baseline.get(package, {})
        for rule, count in rule_counts.items():
            baseline_count = baseline_for_package.get(rule, 0)
            if count > baseline_count:
                failed = True
                notes.append(f"{package}: {rule} count {count} exceeds baseline {baseline_count}")
            elif count < baseline_count:
                notes.append(
                    f"baseline can be lowered: {package}: {rule} is {count}, baseline says {baseline_count}"
                )

    for violation in violations:
        print(violation)
    for note in notes:
        print(note)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
