"""``ReflexionResult`` — the typed outcome of a Reflexion run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt
from pirn_agents.specializations.reflexion.reflexion_frame import ReflexionFrame


class ReflexionResult(AgentResult[ReflexionFrame, str]):
    """Outcome of a bounded Reflexion loop.

    ``ReflexionResult`` is ``Payload[ReflexionFrame, str]`` (PIR-868,
    following the ADR agents-speaks-core WS6b pattern) — ``data`` is the
    best/last answer produced, and ``metadata`` is the :class:`ReflexionFrame`
    carrying the succeeded/iterations/attempts facts. The constructor takes the pattern's
    named fields (``answer``, ``succeeded``, ``iterations``, ``attempts``), and each is also
    a read-only property.
    """

    def __init__(
        self,
        answer: str,
        succeeded: bool,
        iterations: int,
        attempts: tuple[ReflexionAttempt, ...],
    ) -> None:
        frame = ReflexionFrame(succeeded=succeeded, iterations=iterations, attempts=attempts)
        super().__init__(metadata=frame, data=answer)

    @property
    def answer(self) -> str:
        return self._data

    @property
    def succeeded(self) -> bool:
        return self._metadata.succeeded

    @property
    def iterations(self) -> int:
        return self._metadata.iterations

    @property
    def attempts(self) -> tuple[ReflexionAttempt, ...]:
        return self._metadata.attempts

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["answer"] = self.answer
        return audit
