"""Knot design-rule violation scanner.

Reads every Knot source file in full, checks all rules from
docs/contributing/knot-design-rules.md, and writes a markdown audit
table to planning/current/ in the same format as knot-violations-audit.md.

Rules:
  R1   __init__ body is ONLY super().__init__(...)
  R2   Every __init__ param (except _config/**kwargs) appears in process()
  R3   No raise statements in __init__
  R4   No self._x assignments storing inputs in __init__
  R5   No @property exposing inputs or derived strings
  R6   Opaque resources use a dedicated vending Knot (heuristic)
  R7   __init__ params annotated as Knot type or Knot|scalar, not plain scalar
  R8   SubTapestry.process() calls self._run_inner()
  R9   Quality assessment Knots returning QualityReport use *Check, not *Gate
  R10-Algo  Module docstring contains Algorithm: section
  R10-Math  Module docstring contains Math: section
  R10-Refs  Module docstring contains References: section
  Sec  hashlib.md5() includes usedforsecurity=False
  Step11  Corresponding unit test calls process() directly with plain values
  Step12  All applicable rules pass AND Step11 passes

Usage:
    uv run python scripts/audit_knots.py [--path pirn/domains] [--output planning/current]

Exit code 0 when zero violations; 1 otherwise.
"""

from __future__ import annotations

import ast
import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

Cell = Literal["[x]", "[ ]", "N/A"]

PLAIN_SCALAR_TYPES = frozenset({
    "str", "int", "float", "bool", "bytes",
    "dict", "list", "tuple", "set",
    "Path", "timedelta", "datetime", "date",
    "Any",
})

KNOT_BASES = frozenset({"Knot", "SubTapestry", "Source", "Sink"})

RESOURCE_ATTRS = frozenset({
    "connection", "pool", "session", "client", "cursor",
    "conn", "engine", "channel", "socket", "backend",
    "context", "driver", "broker",
})

# Param names in __init__ that suggest an opaque resource input
RESOURCE_PARAM_WORDS = frozenset({
    "connection", "pool", "session", "client", "cursor",
    "conn", "engine", "channel", "socket", "backend",
    "context", "driver", "broker",
})

COLUMNS = [
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    "R9", "R10-Algo", "R10-Math", "R10-Refs", "Sec", "Step11", "Step12",
]


@dataclass
class RuleResult:
    status: Cell = "N/A"
    lineno: int = 0
    detail: str = ""


@dataclass
class KnotResult:
    class_name: str
    lineno: int
    rules: dict[str, RuleResult] = field(default_factory=dict)

    def set(self, rule: str, status: Cell, lineno: int = 0, detail: str = "") -> None:
        self.rules[rule] = RuleResult(status=status, lineno=lineno, detail=detail)

    def has_violation(self) -> bool:
        return any(r.status == "[ ]" for r in self.rules.values())


@dataclass
class FileResult:
    path: Path
    knots: list[KnotResult] = field(default_factory=list)

    def has_violation(self) -> bool:
        return any(k.has_violation() for k in self.knots)

    def all_violations(self) -> list[tuple[str, str, int, str]]:
        out = []
        for k in self.knots:
            for rule, r in k.rules.items():
                if r.status == "[ ]":
                    out.append((k.class_name, rule, r.lineno, r.detail))
        return out


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _is_knot_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = (
            base.id if isinstance(base, ast.Name)
            else base.attr if isinstance(base, ast.Attribute)
            else None
        )
        if name in KNOT_BASES:
            return True
    return False


def _inherits(node: ast.ClassDef, name: str) -> bool:
    for base in node.bases:
        b = (
            base.id if isinstance(base, ast.Name)
            else base.attr if isinstance(base, ast.Attribute)
            else None
        )
        if b == name:
            return True
    return False


def _get_init_and_process(
    cls: ast.ClassDef,
) -> tuple[ast.FunctionDef | None, ast.FunctionDef | ast.AsyncFunctionDef | None]:
    init_node = None
    process_node = None
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name == "__init__":
                init_node = item  # type: ignore[assignment]
            elif item.name == "process":
                process_node = item
    return init_node, process_node


def _init_params(init_node: ast.FunctionDef) -> list[str]:
    """Non-self params from __init__, excluding _config and **kwargs."""
    params = []
    for arg in init_node.args.args:
        if arg.arg not in ("self", "_config"):
            params.append(arg.arg)
    for arg in init_node.args.kwonlyargs:
        if arg.arg not in ("_config",):
            params.append(arg.arg)
    return params


def _process_params(process_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    params = []
    for arg in process_node.args.args:
        if arg.arg != "self":
            params.append(arg.arg)
    params += [a.arg for a in (process_node.args.kwonlyargs or [])]
    return params


def _is_super_init_call(stmt: ast.stmt) -> bool:
    """True if stmt is `super().__init__(...)` expression."""
    if not isinstance(stmt, ast.Expr):
        return False
    call = stmt.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "__init__"
        and isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    )


def _is_plain_return(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Return) and stmt.value is None


def _is_plain_scalar_annotation(ann: ast.expr | None) -> bool:
    """Return True when annotation is a plain value type, not Knot-typed."""
    if ann is None:
        return False
    if isinstance(ann, ast.Constant) and ann.value is None:
        return False
    if isinstance(ann, ast.Name):
        return ann.id in PLAIN_SCALAR_TYPES
    if isinstance(ann, ast.Attribute):
        return ann.attr in PLAIN_SCALAR_TYPES
    if isinstance(ann, ast.Subscript):
        if isinstance(ann.value, ast.Name) and ann.value.id in (
            "Optional", "List", "Dict", "Tuple", "Set", "Sequence", "Iterable"
        ):
            return True
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        # Knot | scalar — presence of | means it's intentional union; compliant
        return False
    return False


def _has_md5(node: ast.ClassDef) -> bool:
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Call):
            func = stmt.func
            if (isinstance(func, ast.Attribute) and func.attr == "md5") or (
                isinstance(func, ast.Name) and func.id == "md5"
            ):
                return True
    return False


def _md5_missing_flag(node: ast.ClassDef) -> list[int]:
    lines = []
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Call):
            func = stmt.func
            if (isinstance(func, ast.Attribute) and func.attr == "md5") or (
                isinstance(func, ast.Name) and func.id == "md5"
            ):
                kwarg_names = [kw.arg for kw in stmt.keywords]
                if "usedforsecurity" not in kwarg_names:
                    lines.append(getattr(stmt, "lineno", 0))
    return lines


def _has_run_inner(process_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(process_node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "_run_inner":
                return True
    return False


def _module_docstring(tree: ast.Module) -> str:
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        return tree.body[0].value.value
    return ""


def _stores_resource_in_init(init_node: ast.FunctionDef) -> list[tuple[str, int]]:
    """Find self._<resource_word> assignments in __init__."""
    found = []
    for stmt in ast.walk(init_node):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr.startswith("_")
                    and not target.attr.startswith("__")
                    and not target.attr.startswith("_mutable_")
                ):
                    attr = target.attr.lstrip("_")
                    for word in RESOURCE_ATTRS:
                        if word in attr:
                            found.append((target.attr, stmt.lineno))
    return found


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------

def _check_r1(cls: ast.ClassDef, init_node: ast.FunctionDef) -> RuleResult:
    """__init__ body is ONLY super().__init__(...)."""
    for stmt in init_node.body:
        if _is_super_init_call(stmt):
            continue
        if _is_plain_return(stmt):
            continue
        if isinstance(stmt, ast.Pass):
            continue
        return RuleResult("[ ]", getattr(stmt, "lineno", init_node.lineno),
                          "extra statement in __init__")
    return RuleResult("[x]", init_node.lineno)


def _check_r2(
    cls: ast.ClassDef,
    init_node: ast.FunctionDef,
    process_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> RuleResult:
    """Every __init__ param appears by same name in process()."""
    params = _init_params(init_node)
    params = [p for p in params if not p.startswith("_")]
    if not params:
        return RuleResult("[x]", init_node.lineno)
    if process_node is None:
        return RuleResult("[ ]", init_node.lineno, "no process() method found")
    proc_params = set(_process_params(process_node))
    missing = [p for p in params if p not in proc_params]
    if missing:
        return RuleResult("[ ]", process_node.lineno,
                          f"missing in process(): {missing}")
    return RuleResult("[x]", init_node.lineno)


def _check_r3(cls: ast.ClassDef, init_node: ast.FunctionDef) -> RuleResult:
    """No raise in __init__."""
    for stmt in ast.walk(init_node):
        if isinstance(stmt, ast.Raise):
            return RuleResult("[ ]", getattr(stmt, "lineno", init_node.lineno),
                              "raise in __init__")
    return RuleResult("[x]", init_node.lineno)


def _check_r4(cls: ast.ClassDef, init_node: ast.FunctionDef) -> RuleResult:
    """No self._x assignments in __init__."""
    for stmt in ast.walk(init_node):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr.startswith("_")
                    and not target.attr.startswith("__")
                    and not target.attr.startswith("_mutable_")
                ):
                    return RuleResult("[ ]", stmt.lineno,
                                      f"stores self.{target.attr}")
        if isinstance(stmt, ast.AnnAssign):
            target = stmt.target
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr.startswith("_")
                and not target.attr.startswith("__")
                and not target.attr.startswith("_mutable_")
            ):
                return RuleResult("[ ]", getattr(stmt, "lineno", init_node.lineno),
                                  f"stores self.{target.attr}")
    return RuleResult("[x]", init_node.lineno)


def _check_r5(cls: ast.ClassDef) -> RuleResult:
    """No @property fields on the class."""
    for item in cls.body:
        if isinstance(item, ast.FunctionDef):
            for dec in item.decorator_list:
                if (isinstance(dec, ast.Name) and dec.id == "property") or (
                    isinstance(dec, ast.Attribute) and dec.attr == "property"
                ):
                    return RuleResult("[ ]", item.lineno,
                                      f"@property '{item.name}'")
    return RuleResult("[x]", cls.lineno)


def _check_r6(
    cls: ast.ClassDef, init_node: ast.FunctionDef | None, source: str
) -> RuleResult:
    """Heuristic: opaque resource params in __init__ must come via a vending Knot."""
    if init_node is None:
        return RuleResult("N/A", cls.lineno)

    # Check __init__ params for resource-like names
    suspicious_params: list[tuple[str, ast.expr | None, int]] = []
    all_args = init_node.args.args + init_node.args.kwonlyargs
    for arg in all_args:
        if arg.arg in ("self", "_config"):
            continue
        name_lower = arg.arg.lower()
        for word in RESOURCE_PARAM_WORDS:
            if word in name_lower:
                suspicious_params.append((arg.arg, arg.annotation, arg.col_offset))
                break

    # Also check for resource attrs stored in __init__ body
    resource_attrs = _stores_resource_in_init(init_node)

    if not suspicious_params and not resource_attrs:
        return RuleResult("N/A", cls.lineno)

    # Dedicated vending Knots ending in 'Knot' are allowed to hold resources
    if cls.name.endswith("Knot"):
        return RuleResult("[x]", cls.lineno)

    # Check if suspicious params are Knot-typed (compliant) or plain types (violation)
    for param_name, ann, col in suspicious_params:
        if ann is None:
            continue
        # Knot-typed: name ends in Knot/Source/Sink, or is a BinOp (Knot | T union)
        if isinstance(ann, ast.Name) and (
            ann.id.endswith("Knot")
            or ann.id in KNOT_BASES
        ):
            continue
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            continue
        # Plain type — resource passed directly, not via vending knot
        return RuleResult(
            "[ ]", init_node.lineno,
            f"param '{param_name}' looks like an opaque resource not typed as Knot",
        )

    if resource_attrs:
        attr_names = [a for a, _ in resource_attrs]
        return RuleResult("[ ]", resource_attrs[0][1],
                          f"stores resource attr(s) in non-vending class: {attr_names}")

    return RuleResult("[x]", cls.lineno)


def _check_r7(
    cls: ast.ClassDef, init_node: ast.FunctionDef
) -> RuleResult:
    """__init__ params must use Knot types or Knot|scalar, not bare scalars."""
    violations = []
    all_args = init_node.args.args + init_node.args.kwonlyargs
    for arg in all_args:
        if arg.arg in ("self", "_config"):
            continue
        ann = arg.annotation
        if _is_plain_scalar_annotation(ann):
            violations.append((arg.arg, arg.col_offset))
    if violations:
        lineno = getattr(init_node.args.args[0] if init_node.args.args else init_node, "lineno", init_node.lineno)
        names = [v[0] for v in violations]
        return RuleResult("[ ]", init_node.lineno,
                          f"plain scalar params (not Knot|T): {names}")
    return RuleResult("[x]", init_node.lineno)


def _check_r8(
    cls: ast.ClassDef,
    process_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> RuleResult:
    """SubTapestry.process() must call self._run_inner()."""
    if not _inherits(cls, "SubTapestry"):
        return RuleResult("N/A", cls.lineno)
    if process_node is None:
        return RuleResult("[ ]", cls.lineno, "no process() found on SubTapestry")
    if _has_run_inner(process_node):
        return RuleResult("[x]", process_node.lineno)
    return RuleResult("[ ]", process_node.lineno,
                      "SubTapestry.process() never calls self._run_inner()")


def _check_r9(cls: ast.ClassDef, source: str) -> RuleResult:
    """Quality Knots returning QualityReport must use *Check not *Gate."""
    is_quality = "QualityReport" in source or "quality" in str(cls.name).lower()
    if not is_quality:
        return RuleResult("N/A", cls.lineno)
    if cls.name.endswith("Gate"):
        return RuleResult("[ ]", cls.lineno,
                          f"use '*Check' suffix, not '*Gate'")
    return RuleResult("[x]", cls.lineno)


def _check_r10(docstring: str) -> tuple[RuleResult, RuleResult, RuleResult]:
    """R10-Algo, R10-Math, R10-Refs checks against module docstring."""
    has_algo = "Algorithm:" in docstring or "Algorithm\n" in docstring
    has_math = "Math:" in docstring or "Math\n" in docstring
    has_refs = "References:" in docstring or "References\n" in docstring

    # R10-Math is always required — N/A must be confirmed by a human reading
    # process() and adding a Math: section or an explicit note.
    # R10-Refs uses a heuristic: N/A when no external library/algorithm keywords appear.
    refs_na = not any(
        kw in docstring.lower()
        for kw in ("based on", "see also", "from the", "reference",
                   "algorithm", "paper", "specification", "rfc", "iso",
                   "datafusion", "apache", "polars", "dask", "ibis", "spark")
    )

    algo_result = RuleResult("[x]" if has_algo else "[ ]")
    math_result = RuleResult("[x]" if has_math else "[ ]")
    refs_result = RuleResult("N/A" if refs_na else ("[x]" if has_refs else "[ ]"))
    return algo_result, math_result, refs_result


def _check_sec(cls: ast.ClassDef) -> RuleResult:
    if not _has_md5(cls):
        return RuleResult("N/A", cls.lineno)
    lines = _md5_missing_flag(cls)
    if lines:
        return RuleResult("[ ]", lines[0], "md5() missing usedforsecurity=False")
    return RuleResult("[x]", cls.lineno)


def _check_step11(source_path: Path, repo_root: Path) -> RuleResult:
    """Check if matching test file calls process() directly."""
    # Map pirn/domains/X/y.py → tests/unit/domains/X/test_y.py
    try:
        rel = source_path.relative_to(repo_root / "pirn")
    except ValueError:
        return RuleResult("N/A")

    test_path = repo_root / "tests" / "unit" / rel.parent / f"test_{rel.name}"
    if not test_path.exists():
        return RuleResult("[ ]", 0, "no matching test file found")

    test_source = test_path.read_text(encoding="utf-8")
    # Check for direct process() calls (not via tapestry.run)
    if ".process(" in test_source:
        return RuleResult("[x]")
    return RuleResult("[ ]", 0, "test file exists but doesn't call .process() directly")


# ---------------------------------------------------------------------------
# Per-file audit
# ---------------------------------------------------------------------------

def audit_file(path: Path, repo_root: Path) -> FileResult:
    result = FileResult(path=path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return result

    docstring = _module_docstring(tree)
    r10_algo, r10_math, r10_refs = _check_r10(docstring)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_knot_class(node):
            continue

        init_node, process_node = _get_init_and_process(node)
        kr = KnotResult(class_name=node.name, lineno=node.lineno)

        # R1
        if init_node is not None:
            kr.set("R1", **_result_kw(_check_r1(node, init_node)))
        else:
            kr.set("R1", "N/A")

        # R2
        if init_node is not None:
            kr.set("R2", **_result_kw(_check_r2(node, init_node, process_node)))
        else:
            kr.set("R2", "N/A")

        # R3
        if init_node is not None:
            kr.set("R3", **_result_kw(_check_r3(node, init_node)))
        else:
            kr.set("R3", "N/A")

        # R4
        if init_node is not None:
            kr.set("R4", **_result_kw(_check_r4(node, init_node)))
        else:
            kr.set("R4", "N/A")

        # R5
        kr.set("R5", **_result_kw(_check_r5(node)))

        # R6
        kr.set("R6", **_result_kw(_check_r6(node, init_node, source)))

        # R7
        if init_node is not None:
            kr.set("R7", **_result_kw(_check_r7(node, init_node)))
        else:
            kr.set("R7", "N/A")

        # R8
        kr.set("R8", **_result_kw(_check_r8(node, process_node)))

        # R9
        kr.set("R9", **_result_kw(_check_r9(node, source)))

        # R10
        kr.set("R10-Algo", **_result_kw(r10_algo))
        kr.set("R10-Math", **_result_kw(r10_math))
        kr.set("R10-Refs", **_result_kw(r10_refs))

        # Sec
        kr.set("Sec", **_result_kw(_check_sec(node)))

        # Step11
        kr.set("Step11", **_result_kw(_check_step11(path, repo_root)))

        # Step12
        all_applicable = [
            r for col, r in kr.rules.items()
            if col != "Step12" and r.status != "N/A"
        ]
        all_pass = all(r.status == "[x]" for r in all_applicable)
        step11_pass = kr.rules.get("Step11", RuleResult("N/A")).status == "[x]"
        if all_pass and step11_pass:
            kr.set("Step12", "[x]")
        else:
            kr.set("Step12", "[ ]")

        result.knots.append(kr)

    return result


def _result_kw(r: RuleResult) -> dict:
    return {"status": r.status, "lineno": r.lineno, "detail": r.detail}


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_key(path: Path, domains_root: Path) -> str:
    try:
        rel = path.relative_to(domains_root)
        parts = rel.parts
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return parts[0] if parts else "other"
    except ValueError:
        return "other"


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def _row_cells(kr: KnotResult) -> list[str]:
    return [kr.rules.get(col, RuleResult("N/A")).status for col in COLUMNS]


def _render_markdown(
    results: list[FileResult],
    domains_root: Path,
    repo_root: Path,
    scan_date: str,
) -> str:
    lines: list[str] = []
    lines.append("# Knot Design Rules Audit Report")
    lines.append("")
    lines.append(f"**Scan Date:** {scan_date}  ")
    lines.append("**Method:** Automated AST scan, all rules R1-R11 + Security")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("| Column | Rule | Details |")
    lines.append("|--------|------|---------|")
    lines.append("| R1 | `__init__` body is ONLY `super().__init__(...)` | No validation, assignments, or logic |")
    lines.append("| R2 | Every `__init__` param (except `_config`, `**kwargs`) appears by same name in `process()` | Ensures direct testability |")
    lines.append("| R3 | No `raise` statements in `__init__` | All validation deferred to `process()` |")
    lines.append("| R4 | No `self._x` assignments storing inputs | Inputs arrive fresh in `process()` |")
    lines.append("| R5 | No `@property` exposing stored inputs or derived strings | Computed values via private helpers only |")
    lines.append("| R6 | Opaque resources use a dedicated vending Knot, not passed directly | Live connections/sessions cannot travel the graph |")
    lines.append(r"| R7 | `__init__` params use Knot types or `Knot \| scalar` — NOT plain scalars | Ensures graph wiring and lineage |")
    lines.append("| R8 | If inherits `SubTapestry`: `process()` calls `self._run_inner()` | N/A for plain `Knot`/`Source`/`Sink` |")
    lines.append("| R9 | Quality assessment Knots returning `QualityReport` use `*Check` suffix, not `*Gate` | N/A if not a quality assessment Knot |")
    lines.append("| R10-Algo | Module docstring contains `Algorithm:` section | Step-by-step description |")
    lines.append("| R10-Math | Module docstring contains `Math:` section | Always required — N/A confirmed only after reading `process()` |")
    lines.append("| R10-Refs | Module docstring contains `References:` section | N/A if entirely pirn-native |")
    lines.append("| Sec | Any `hashlib.md5()` call includes `usedforsecurity=False` | N/A if no md5 usage |")
    lines.append("| Step11 | Tests call `process()` directly with plain values under `tests/unit/` | Not just via Tapestry.run() |")
    lines.append("| Step12 | All applicable rules pass AND Step11 passes | Ready for ruff/pyright/pytest |")
    lines.append("")
    lines.append("**Cell values:** `[x]` = compliant · `[ ]` = violation · `N/A` = rule does not apply")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Audit Table")
    lines.append("")

    # Group files by directory
    groups: dict[str, list[FileResult]] = defaultdict(list)
    for fr in results:
        key = _group_key(fr.path, domains_root)
        groups[key].append(fr)

    header = "| File | " + " | ".join(COLUMNS) + " |"
    separator = "|------|" + "|".join(["----"] * len(COLUMNS)) + "|"

    for group_idx, (group_name, group_files) in enumerate(sorted(groups.items()), 1):
        lines.append(f"### Group {group_idx} — {group_name}")
        lines.append("")
        lines.append(header)
        lines.append(separator)

        for fr in sorted(group_files, key=lambda x: str(x.path)):
            rel_path = fr.path.relative_to(repo_root)
            if not fr.knots:
                continue
            # One row per knot class; if multiple knots, use class name as suffix
            for kr in fr.knots:
                label = f"`{rel_path}`"
                if len(fr.knots) > 1:
                    label = f"`{rel_path}` ({kr.class_name})"
                cells = _row_cells(kr)
                lines.append("| " + label + " | " + " | ".join(cells) + " |")

        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(root: Path, repo_root: Path) -> list[FileResult]:
    results = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name.startswith("test_"):
            continue
        if path.name == "__init__.py":
            continue
        fr = audit_file(path, repo_root)
        if fr.knots:
            results.append(fr)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Knot design rule violations")
    parser.add_argument(
        "--path",
        default="pirn/domains",
        help="Root path to scan (default: pirn/domains)",
    )
    parser.add_argument(
        "--output",
        default="planning/current",
        help="Directory for audit markdown output (default: planning/current)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print violation summary to stdout instead of writing a file",
    )
    args = parser.parse_args()

    # Resolve repo root as the parent of the scan path's top-level component
    scan_root = Path(args.path)
    if not scan_root.exists():
        print(f"ERROR: path not found: {scan_root}", file=sys.stderr)
        return 2

    # Repo root: walk up until we find pyproject.toml
    repo_root = scan_root.resolve()
    while repo_root != repo_root.parent:
        if (repo_root / "pyproject.toml").exists():
            break
        repo_root = repo_root.parent

    results = scan(scan_root.resolve(), repo_root)

    today = date.today().isoformat()
    domains_root = scan_root.resolve()
    md = _render_markdown(results, domains_root, repo_root, today)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    domain_name = scan_root.resolve().name
    output_path = output_dir / f"knot-violations-audit-{domain_name}-{today}.md"
    output_path.write_text(md, encoding="utf-8")
    print(f"Audit table written to {output_path}")

    # Violation summary
    violation_files = [r for r in results if r.has_violation()]
    if not violation_files:
        print("✓ Zero violations found.")
        return 0

    total = sum(len(r.all_violations()) for r in violation_files)
    print(f"\nFound {total} violation(s) across {len(violation_files)} file(s):\n")
    for fr in violation_files:
        print(f"  {fr.path}")
        for class_name, rule, lineno, detail in fr.all_violations():
            loc = f"line {lineno}" if lineno else "—"
            print(f"    [{rule}] {class_name} {loc}: {detail}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
