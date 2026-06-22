"""``ConstitutionalFilter`` — evaluate and revise a response against a set of principles.

Algorithm:
    1. Format the principles as a bulleted list.
    2. For each revision attempt (up to ``max_revisions``):
       a. Ask the LLM to evaluate the current response against the principles.
       b. If the LLM responds with exactly ``COMPLIANT``, return the current response.
       c. Otherwise treat the LLM's output as the revised response and continue.
    3. If violations persist after all attempts, raise :class:`ConstitutionalViolationError`.


References:
    - Bai et al., "Constitutional AI: Harmlessness from AI Feedback", 2022.
      https://arxiv.org/abs/2212.08073
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.reflection.constitutional_violation_error import (
    ConstitutionalViolationError,
)
from pirn_agents.types.agent_response import AgentResponse


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
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_revisions: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            principles=principles,
            llm=llm,
            max_revisions=max_revisions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        principles: tuple[str, ...] | list[str],
        llm: LLMProvider,
        max_revisions: int = 3,
        **_: Any,
    ) -> AgentResponse:
        """Evaluate response against principles, revise until compliant or raise on failure.

        Args:
            response: The AgentResponse to evaluate against the constitutional principles.
            principles: A sequence of principle strings the response must satisfy.
            llm: The LLMProvider to use for evaluation and revision.
            max_revisions: Maximum number of revision attempts before raising.

        Returns:
            A compliant AgentResponse, possibly revised from the original.

        Raises:
            TypeError: If response is not an AgentResponse or llm is not an LLMProvider.
            ValueError: If max_revisions is not a positive int.
            ConstitutionalViolationError: If violations persist after max_revisions attempts.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ConstitutionalFilter: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_revisions, int) or max_revisions <= 0:
            raise ValueError(
                f"ConstitutionalFilter: max_revisions must be a positive int, got {max_revisions!r}"
            )
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "ConstitutionalFilter: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        principles_text = "\n".join(f"- {p}" for p in principles)
        current_content = response.content

        for _i in range(max_revisions):
            messages = [
                {"role": "system", "content": type(self)._evaluation_system},
                {
                    "role": "user",
                    "content": (f"Principles:\n{principles_text}\n\nResponse:\n{current_content}"),
                },
            ]
            raw = await llm.chat(messages=messages)
            evaluation = self._extract_text(raw).strip()
            if evaluation.upper() == "COMPLIANT":
                return AgentResponse(content=current_content)
            current_content = evaluation

        raise ConstitutionalViolationError(
            "ConstitutionalFilter: response still violates principles after "
            f"{max_revisions} revision(s)"
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
