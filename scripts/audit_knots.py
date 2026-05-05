"""Knot design-rule violation scanner.

Scans pirn/domains/ for violations of the rules in
docs/contributing/knot-design-rules.md and emits a per-file report.

Usage:
    uv run python scripts/audit_knots.py [--path pirn/domains/data]

Exit code 0 when zero violations are found; 1 otherwise.
"""

from __future__ import annotations

import ast
import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Violation:
    rule: str
    message: str
    lineno: int


@dataclass
class FileResult:
    path: Path
    violations: list[Violation] = field(default_factory=list)

    def add(self, rule: str, message: str, lineno: int) -> None:
        self.violations.append(Violation(rule=rule, message=message, lineno=lineno))

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0


def _is_knot_class(node: ast.ClassDef) -> bool:
    """Return True if the class inherits from Knot, SubTapestry, or a known domain base."""
    knot_bases = {"Knot", "SubTapestry", "Source", "Sink"}
    for base in node.bases:
        name = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else None
        )
        if name in knot_bases:
            return True
    return False


def _method_body_source(node: ast.FunctionDef | ast.AsyncFunctionDef, src_lines: list[str]) -> str:
    start = node.body[0].lineno - 1
    end = node.end_lineno or start
    return "\n".join(src_lines[start:end])


def _has_run_inner(process_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(process_node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "_run_inner":
                return True
    return False


def audit_file(path: Path) -> FileResult:
    result = FileResult(path=path)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.add("parse", f"SyntaxError: {exc}", 0)
        return result

    src_lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_knot_class(node):
            continue

        class_name = node.name

        # Rule 7: *Gate naming for non-Gate framework classes
        if class_name.endswith("Gate") and "quality" in str(path):
            result.add(
                "Rule 7",
                f"Class '{class_name}' ends with 'Gate' — quality assessment Knots must use '*Check'",
                node.lineno,
            )

        # Rule 7 (ingestion variant): Gate in name for non-quality knot
        if "Gate" in class_name and "quality" not in str(path):
            result.add(
                "Rule 7",
                f"Class '{class_name}' contains 'Gate' — review naming; Gate is a framework primitive",
                node.lineno,
            )

        # Collect __init__ and process methods
        init_node: ast.FunctionDef | None = None
        process_node: ast.AsyncFunctionDef | ast.FunctionDef | None = None

        for item in ast.walk(node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__init__" and any(
                    isinstance(p, ast.arg) and p.arg == "self"
                    for p in item.args.args
                ):
                    init_node = item  # type: ignore[assignment]
                if item.name == "process":
                    process_node = item

        # Rule 8: SubTapestry without _run_inner
        inherits_sub_tapestry = any(
            (isinstance(b, ast.Name) and b.id == "SubTapestry") or
            (isinstance(b, ast.Attribute) and b.attr == "SubTapestry")
            for b in node.bases
        )
        if inherits_sub_tapestry and process_node and not _has_run_inner(process_node):
            result.add(
                "Rule 8",
                f"Class '{class_name}' inherits SubTapestry but process() never calls self._run_inner()",
                node.lineno,
            )

        if init_node is None:
            continue

        # Rule 3 / Rule 4: validation or self._x assignments in __init__
        for stmt in ast.walk(init_node):
            # self._x = ... in __init__
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and target.attr.startswith("_")
                        and not target.attr.startswith("__")
                    ):
                        # Skip _mutable_ framework-reserved prefix
                        if not target.attr.startswith("_mutable_"):
                            result.add(
                                "Rule 4",
                                f"Class '{class_name}.__init__': stores input as self.{target.attr}",
                                stmt.lineno,
                            )

            # Raise statements in __init__ = validation in constructor
            if isinstance(stmt, ast.Raise) and stmt is not init_node:
                result.add(
                    "Rule 3",
                    f"Class '{class_name}.__init__': contains raise statement (validation belongs in process())",
                    stmt.lineno,
                )

        # Rule 4: @property fields on Knot class
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if (
                        isinstance(decorator, ast.Name) and decorator.id == "property"
                    ) or (
                        isinstance(decorator, ast.Attribute) and decorator.attr == "property"
                    ):
                        result.add(
                            "Rule 4 / Rule 5",
                            f"Class '{class_name}': @property '{item.name}' — inputs/derived strings must not be exposed as properties",
                            item.lineno,
                        )

        # Rule 2: process() missing declared inputs (params = only self + **_)
        if process_node is not None:
            args = process_node.args
            named_params = [a.arg for a in args.args if a.arg != "self"]
            named_params += [a.arg for a in (args.kwonlyargs or [])]
            # Filter out **_ / **kwargs catch-all
            has_named = any(p != "_" and not p.startswith("__") for p in named_params)
            # If __init__ has params beyond self, _config, **kwargs but process has none — violation
            if init_node is not None:
                init_params = [
                    a.arg for a in init_node.args.kwonlyargs
                    if a.arg not in ("_config", "kwargs")
                ]
                if init_params and not has_named:
                    result.add(
                        "Rule 2",
                        f"Class '{class_name}.process()': declares no named inputs but __init__ has {init_params} — process() must declare all inputs",
                        process_node.lineno,
                    )

        # Security: hashlib.md5 without usedforsecurity=False
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Call):
                func = stmt.func
                is_md5 = (
                    (isinstance(func, ast.Attribute) and func.attr == "md5") or
                    (isinstance(func, ast.Name) and func.id == "md5")
                )
                if is_md5:
                    kwarg_names = [kw.arg for kw in stmt.keywords]
                    if "usedforsecurity" not in kwarg_names:
                        result.add(
                            "Security",
                            f"Class '{class_name}': hashlib.md5() missing usedforsecurity=False",
                            stmt.lineno,
                        )

    return result


def scan(root: Path) -> list[FileResult]:
    results = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name.startswith("test_"):
            continue
        r = audit_file(path)
        if not r.ok:
            results.append(r)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Knot design rule violations")
    parser.add_argument(
        "--path",
        default="pirn/domains",
        help="Root path to scan (default: pirn/domains)",
    )
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"ERROR: path not found: {root}", file=sys.stderr)
        return 2

    results = scan(root)

    if not results:
        print("✓ Zero violations found.")
        return 0

    total = sum(len(r.violations) for r in results)
    print(f"Found {total} violation(s) across {len(results)} file(s):\n")

    for file_result in results:
        print(f"  {file_result.path}")
        for v in file_result.violations:
            print(f"    [{v.rule}] line {v.lineno}: {v.message}")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
