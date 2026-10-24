"""``JudgeVerdict`` — a scored verdict from an LLM-as-judge.

``JudgeVerdict`` is ``Payload[JudgeVerdictFrame, str]`` (PIR-868 pattern,
enforced by PIR-874): the frame carries the numeric ``score`` and ``data`` is the
free-form ``feedback`` critique. Read them back as ``metadata.score`` and
``data``.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.evaluator_optimizer.judge_verdict_frame import JudgeVerdictFrame


class JudgeVerdict(AgentResult[JudgeVerdictFrame, str]):
    """A numeric judgment of a candidate answer.

    This is the scored generalisation of the boolean signal
    :class:`~pirn_agents.control.reflection_check.ReflectionCheck` returns: rather
    than a yes/no "iterate again?", the judge returns a continuous ``score`` plus
    ``feedback`` the optimiser can act on.

    The constructor takes ``score`` (0-10, higher is better) and ``feedback``
    (free-form critique the generator can use to improve the next candidate).
    """

    def __init__(self, score: float, feedback: str = "") -> None:
        super().__init__(metadata=JudgeVerdictFrame(score=score), data=feedback)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["feedback"] = self.data
        return audit
