"""``_CodeGenerator`` — internal helper Knot for :class:`CodeAgent`.

Asks the LLM to emit code for the supplied task. Internal API; the
leading-underscore filename signals "implementation detail of CodeAgent".
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _CodeGenerator(Knot):
    """Ask the LLM to emit code for the supplied task."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        language: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._language = language
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> str:
        """Ask the LLM to generate code for the task in the configured language and return it.

        Args:
            task: The non-empty task description used to prompt the LLM for code generation.

        Returns:
            The raw code string emitted by the LLM.

        Raises:
            TypeError: If task is not a non-empty string.
        """
        if not isinstance(task, str) or not task:
            raise TypeError(
                "CodeAgent: task must be a non-empty string, "
                f"got {task!r}"
            )
        chat_messages = [
            {
                "role": "system",
                "content": (
                    f"You are a senior {self._language} engineer. Reply with "
                    f"working {self._language} code only — no prose, no "
                    "markdown fences, no explanation."
                ),
            },
            {"role": "user", "content": task},
        ]
        raw = await self._llm.chat(chat_messages)
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
