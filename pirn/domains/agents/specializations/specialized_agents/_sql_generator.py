"""``_SQLGenerator`` — internal helper Knot for :class:`SQLAgent`.

Asks the LLM to emit a single SQL statement for a natural-language
question, optionally informed by a schema description. Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _SQLGenerator(Knot):
    """Ask the LLM to emit a single SQL statement for the question."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: LLMProvider,
        schema_description: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._schema_description = schema_description
        super().__init__(question=question, _config=_config, **kwargs)

    async def process(self, question: str, **_: Any) -> str:
        """Ask the LLM to emit a single SQL statement for the question and return it.

        Args:
            question: The non-empty natural-language question to translate into SQL.

        Returns:
            The SQL statement string emitted by the LLM, stripped of leading and trailing whitespace.

        Raises:
            TypeError: If question is not a non-empty string.
        """
        if not isinstance(question, str) or not question:
            raise TypeError(
                "SQLAgent: question must be a non-empty string, "
                f"got {question!r}"
            )
        system_lines = [
            "You are a SQL writing assistant.",
            "Reply with a single SQL statement only — no commentary, no "
            "fences, no semicolons after the statement.",
            "Use only standard SQL bind syntax (named or positional "
            "parameters); never inline values via Python string "
            "formatting like {value} or %s.",
        ]
        if self._schema_description:
            system_lines.append(
                f"Schema reference:\n{self._schema_description}"
            )
        chat_messages = [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": question},
        ]
        raw = await self._llm.chat(chat_messages)
        return _SQLGenerator._extract_text(raw).strip()

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
