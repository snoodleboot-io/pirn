"""``_ChunkTranslator`` — internal helper Knot for :class:`DocumentTranslationPipeline`.

Translates each chunk via the LLM and concatenates the results. Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _ChunkTranslator(Knot):
    """Translate each chunk via the LLM and concatenate."""

    def __init__(
        self,
        *,
        chunks: Knot,
        target_language: str,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._target_language = target_language
        self._llm = llm
        super().__init__(chunks=chunks, _config=_config, **kwargs)

    async def process(self, chunks: list[str], **_: Any) -> str:
        if not chunks:
            return ""
        translated_parts: list[str] = []
        for chunk in chunks:
            chat_messages = [
                {
                    "role": "system",
                    "content": (
                        f"Translate the supplied text into {self._target_language}. "
                        "Preserve formatting and named entities. Reply with the "
                        "translation only — no commentary."
                    ),
                },
                {"role": "user", "content": chunk},
            ]
            raw = await self._llm.chat(chat_messages)
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
