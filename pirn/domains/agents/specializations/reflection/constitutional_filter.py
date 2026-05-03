"""``ConstitutionalFilter`` — evaluate and revise a response against a set of principles."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.reflection.constitutional_violation_error import ConstitutionalViolationError
from pirn.domains.agents.types.agent_response import AgentResponse


class ConstitutionalFilter(Knot):
    """Evaluate a response against constitutional principles and revise until compliant.

    For each revision attempt the LLM is asked to identify any violations of
    the supplied principles and to produce a revised response that addresses
    them. If the LLM reports no violations the current response is returned
    immediately. If violations remain after ``max_revisions`` attempts,
    :class:`ConstitutionalViolationError` is raised.
    """

    _evaluation_system: str = (
        "You are a constitutional AI reviewer. Evaluate the response against "
        "the principles listed below. If the response violates any principle, "
        "describe the violation and provide a revised response that is compliant. "
        "If the response is fully compliant, reply with exactly: COMPLIANT"
    )

    def __init__(
        self,
        *,
        response: Knot,
        principles: Knot | tuple[str, ...] | list[str],
        llm: LLMProvider,
        _config: KnotConfig,
        max_revisions: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ConstitutionalFilter: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(max_revisions, int) or max_revisions <= 0:
            raise ValueError(
                "ConstitutionalFilter: max_revisions must be a positive int, "
                f"got {max_revisions!r}"
            )
        self._llm = llm
        self._max_revisions = max_revisions
        super().__init__(
            response=response,
            principles=principles,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        principles: tuple[str, ...] | list[str],
        **_: Any,
    ) -> AgentResponse:
        """Evaluate response against principles, revise until compliant or raise on failure.

        Args:
            response: The AgentResponse to evaluate against the constitutional principles.
            principles: A sequence of principle strings the response must satisfy.

        Returns:
            A compliant AgentResponse, possibly revised from the original.

        Raises:
            TypeError: If response is not an AgentResponse instance.
            ConstitutionalViolationError: If violations persist after max_revisions attempts.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "ConstitutionalFilter: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        principles_text = "\n".join(f"- {p}" for p in principles)
        current_content = response.content

        for _ in range(self._max_revisions):
            messages = [
                {"role": "system", "content": type(self)._evaluation_system},
                {
                    "role": "user",
                    "content": (
                        f"Principles:\n{principles_text}\n\n"
                        f"Response:\n{current_content}"
                    ),
                },
            ]
            raw = await self._llm.chat(messages=messages)
            evaluation = self._extract_text(raw).strip()
            if evaluation.upper() == "COMPLIANT":
                return AgentResponse(content=current_content)
            current_content = evaluation

        raise ConstitutionalViolationError(
            "ConstitutionalFilter: response still violates principles after "
            f"{self._max_revisions} revision(s)"
        )

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
        return str(raw)
