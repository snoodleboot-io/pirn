"""``_CodeGenerator`` — internal helper Knot for :class:`CodeAgent`.

Asks the LLM to emit code for the supplied task. Internal API; the
leading-underscore filename signals "implementation detail of CodeAgent".

Algorithm:
    1. Receive the ``task`` description and ``language`` target language.
    2. Build a two-message chat prompt: a system message instructing the
       LLM to act as a senior engineer and reply with code only, and a
       user message containing the task description.
    3. Send the prompt to the LLM via :meth:`LLMProvider.chat`.
    4. Extract and return the raw text from the LLM response.

Math:
    No numeric computation.

References:
    - OpenAI chat completion API format: https://platform.openai.com/docs/guides/chat
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class _CodeGenerator(Knot):
    """Ask the LLM to emit code for the supplied task."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        language: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, llm=llm, language=language, _config=_config, **kwargs)

    async def process(self, task: str, llm: LLMProvider, language: str, **_: Any) -> str:
        """Ask the LLM to generate code for the task in the configured language and return it.

        Args:
            task: The non-empty task description used to prompt the LLM for code generation.
            llm: The LLM provider used to generate the code.
            language: The target programming language for the generated code.

        Returns:
            The raw code string emitted by the LLM.

        Raises:
            TypeError: If task is not a non-empty string.
        """
        if not isinstance(task, str) or not task:
            raise TypeError(f"CodeAgent: task must be a non-empty string, got {task!r}")
        chat_messages = [
            {
                "role": "system",
                "content": (
                    f"You are a senior {language} engineer. Reply with "
                    f"working {language} code only — no prose, no "
                    "markdown fences, no explanation."
                ),
            },
            {"role": "user", "content": task},
        ]
        raw = await llm.chat(chat_messages)
        return _CodeGenerator._extract_text(raw)

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
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
