"""``_ChunkTranslator`` — internal helper Knot for :class:`DocumentTranslationPipeline`.

Algorithm:
    1. Receive resolved ``chunks``, ``target_language``, and ``llm``.
    2. For each chunk, issue one LLM chat call with a translation system prompt.
    3. Extract text from the raw LLM response.
    4. Concatenate all translated parts and return the result.


References:
    - Standard LLM translation prompting patterns.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class _ChunkTranslator(Knot):
    """Translate each chunk via the LLM and concatenate."""

    def __init__(
        self,
        *,
        chunks: Knot,
        target_language: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            target_language=target_language,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, chunks: list[str], target_language: str, llm: LLMProvider, **_: Any
    ) -> str:
        """Translate each chunk via the LLM and return the concatenated translation.

        Args:
            chunks: The list of text chunks to translate.
            target_language: The language to translate each chunk into.
            llm: The LLM provider to call for translation.

        Returns:
            The concatenated translation of all chunks.
        """
        if not chunks:
            return ""
        translated_parts: list[str] = []
        for chunk in chunks:
            chat_messages = [
                {
                    "role": "system",
                    "content": (
                        f"Translate the supplied text into {target_language}. "
                        "Preserve formatting and named entities. Reply with the "
                        "translation only — no commentary."
                    ),
                },
                {"role": "user", "content": chunk},
            ]
            raw = await llm.chat(chat_messages)
            translated_parts.append(_ChunkTranslator._extract_text(raw))
        return "".join(translated_parts)

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
