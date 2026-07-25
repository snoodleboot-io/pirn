"""``CascadeOutcome`` — the observable record of a model-cascade run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CascadeOutcome(PirnOpaqueValue):
    """What a :class:`ModelCascadeRouter` produced, plus the audit trail for cost analysis.

    Attributes
    ----------
    value:
        The accepted (or best available) model output, or ``None`` when every
        tier failed.
    chosen:
        The name of the tier whose output was returned, or ``None`` when every
        tier failed.
    succeeded:
        Whether a tier's output cleared its confidence floor. ``False`` means the
        value is a best-effort fallback (last tier's output or ``None``).
    escalated:
        Whether the cascade climbed past the cheapest tier.
    attempted:
        The tier names tried, in order — the cost story of the run.
    decisions:
        A human-readable log line per tier explaining accept/escalate/skip, so
        the escalation choice is observable.
    confidence:
        The confidence score of the returned output, or ``None`` when no tier
        produced a scored output.
    """

    value: Any
    chosen: str | None
    succeeded: bool
    escalated: bool
    attempted: tuple[str, ...]
    decisions: tuple[str, ...]
    confidence: float | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "value": repr(self.value),
            "chosen": self.chosen,
            "succeeded": self.succeeded,
            "escalated": self.escalated,
            "attempted": list(self.attempted),
            "decisions": list(self.decisions),
            "confidence": self.confidence,
        }
