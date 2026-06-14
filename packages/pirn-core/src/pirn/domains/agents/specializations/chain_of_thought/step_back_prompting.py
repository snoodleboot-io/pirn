"""``StepBackPrompting`` — abstraction-first prompting strategy.

Algorithm:
    1. Receive the resolved ``prompt`` string and ``LLMProvider``.
    2. Validate input types at process time.
    3. Call ``llm.chat`` with a step-back system prompt to identify underlying principles.
    4. Extract text from the step-back raw response.
    5. Call ``llm.chat`` again with the step-back answer as context plus the original prompt.
    6. Extract text from the forward raw response.
    7. Return the final answer as an ``AgentResponse``.


References:
    - Zheng et al. (2023) "Take a Step Back: Evoking Reasoning via Abstraction in Large Language Models"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
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
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, _config=_config, **kwargs)

    async def process(self, prompt: str, llm: LLMProvider, **_: Any) -> AgentResponse:
        """Elicit background principles via a step-back question, then answer the original prompt.

        Args:
            prompt: The original user question to answer.
            llm: LLM provider used to perform both chat completions.

        Returns:
            An AgentResponse containing the final answer informed by the step-back reasoning.

        Raises:
            TypeError: If prompt is not a string or llm is not an LLMProvider.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"StepBackPrompting: prompt must be a string, got {type(prompt).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"StepBackPrompting: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        step_back_messages = [
            {"role": "system", "content": type(self)._step_back_system},
            {"role": "user", "content": prompt},
        ]
        step_back_raw = await llm.chat(messages=step_back_messages)
        step_back_answer = self._extract_text(step_back_raw)

        forward_messages = [
            {"role": "system", "content": type(self)._forward_system},
            {
                "role": "user",
                "content": (
                    f"Background principles:\n{step_back_answer}\n\nOriginal question:\n{prompt}"
                ),
            },
        ]
        forward_raw = await llm.chat(messages=forward_messages)
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
