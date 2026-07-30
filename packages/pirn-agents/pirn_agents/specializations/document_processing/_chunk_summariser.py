"""``_ChunkSummariser`` — summarise one document chunk.

The map half of the map-reduce summariser, split out of
``_MapReduceSummariser`` so the fan-out is expressed as a core ``ZipMap`` rather
than a hand-rolled ``asyncio.gather`` inside a single knot body. Each chunk
becomes its own engine-scheduled invocation with its own ``Result``.

``ZipMap`` rather than ``Map``: the prompt embeds ``"Chunk {i} of {n}"`` and
``Map`` injects only the element, so the position labels arrive from
:class:`_ChunkPositions` as a second zipped collection.

Note:
    The ``PromptBinding`` name still reads ``_map_reduce_summariser.*`` even
    though that module is gone. That is deliberate, not an oversight: the
    binding name is an **operator-facing override key**, so renaming it would
    silently break any deployment overriding this prompt. Same call as the
    ``assess_prompt`` binding in PIR-715.

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding


class _ChunkSummariser(Knot):
    """Summarise a single chunk, positioned within the document."""

    _chunk_summary_system: ClassVar[PromptBinding] = PromptBinding(
        name=("specializations.document_processing._map_reduce_summariser.chunk_summary_system"),
        default=(
            "Summarise the supplied document chunk in 3-5 sentences. "
            "Preserve key facts and named entities."
        ),
    )

    def __init__(
        self,
        *,
        chunk: Knot | str,
        position: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk=chunk, position=position, llm=llm, _config=_config, **kwargs)

    async def process(self, chunk: str, position: str, llm: LLMProvider, **_: Any) -> str:
        """Summarise ``chunk``.

        Args:
            chunk: The chunk text to summarise.
            position: Rendered position label, e.g. ``"Chunk 1 of 2"``.
            llm: The provider to call.

        Returns:
            The chunk's summary text.
        """
        chat_messages = [
            {
                "role": "system",
                "content": type(self)._chunk_summary_system.resolve(),
            },
            {
                "role": "user",
                "content": (f"{position}.\n\n{chunk}"),
            },
        ]
        raw = await llm.chat(chat_messages)
        return _ChunkSummariser._extract_text(raw)

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
