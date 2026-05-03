"""``SelfCritiqueRevise`` — generate, critique, then revise a response."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class SelfCritiqueRevise(Knot):
    """Generate an initial response, critique it, then revise based on the critique.

    Three sequential LLM calls are made:

    1. **Generate** — produce an initial answer to the prompt.
    2. **Critique** — identify weaknesses, errors, or gaps in the initial answer.
    3. **Revise** — produce a final improved answer that addresses the critique.

    The final revised answer is returned as an :class:`AgentResponse`.
    """

    _generation_system: str = (
        "You are a helpful assistant. Answer the question as accurately and "
        "completely as you can."
    )
    _critique_system: str = (
        "You are a critical reviewer. Identify the main weaknesses, errors, "
        "or gaps in the following answer. Be concise and specific."
    )
    _revision_system: str = (
        "You are a helpful assistant. Given the original question, the initial "
        "answer, and a critique of that answer, produce an improved final answer "
        "that addresses the critique."
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
                "SelfCritiqueRevise: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> AgentResponse:
        """Generate an initial answer, critique it, revise it, and return the final AgentResponse.

        Args:
            prompt: The user question or task to answer.

        Returns:
            An AgentResponse containing the final revised answer.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "SelfCritiqueRevise: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        initial_raw = await self._llm.chat(messages=[
            {"role": "system", "content": type(self)._generation_system},
            {"role": "user", "content": prompt},
        ])
        initial = self._extract_text(initial_raw)

        critique_raw = await self._llm.chat(messages=[
            {"role": "system", "content": type(self)._critique_system},
            {"role": "user", "content": initial},
        ])
        critique = self._extract_text(critique_raw)

        revision_raw = await self._llm.chat(messages=[
            {"role": "system", "content": type(self)._revision_system},
            {
                "role": "user",
                "content": (
                    f"Original question:\n{prompt}\n\n"
                    f"Initial answer:\n{initial}\n\n"
                    f"Critique:\n{critique}"
                ),
            },
        ])
        revised = self._extract_text(revision_raw)
        return AgentResponse(content=revised)

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
