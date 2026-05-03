"""``StepBackPrompting`` — abstraction-first prompting strategy."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class StepBackPrompting(Knot):
    """Ask a higher-level abstraction question first, then use the answer to answer the original.

    Two LLM calls are made:

    1. A *step-back* call that asks the model to identify the underlying
       principle, concept, or category relevant to the original question.
    2. A *forward* call that provides both the step-back answer and the
       original question to elicit a grounded final response.
    """

    _step_back_system: str = (
        "You are an expert at identifying the underlying principles and "
        "concepts relevant to a question. Given the question below, first "
        "ask and answer a more abstract, high-level question whose answer "
        "would be useful context for answering the original question."
    )
    _forward_system: str = (
        "You are a helpful assistant. Use the provided background principles "
        "to answer the original question accurately."
    )

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "StepBackPrompting: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> AgentResponse:
        """Elicit background principles via a step-back question, then answer the original prompt.

        Args:
            prompt: The original user question to answer.

        Returns:
            An AgentResponse containing the final answer informed by the step-back reasoning.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "StepBackPrompting: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        step_back_messages = [
            {"role": "system", "content": type(self)._step_back_system},
            {"role": "user", "content": prompt},
        ]
        step_back_raw = await self._llm.chat(messages=step_back_messages)
        step_back_answer = self._extract_text(step_back_raw)

        forward_messages = [
            {"role": "system", "content": type(self)._forward_system},
            {
                "role": "user",
                "content": (
                    f"Background principles:\n{step_back_answer}\n\n"
                    f"Original question:\n{prompt}"
                ),
            },
        ]
        forward_raw = await self._llm.chat(messages=forward_messages)
        answer = self._extract_text(forward_raw)
        return AgentResponse(content=answer)

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
