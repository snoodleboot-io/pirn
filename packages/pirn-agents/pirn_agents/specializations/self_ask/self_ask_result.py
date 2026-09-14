"""``SelfAskResult`` — the typed outcome of a Self-Ask run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.self_ask.self_ask_frame import SelfAskFrame


class SelfAskResult(AgentResult[SelfAskFrame, str]):
    """Outcome of a Self-Ask decomposition.

    ``SelfAskResult`` is ``Payload[SelfAskFrame, str]`` (PIR-868, following
    the ADR agents-speaks-core WS6b pattern) — ``data`` is the composed
    final answer, and ``metadata`` is the :class:`SelfAskFrame` carrying the
    sub-questions and sub-answers. The constructor takes the pattern's named fields
    (``final_answer``, ``subquestions``, ``subanswers``); read them back as ``data``
    and ``metadata.<field>``.
    """

    def __init__(
        self, final_answer: str, subquestions: tuple[str, ...], subanswers: tuple[str, ...]
    ) -> None:
        frame = SelfAskFrame(subquestions=subquestions, subanswers=subanswers)
        super().__init__(metadata=frame, data=final_answer)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["final_answer"] = self.data
        return audit
