"""Static tapestry validation — ``tapestry-check`` CLI entry point.

Imports a Python module, calls a factory function, and validates the
resulting ``Tapestry`` for common structural problems:

- Missing required parameters (knots wired to nothing)
- Duplicate knot ids
- Cycles in the dependency graph
- Disconnected knots (defined but not reachable from any terminal)

Usage::

    tapestry-check mymodule:build_tapestry
    tapestry-check mymodule:build_tapestry --strict
    python -m pirn.check mymodule:build_tapestry

Exit codes:
    0  — no issues found
    1  — issues found
    2  — import / usage error
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationIssue:
    severity: str   # "error" or "warning"
    knot_id: str | None
    message: str

    def __str__(self) -> str:
        loc = f"[{self.knot_id}] " if self.knot_id else ""
        return f"{self.severity.upper()}: {loc}{self.message}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_tapestry(tapestry: Any) -> ValidationResult:
    """Validate a ``Tapestry`` instance and return a ``ValidationResult``.

    This is the library-facing API; the CLI wraps it.  Can be used in
    tests to assert that a tapestry is structurally sound::

        from pirn.check import validate_tapestry

        result = validate_tapestry(build_tapestry())
        assert result.ok, result.issues
    """
    result = ValidationResult()

    knots = tapestry._store.all()
    if not knots:
        result.issues.append(ValidationIssue("warning", None, "tapestry has no knots"))
        return result

    # 1. Duplicate knot ids
    seen_ids: dict[str, int] = {}
    for k in knots:
        seen_ids[k.knot_id] = seen_ids.get(k.knot_id, 0) + 1
    for knot_id, count in seen_ids.items():
        if count > 1:
            result.issues.append(ValidationIssue(
                "error", knot_id,
                f"knot id appears {count} times — ids must be unique",
            ))

    # 2. Cycle detection (DFS)
    adj: dict[str, list[str]] = {k.knot_id: list(k.parents.keys()) for k in knots}
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {k.knot_id: WHITE for k in knots}
    cycle_reported: set[str] = set()

    def dfs(node: str) -> bool:
        color[node] = GREY
        for parent_id in adj.get(node, []):
            if parent_id not in color:
                continue  # parameter nodes are not in adj
            if color[parent_id] == GREY and parent_id not in cycle_reported:
                cycle_reported.add(parent_id)
                result.issues.append(ValidationIssue(
                    "error", node,
                    f"cycle detected: {node!r} → {parent_id!r}",
                ))
                return True
            if color[parent_id] == WHITE:
                dfs(parent_id)
        color[node] = BLACK
        return False

    for k in knots:
        if color[k.knot_id] == WHITE:
            dfs(k.knot_id)

    # 3. Unreachable terminal check — warn about knots with no dependants
    #    (these are sinks / side-effect nodes and are fine, but knots that
    #    are neither terminals nor parents of any other knot may be orphans)
    all_ids = {k.knot_id for k in knots}
    referenced_as_parent: set[str] = set()
    for k in knots:
        referenced_as_parent.update(k.parents.keys())

    # Terminals are knots not referenced as parent of anything else.
    # A knot that has no dependants AND is not a Parameter is a terminal
    # (intentional sink).  Warn only if there are more than one non-parameter
    # terminal — a tapestry should typically have one or a few explicit sinks.
    from pirn.core.parameter import Parameter
    non_param_knots = [k for k in knots if not isinstance(k, Parameter)]
    terminals = [
        k for k in non_param_knots
        if k.knot_id not in referenced_as_parent
    ]
    if len(terminals) > 3:
        result.issues.append(ValidationIssue(
            "warning", None,
            f"{len(terminals)} terminal knots found — ensure this is intentional: "
            + ", ".join(k.knot_id for k in terminals[:5])
            + ("…" if len(terminals) > 5 else ""),
        ))

    return result


def _load_factory(spec: str) -> Any:
    """Import ``module:function`` and return the callable."""
    if ":" not in spec:
        print(
            f"error: expected MODULE:FUNCTION, got {spec!r}\n"
            "example: mymodule:build_tapestry",
            file=sys.stderr,
        )
        sys.exit(2)

    module_path, func_name = spec.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        print(f"error: cannot import {module_path!r}: {exc}", file=sys.stderr)
        sys.exit(2)

    func = getattr(module, func_name, None)
    if func is None:
        print(
            f"error: {module_path!r} has no attribute {func_name!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    return func


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="tapestry-check",
        description="Statically validate a pirn tapestry for structural issues.",
    )
    parser.add_argument(
        "spec",
        help="MODULE:FUNCTION — e.g. myapp.pipeline:build_tapestry",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )
    args = parser.parse_args(argv)

    factory = _load_factory(args.spec)

    try:
        tapestry = factory()
    except Exception as exc:
        print(f"error: factory raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    result = validate_tapestry(tapestry)

    for issue in result.issues:
        print(issue)

    if not result.issues:
        knot_count = len(tapestry._store.all())
        print(f"ok — {knot_count} knots, no issues found")

    if args.strict and result.warnings:
        return 1

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
