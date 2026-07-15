"""``GateResult`` — the pass/fail verdict of a regression gate, with a diff."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class GateResult(PirnOpaqueValue):
    """Whether an eval run cleared its regression gate, plus every breach.

    Emits a human-readable Markdown diff (for the CI job log / PR comment) and a
    machine-readable JSON form. Each breach names the metric, its measured value,
    the limit it violated, and the kind of violation (``threshold``,
    ``regression``, or ``missing``).

    Attributes
    ----------
    passed:
        ``True`` iff there are no breaches.
    breaches:
        One mapping per violated metric.
    detail:
        Free-form context (the compared aggregates).
    """

    passed: bool
    breaches: tuple[Mapping[str, Any], ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise ``breaches`` to a tuple.

        Raises:
            TypeError: If ``breaches`` is not a sequence of mappings.
        """
        if isinstance(self.breaches, (str, bytes)) or not isinstance(self.breaches, Sequence):
            raise TypeError(
                f"GateResult.breaches must be a sequence of mappings, "
                f"got {type(self.breaches).__name__}"
            )
        object.__setattr__(self, "breaches", tuple(self.breaches))

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the gate result to a stable, machine-readable JSON string."""
        return json.dumps(
            {
                "passed": self.passed,
                "breaches": [dict(b) for b in self.breaches],
                "detail": dict(self.detail),
            },
            indent=indent,
            sort_keys=True,
        )

    def to_markdown(self) -> str:
        """Render a clear pass/fail diff suitable for a CI job log or PR comment."""
        if self.passed:
            return "Quality gate PASSED: all metrics met their thresholds."
        header = (
            "Quality gate FAILED\n\n| metric | kind | actual | limit |\n| --- | --- | ---: | ---: |"
        )
        lines = [header]
        for breach in self.breaches:
            actual = breach.get("actual")
            limit = breach.get("limit")
            lines.append(
                f"| {breach.get('metric')} | {breach.get('kind')} | "
                f"{self._fmt(actual)} | {self._fmt(limit)} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: Any) -> str:
        return "—" if value is None else f"{value:.4g}"

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "breaches": [dict(b) for b in self.breaches],
            "detail": dict(self.detail),
        }
