"""``EvalCaseFrame`` — the verdict half of an :class:`EvalCaseResult` (PIR-868, PIR-874)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvalCaseFrame(PirnOpaqueValue):
    """The pass/fail facts for a single :class:`EvalItem`.

    Attributes
    ----------
    item_id:
        The evaluated item's id.
    passed:
        ``True``/``False`` when thresholds applied to this item, else ``None``
        (no threshold configured for any of its metrics).
    detail:
        Free-form breakdown (produced output, per-metric threshold breaches).
    """

    item_id: str
    passed: bool | None = None
    detail: Mapping[str, Any] = field(default_factory=dict[str, Any])

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "passed": self.passed,
            "detail": dict(self.detail),
        }
