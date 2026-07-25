"""``DocumentTranslationPipeline`` — chunk-by-chunk LLM translation.

A :class:`SubTapestry` that loads a document, splits it into fixed-size
chunks, asks the LLM to translate each chunk into ``target_language``,
and concatenates the translated chunks back into a single string. Each
chunk is translated independently so the pipeline tolerates documents
larger than the LLM's context window.

Algorithm:
    1. ``_TranslationLoadAndChunk`` reads the document from a file path or HTTP/HTTPS
       URL and partitions it into non-overlapping windows of ``chunk_size`` characters.
    2. ``_ChunkTranslator`` issues one LLM call per chunk, prompting the model to
       translate the chunk text into ``target_language``.
    3. The translated chunk strings are concatenated in order to form the final
       translated document, which is returned as a single string.

Math:
    LLM call count: ``N = ceil(len(text) / chunk_size)`` where each call translates
    one non-overlapping partition of the source text.

References:
    - Koehn & Knowles, 2017 — Six Challenges for Neural Machine Translation
      (arXiv 1706.04972).
    - Brown et al., 2020 — Language Models are Few-Shot Learners (arXiv 2005.14165).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.document_processing._chunk_translator import (
    _ChunkTranslator,
)
from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)
from pirn_agents.specializations.document_processing._translation_load_and_chunk import (
    _TranslationLoadAndChunk,
)


class DocumentTranslationPipeline(SubTapestry):
    """Translate a document chunk-by-chunk; returns the concatenated text."""

    def __init__(
        self,
        *,
        source: Knot | str,
        target_language: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        chunk_size: Knot | int = 2000,
        allowed_root: Knot | str | None = None,
        allowed_hosts: Knot | tuple[str, ...] | None = None,
        max_bytes: Knot | int = _DocumentSourceReader.max_bytes,
        request_timeout: Knot | float = _DocumentSourceReader.request_timeout,
        connect_timeout: Knot | float = _DocumentSourceReader.connect_timeout,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            target_language=target_language,
            llm=llm,
            chunk_size=chunk_size,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        target_language: str,
        llm: LLMProvider,
        chunk_size: int = 2000,
        allowed_root: str | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
        max_bytes: int = _DocumentSourceReader.max_bytes,
        request_timeout: float = _DocumentSourceReader.request_timeout,
        connect_timeout: float = _DocumentSourceReader.connect_timeout,
        **_: Any,
    ) -> Any:
        """Load, chunk, and translate each chunk into the target language, returning the joined text.

        Args:
            source: A local file path or http(s):// URL identifying the document to translate.
            target_language: The language to translate each chunk into.
            llm: The LLM provider to use for translation.
            chunk_size: Maximum character length of each chunk.
            allowed_root: Directory root that local file reads must stay within.
                Required for local reads — the guard is fail-closed and rejects a
                bare path when this is unset.
            allowed_hosts: Optional allow-list of hostnames for URL fetches.
            max_bytes: Maximum source size in bytes, for both files and URL
                responses (default 100 MiB).
            request_timeout: HTTP request timeout in seconds.
            connect_timeout: HTTP connection timeout in seconds.

        Returns:
            The concatenated translation of all chunks as a single string.

        Raises:
            TypeError: If source or target_language is not a non-empty string.
            ValueError: If chunk_size is not a positive int, or the source is
                rejected by the SSRF / path-traversal guard.
        """
        if not isinstance(target_language, str) or not target_language:
            raise TypeError(
                "DocumentTranslationPipeline: target_language must be a "
                f"non-empty string, got {target_language!r}"
            )
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(
                "DocumentTranslationPipeline: chunk_size must be a positive "
                f"int, got {chunk_size!r}"
            )
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentTranslationPipeline: source must be a non-empty string, got {source!r}"
            )
        chunks = _TranslationLoadAndChunk(
            source=source,
            chunk_size=chunk_size,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            request_timeout=request_timeout,
            connect_timeout=connect_timeout,
            _config=KnotConfig(id="chunk"),
        )
        return _ChunkTranslator(
            chunks=chunks,
            target_language=target_language,
            llm=llm,
            _config=KnotConfig(id="translate"),
        )
