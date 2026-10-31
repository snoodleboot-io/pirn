"""``CascadeOutcome`` — the observable record of a model-cascade run.

PIR-874 completes the PIR-868 rebase for this type: ``CascadeOutcome`` is
``Payload[CascadeFrame, Any]``. The frame
(:class:`~pirn_agents.specializations.routing.cascade_frame.CascadeFrame`)
carries the run-level facts (chosen tier, success, escalation, attempted tiers,
decision log, confidence); ``data`` is the accepted (or best-effort) model
output the cascade actually produced.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.routing.cascade_frame import CascadeFrame


class CascadeOutcome(AgentResult[CascadeFrame, Any]):
    """What a :class:`ModelCascadeRouter` produced, plus the audit trail for cost analysis.

    Read ``chosen``, ``succeeded``, ``escalated``, ``attempted``, ``decisions``
    and ``confidence`` as ``metadata.<field>``, and the model output as ``data``.
    """

    def __init__(
        self,
        value: Any,
        chosen: str | None,
        succeeded: bool,
        escalated: bool,
        attempted: tuple[str, ...],
        decisions: tuple[str, ...],
        confidence: float | None = None,
    ) -> None:
        """Build an outcome from the run's facts and its output.

        Args:
            value: The accepted (or best available) model output, or ``None``
                when every tier failed. Stored as ``data``.
            chosen: The tier whose output was returned, or ``None``.
            succeeded: Whether a tier's output cleared its confidence floor.
            escalated: Whether the cascade climbed past the cheapest tier.
            attempted: The tier names tried, in order.
            decisions: One accept/escalate/skip log line per tier.
            confidence: Confidence of the returned output, or ``None``.
        """
        frame = CascadeFrame(
            chosen=chosen,
            succeeded=succeeded,
            escalated=escalated,
            attempted=attempted,
            decisions=decisions,
            confidence=confidence,
        )
        super().__init__(metadata=frame, data=value)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["value"] = repr(self.data)
        return audit
