"""``ChainOfThought`` — step-by-step reasoning via a single LLM call.

Algorithm:
    1. Receive the resolved ``prompt`` string and ``LLMProvider``.
    2. Validate input types at process time.
    3. Build a two-message request: system step-by-step instruction + user prompt.
    4. Call ``llm.chat`` with the messages.
    5. Extract text from the raw response.
    6. Return the full reasoning chain as an ``AgentResponse``.


References:
    - Wei et al. (2022) "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class ChainOfThought(Knot):
    """Send a prompt with a think-step-by-step system instruction and return the reasoning chain.

    The LLM is primed with a system prompt asking it to reason step-by-step
    before giving a final answer. The full response (including the reasoning
    chain) is returned as an :class:`AgentResponse`.
    """

    _system_prompt: str = (
        "Think step-by-step. Show your reasoning before stating your final answer."
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
        """Send the prompt to the LLM with a step-by-step system instruction and return the AgentResponse.

        Args:
            prompt: The user question or task to reason through step-by-step.
            llm: LLM provider used to perform the chat completion.

        Returns:
            An AgentResponse whose content contains the full reasoning chain.

        Raises:
            TypeError: If prompt is not a string or llm is not an LLMProvider.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "ChainOfThought: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ChainOfThought: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        messages = [
            {"role": "system", "content": type(self)._system_prompt},
            {"role": "user", "content": prompt},
        ]
        raw = await llm.chat(messages=messages)
        content = self._extract_text(raw)
        return AgentResponse(content=content)

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
