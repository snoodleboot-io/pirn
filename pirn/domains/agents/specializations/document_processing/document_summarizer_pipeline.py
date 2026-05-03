"""``DocumentSummarizerPipeline`` — map-reduce document summarisation.

A :class:`SubTapestry` that loads a document, splits it into chunks, asks
the LLM for a per-chunk summary, then asks the LLM once more to combine
the per-chunk summaries into a single coherent summary.

The map step issues N independent LLM calls (one per chunk); the reduce
step issues a single combining call. The pipeline returns the final
summary string.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.document_processing._load_and_chunk import (  # noqa: E501
    _LoadAndChunk,
)
from pirn.domains.agents.specializations.document_processing._map_reduce_summariser import (  # noqa: E501
    _MapReduceSummariser,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DocumentSummarizerPipeline(SubTapestry):
    """Map-reduce summarisation; returns the final summary string."""

    def __init__(
        self,
        *,
        source: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        chunk_size: int = 2000,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "DocumentSummarizerPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError(
                "DocumentSummarizerPipeline: chunk_size must be a positive "
                f"int, got {chunk_size!r}"
            )
        self._llm = llm
        self._chunk_size = chunk_size
        super().__init__(source=source, _config=_config, **kwargs)

    async def process(self, source: str, **_: Any) -> str:
        """Load the document, map-reduce summarise each chunk, and return the combined summary.

        Args:
            source: A local file path or http(s):// URL identifying the document to summarise.

        Returns:
            A single coherent summary string combining all per-chunk summaries.

        Raises:
            TypeError: If source is not a non-empty string.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentSummarizerPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        with Tapestry() as inner:
            chunks = _LoadAndChunk(
                source=source,
                chunk_size=self._chunk_size,
                _config=KnotConfig(id="chunk"),
            )
            _MapReduceSummariser(
                chunks=chunks,
                llm=self._llm,
                _config=KnotConfig(id="summarise"),
            )
        inner_result = await self._run_inner(inner)
        summary = inner_result.outputs.get("summarise")
        if not isinstance(summary, str):
            return ""
        return summary
