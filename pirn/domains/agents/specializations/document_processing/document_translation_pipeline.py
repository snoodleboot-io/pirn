"""``DocumentTranslationPipeline`` — chunk-by-chunk LLM translation.

A :class:`SubTapestry` that loads a document, splits it into fixed-size
chunks, asks the LLM to translate each chunk into ``target_language``,
and concatenates the translated chunks back into a single string. Each
chunk is translated independently so the pipeline tolerates documents
larger than the LLM's context window.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.document_processing._chunk_translator import (  # noqa: E501
    _ChunkTranslator,
)
from pirn.domains.agents.specializations.document_processing._translation_load_and_chunk import (  # noqa: E501
    _TranslationLoadAndChunk,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


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
