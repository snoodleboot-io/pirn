"""``DocumentSummarizerPipeline`` — map-reduce document summarisation.

A :class:`SubTapestry` that loads a document, splits it into chunks, asks
the LLM for a per-chunk summary, then asks the LLM once more to combine
the per-chunk summaries into a single coherent summary.

The map step issues N independent LLM calls (one per chunk); the reduce
step issues a single combining call. The pipeline returns the final
summary string.
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


class _LoadAndChunk(Knot):
    """Read the source text and split it into fixed-size chunks."""

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
                "DocumentSummarizerPipeline: source must be a non-empty "
                f"string, got {source!r}"
            )
        if chunk_size <= 0:
            raise ValueError(
                "DocumentSummarizerPipeline: chunk_size must be positive, "
                f"got {chunk_size!r}"
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
                "DocumentSummarizerPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        async with httpx.AsyncClient() as client:
            response = await client.get(source)
            response.raise_for_status()
            return response.text
    return Path(source).read_text(encoding="utf-8")


class _MapReduceSummariser(Knot):
    """Per-chunk summary fan-out plus a single reduce LLM call."""

    def __init__(
        self,
        *,
        chunks: Knot,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        super().__init__(chunks=chunks, _config=_config, **kwargs)

    async def process(self, chunks: list[str], **_: Any) -> str:
        if not chunks:
            return ""
        partial_summaries: list[str] = []
        for index, chunk in enumerate(chunks):
            partial_summaries.append(
                await self._summarise_chunk(chunk, index, len(chunks))
            )
        if len(partial_summaries) == 1:
            return partial_summaries[0]
        return await self._reduce(partial_summaries)

    async def _summarise_chunk(
        self,
        chunk: str,
        index: int,
        total: int,
    ) -> str:
        chat_messages = [
            {
                "role": "system",
                "content": (
                    "Summarise the supplied document chunk in 3-5 sentences. "
                    "Preserve key facts and named entities."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Chunk {index + 1} of {total}.\n\n{chunk}"
                ),
            },
        ]
        raw = await self._llm.chat(chat_messages)
        return _extract_text(raw)

    async def _reduce(self, summaries: list[str]) -> str:
        joined = "\n\n".join(
            f"Summary {i + 1}: {s}" for i, s in enumerate(summaries)
        )
        chat_messages = [
            {
                "role": "system",
                "content": (
                    "Combine the following per-chunk summaries into one "
                    "coherent summary of the entire document. Avoid "
                    "repetition and preserve chronological order."
                ),
            },
            {"role": "user", "content": joined},
        ]
        raw = await self._llm.chat(chat_messages)
        return _extract_text(raw)


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
