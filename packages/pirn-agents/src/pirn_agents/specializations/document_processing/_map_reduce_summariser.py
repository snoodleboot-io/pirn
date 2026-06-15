"""``_MapReduceSummariser`` — internal helper Knot for :class:`DocumentSummarizerPipeline`.

Algorithm:
    1. Receive resolved ``chunks`` and ``llm``.
    2. Fan out: call ``llm.chat`` concurrently for each chunk with a summarisation prompt.
    3. If only one chunk, return its summary directly (no reduce step).
    4. Reduce: combine all partial summaries into one final summary via a second LLM call.
    5. Return the final summary string.


References:
    - MapReduce summarisation pattern from LangChain documentation.
    - Python asyncio.gather for concurrent fan-out.

Internal API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class _MapReduceSummariser(Knot):
    """Per-chunk summary fan-out plus a single reduce LLM call."""

    def __init__(
        self,
        *,
        chunks: Knot,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunks=chunks, llm=llm, _config=_config, **kwargs)

    async def process(self, chunks: list[str], llm: LLMProvider, **_: Any) -> str:
        """Summarise each chunk in parallel then reduce the partial summaries into one final summary.

        Args:
            chunks: The list of text chunks to summarise.

        Returns:
            A single combined summary string; empty if chunks is empty.
        """
        if not chunks:
            return ""
        total = len(chunks)
        partial_summaries = list(
            await asyncio.gather(
                *(
                    self._summarise_chunk(chunk, index, total, llm)
                    for index, chunk in enumerate(chunks)
                )
            )
        )
        if len(partial_summaries) == 1:
            return partial_summaries[0]
        return await self._reduce(partial_summaries, llm)

    async def _summarise_chunk(
        self,
        chunk: str,
        index: int,
        total: int,
        llm: LLMProvider,
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
                "content": (f"Chunk {index + 1} of {total}.\n\n{chunk}"),
            },
        ]
        raw = await llm.chat(chat_messages)
        return _MapReduceSummariser._extract_text(raw)

    async def _reduce(self, summaries: list[str], llm: LLMProvider) -> str:
        joined = "\n\n".join(f"Summary {i + 1}: {s}" for i, s in enumerate(summaries))
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
        raw = await llm.chat(chat_messages)
        return _MapReduceSummariser._extract_text(raw)

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
