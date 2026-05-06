"""``_SQLGenerator`` — internal helper Knot for :class:`SQLAgent`.

Asks the LLM to emit a single SQL statement for a natural-language
question, optionally informed by a schema description. Internal API.

Algorithm:
    1. Receive the ``question``, ``llm`` provider, and optional
       ``schema_description`` string.
    2. Build a system prompt that instructs the LLM to reply with a
       single SQL statement only, appending the schema reference when
       ``schema_description`` is non-empty.
    3. Send the two-message chat prompt to the LLM via
       :meth:`LLMProvider.chat`.
    4. Extract and return the raw text, stripped of surrounding whitespace.

Math:
    No numeric computation.

References:
    - Text-to-SQL survey: Katsogiannis-Meimarakis & Koutrika, 2023
      (ACM SIGMOD Record, doi 10.1145/3613068.3613069).
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
        llm: Knot | LLMProvider,
        schema_description: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            question=question,
            llm=llm,
            schema_description=schema_description,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        question: str,
        llm: LLMProvider,
        schema_description: str,
        **_: Any,
    ) -> str:
        """Ask the LLM to emit a single SQL statement for the question and return it.

        Args:
            question: The non-empty natural-language question to translate into SQL.
            llm: The LLM provider used to generate the SQL statement.
            schema_description: Optional schema reference appended to the system prompt.

        Returns:
            The SQL statement string emitted by the LLM, stripped of leading and trailing whitespace.

        Raises:
            TypeError: If question is not a non-empty string.
        """
        if not isinstance(question, str) or not question:
            raise TypeError(f"SQLAgent: question must be a non-empty string, got {question!r}")
        system_lines = [
            "You are a SQL writing assistant.",
            "Reply with a single SQL statement only — no commentary, no "
            "fences, no semicolons after the statement.",
            "Use only standard SQL bind syntax (named or positional "
            "parameters); never inline values via Python string "
            "formatting like {value} or %s.",
        ]
        if schema_description:
            system_lines.append(f"Schema reference:\n{schema_description}")
        chat_messages = [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": question},
        ]
        raw = await llm.chat(chat_messages)
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
