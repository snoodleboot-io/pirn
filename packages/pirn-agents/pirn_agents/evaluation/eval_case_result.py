"""``EvalCaseResult`` — one item's metric scores and pass/fail verdict."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvalCaseResult(PirnOpaqueValue):
    """The evaluation outcome for a single :class:`EvalItem`.

    Attributes
    ----------
    item_id:
        The evaluated item's id.
    metrics:
        Mapping of metric name to the item's score for that metric.
    passed:
        ``True``/``False`` when thresholds applied to this item, else ``None``
        (no threshold configured for any of its metrics).
    detail:
        Free-form breakdown (produced output, per-metric threshold breaches).
    """

    item_id: str
    metrics: Mapping[str, float]
    passed: bool | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "metrics": dict(self.metrics),
            "passed": self.passed,
            "detail": dict(self.detail),
        }
