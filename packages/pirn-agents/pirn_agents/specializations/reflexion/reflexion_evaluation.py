"""``ReflexionEvaluation`` — the evaluator's verdict on one Reflexion attempt.

``ReflexionEvaluation`` is ``Payload[ReflexionEvaluationFrame, str]`` (PIR-868
pattern, enforced by PIR-874): the frame carries ``success`` and ``data`` is the
``feedback`` text. Read them back as ``metadata.success`` and ``data``.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.reflexion.reflexion_evaluation_frame import (
    ReflexionEvaluationFrame,
)


class ReflexionEvaluation(AgentResult[ReflexionEvaluationFrame, str]):
    """Outcome of evaluating a single actor attempt.

    The constructor takes ``success`` (whether the attempt satisfies the task)
    and ``feedback`` (what to improve when ``success`` is ``False``; empty on
    success).
    """

    def __init__(self, success: bool, feedback: str = "") -> None:
        super().__init__(metadata=ReflexionEvaluationFrame(success=success), data=feedback)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["feedback"] = self.data
        return audit
