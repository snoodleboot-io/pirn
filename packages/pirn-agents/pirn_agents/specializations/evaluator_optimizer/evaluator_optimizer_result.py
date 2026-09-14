"""``EvaluatorOptimizerResult`` — the typed outcome of an accept-loop run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_frame import (
    EvaluatorOptimizerFrame,
)


class EvaluatorOptimizerResult(AgentResult[EvaluatorOptimizerFrame, str]):
    """Outcome of a generator/judge accept loop.

    ``EvaluatorOptimizerResult`` is ``Payload[EvaluatorOptimizerFrame, str]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the best candidate answer produced, and ``metadata`` is the
    :class:`EvaluatorOptimizerFrame` carrying the score/accepted/iterations
    facts. The pre-ADR field names (``answer``, ``score``, ``accepted``,
    ``iterations``) stay available as read-only properties, so every
    existing construction and attribute-access call site keeps compiling
    unchanged.
    """

    def __init__(self, answer: str, score: float, accepted: bool, iterations: int) -> None:
        frame = EvaluatorOptimizerFrame(score=score, accepted=accepted, iterations=iterations)
        super().__init__(metadata=frame, data=answer)

    @property
    def answer(self) -> str:
        return self._data

    @property
    def score(self) -> float:
        return self._metadata.score

    @property
    def accepted(self) -> bool:
        return self._metadata.accepted

    @property
    def iterations(self) -> int:
        return self._metadata.iterations

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["answer"] = self.answer
        return audit
