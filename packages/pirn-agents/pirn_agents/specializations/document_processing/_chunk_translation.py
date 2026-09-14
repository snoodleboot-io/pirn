"""``_ChunkTranslation`` — translate one text chunk via a single LLM call.

Internal per-chunk knot for
:class:`~pirn_agents.specializations.document_processing._chunk_translator._ChunkTranslator`'s
fan-out (PIR-867): each chunk's translation is independent of every other
chunk's, so it is one node per chunk rather than a hand-rolled ``for`` loop
awaiting ``llm.chat`` directly.

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding


class _ChunkTranslation(Knot):
    """Translate one chunk into ``target_language`` via a single LLM call."""

    _system_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.document_processing._chunk_translator.system_prompt",
        default=(
            "Translate the supplied text into {{ target_language }}. "
            "Preserve formatting and named entities. Reply with the "
            "translation only — no commentary."
        ),
    )

    def __init__(
        self,
        *,
        chunk: Knot | str,
        target_language: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunk=chunk,
            target_language=target_language,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(self, chunk: str, target_language: str, llm: LLMProvider, **_: Any) -> str:
        """Translate ``chunk`` and return the extracted translation text.

        Args:
            chunk: The text chunk to translate.
            target_language: The language to translate the chunk into.
            llm: The LLM provider to call for translation.

        Returns:
            The translated text for this chunk.
        """
        chat_messages = [
            {
                "role": "system",
                "content": type(self)._system_prompt.render(
                    {"target_language": target_language},
                ),
            },
            {"role": "user", "content": chunk},
        ]
        raw = await llm.chat(chat_messages)
        return _ChunkTranslation._extract_text(raw)

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
