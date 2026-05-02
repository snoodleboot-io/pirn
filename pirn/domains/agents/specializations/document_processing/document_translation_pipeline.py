"""``DocumentTranslationPipeline`` — chunk-by-chunk LLM translation.

A :class:`SubTapestry` that loads a document, splits it into fixed-size
chunks, asks the LLM to translate each chunk into ``target_language``,
and concatenates the translated chunks back into a single string. Each
chunk is translated independently so the pipeline tolerates documents
larger than the LLM's context window.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _TranslationLoadAndChunk(Knot):
    """Read the source text and split into fixed-size chunks."""

    def __init__(
        self,
        *,
        source: Knot | str,
        chunk_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            chunk_size=chunk_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        chunk_size: int,
        **_: Any,
    ) -> list[str]:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentTranslationPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        text = await _load_text(source)
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


async def _load_text(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "DocumentTranslationPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        async with httpx.AsyncClient() as client:
            response = await client.get(source)
            response.raise_for_status()
            return response.text
    return Path(source).read_text(encoding="utf-8")


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
            translated_parts.append(_extract_text(raw))
        return "".join(translated_parts)


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


class DocumentTranslationPipeline(SubTapestry):
    """Translate a document chunk-by-chunk; returns the concatenated text."""

    def __init__(
        self,
        *,
        source: Knot | str,
        target_language: str,
        llm: LLMProvider,
        _config: KnotConfig,
        chunk_size: int = 2000,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_language, str) or not target_language:
            raise TypeError(
                "DocumentTranslationPipeline: target_language must be a "
                f"non-empty string, got {target_language!r}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "DocumentTranslationPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(
                "DocumentTranslationPipeline: chunk_size must be a positive "
                f"int, got {chunk_size!r}"
            )
        self._target_language = target_language
        self._llm = llm
        self._chunk_size = chunk_size
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> str:
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentTranslationPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        with Tapestry() as inner:
            chunks = _TranslationLoadAndChunk(
                source=source,
                chunk_size=self._chunk_size,
                _config=KnotConfig(id="chunk"),
            )
            _ChunkTranslator(
                chunks=chunks,
                target_language=self._target_language,
                llm=self._llm,
                _config=KnotConfig(id="translate"),
            )
        inner_result = await self._run_inner(inner)
        translation = inner_result.outputs.get("translate")
        if not isinstance(translation, str):
            return ""
        return translation
