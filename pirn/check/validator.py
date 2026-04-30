from __future__ import annotations

from typing import Any

from pirn.check.validation_issue import ValidationIssue
from pirn.check.validation_result import ValidationResult


def _dfs(
    node: str,
    adj: dict[str, list[str]],
    color: dict[str, int],
    result: ValidationResult,
    cycle_reported: set[str],
) -> None:
    color[node] = 1  # GREY
    for parent_id in adj.get(node, []):
        if parent_id not in color:
            continue
        if color[parent_id] == 1 and parent_id not in cycle_reported:
            cycle_reported.add(parent_id)
            result.issues.append(
                ValidationIssue("error", node, f"cycle detected: {node!r} → {parent_id!r}")
            )
            return
        if color[parent_id] == 0:
            _dfs(parent_id, adj, color, result, cycle_reported)
    color[node] = 2  # BLACK


def validate_tapestry(tapestry: Any) -> ValidationResult:
    """Validate a ``Tapestry`` instance and return a ``ValidationResult``.

    Can be used in tests to assert a tapestry is structurally sound::

        result = validate_tapestry(build_tapestry())
        assert result.ok, result.issues
    """
    result = ValidationResult()

    knots = tapestry._store.all()
    if not knots:
        result.issues.append(ValidationIssue("warning", None, "tapestry has no knots"))
        return result

    seen_ids: dict[str, int] = {}
    for k in knots:
        seen_ids[k.knot_id] = seen_ids.get(k.knot_id, 0) + 1
    for knot_id, count in seen_ids.items():
        if count > 1:
            result.issues.append(
                ValidationIssue(
                    "error",
                    knot_id,
                    f"knot id appears {count} times — ids must be unique",
                )
            )

    adj: dict[str, list[str]] = {k.knot_id: list(k.parents.keys()) for k in knots}
    color: dict[str, int] = {k.knot_id: 0 for k in knots}  # 0=WHITE, 1=GREY, 2=BLACK
    cycle_reported: set[str] = set()

    for k in knots:
        if color[k.knot_id] == 0:
            _dfs(k.knot_id, adj, color, result, cycle_reported)

    referenced_as_parent: set[str] = set()
    for k in knots:
        referenced_as_parent.update(k.parents.keys())

    from pirn.core.parameter import Parameter

    non_param_knots = [k for k in knots if not isinstance(k, Parameter)]
    terminals = [k for k in non_param_knots if k.knot_id not in referenced_as_parent]
    if len(terminals) > 3:
        result.issues.append(
            ValidationIssue(
                "warning",
                None,
                f"{len(terminals)} terminal knots found — ensure this is intentional: "
                + ", ".join(k.knot_id for k in terminals[:5])
                + ("…" if len(terminals) > 5 else ""),
            )
        )

    return result
