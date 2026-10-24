"""``CascadeFrame`` — lineage metadata for a :class:`CascadeOutcome`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CascadeFrame(PirnOpaqueValue):
    """Run-level facts for a model-cascade run.

    The frame half of the ``Payload[CascadeFrame, Any]`` split (PIR-868,
    PIR-874); the accepted (or best-effort) model output is the ``data`` half.

    Attributes
    ----------
    chosen:
        The name of the tier whose output was returned, or ``None`` when every
        tier failed.
    succeeded:
        Whether a tier's output cleared its confidence floor. ``False`` means the
        data is a best-effort fallback (last tier's output or ``None``).
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

    chosen: str | None
    succeeded: bool
    escalated: bool
    attempted: tuple[str, ...]
    decisions: tuple[str, ...]
    confidence: float | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "chosen": self.chosen,
            "succeeded": self.succeeded,
            "escalated": self.escalated,
            "attempted": list(self.attempted),
            "decisions": list(self.decisions),
            "confidence": self.confidence,
        }
