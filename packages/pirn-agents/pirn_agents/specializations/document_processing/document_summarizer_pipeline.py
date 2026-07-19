"""``DocumentSummarizerPipeline`` — map-reduce document summarisation.

A :class:`SubTapestry` that loads a document, splits it into chunks, asks
the LLM for a per-chunk summary, then asks the LLM once more to combine
the per-chunk summaries into a single coherent summary.

The map step issues N independent LLM calls (one per chunk); the reduce
step issues a single combining call. The pipeline returns the final
summary string.

Algorithm:
    1. ``_LoadAndChunk`` reads the document from a file path or HTTP/HTTPS URL and
       partitions it into overlapping character windows of ``chunk_size``.
    2. Map phase — ``_MapReduceSummariser`` sends each chunk to the LLM with a
       per-chunk summarisation prompt, collecting N partial summaries.
    3. Reduce phase — the N partial summaries are concatenated and sent to the LLM
       in a single combining prompt to produce the final summary.

Math:
    LLM call count: ``N + 1`` where ``N = ceil(len(text) / chunk_size)`` (map calls)
    plus one reduce call.

References:
    - Wu et al., 2021 — Recursively Summarizing Books with Human Feedback
      (arXiv 2109.10862).
    - Chang et al., 2023 — A Survey of Evaluation Metrics Used for NLG Systems
      (arXiv 2008.12009).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.document_processing._load_and_chunk import (
    _LoadAndChunk,
)
from pirn_agents.specializations.document_processing._map_reduce_summariser import (
    _MapReduceSummariser,
)


class DocumentSummarizerPipeline(SubTapestry):
    """Map-reduce summarisation; returns the final summary string."""

    def __init__(
        self,
        *,
        source: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        chunk_size: Knot | int = 2000,
        **kwargs: Any,
    ) -> None:
        super().__init__(source=source, llm=llm, chunk_size=chunk_size, _config=_config, **kwargs)

    async def process(self, source: str, llm: LLMProvider, chunk_size: int = 2000, **_: Any) -> Any:
        """Load the document, map-reduce summarise each chunk, and return the combined summary.

        Args:
            source: A local file path or http(s):// URL identifying the document to summarise.
            llm: The LLM provider to use for chunk summarisation and reduction.
            chunk_size: Maximum character length of each chunk.

        Returns:
            A single coherent summary string combining all per-chunk summaries.

        Raises:
            TypeError: If source is not a non-empty string.
            ValueError: If chunk_size is not a positive int.
        """
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(
                f"DocumentSummarizerPipeline: chunk_size must be a positive int, got {chunk_size!r}"
            )
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentSummarizerPipeline: source must be a non-empty string, got {source!r}"
            )
        chunks = _LoadAndChunk(
            source=source,
            chunk_size=chunk_size,
            _config=KnotConfig(id="chunk"),
        )
        return _MapReduceSummariser(
            chunks=chunks,
            llm=llm,
            _config=KnotConfig(id="summarise"),
        )
