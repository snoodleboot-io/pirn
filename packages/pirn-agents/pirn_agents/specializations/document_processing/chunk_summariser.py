"""``ChunkSummariser`` — summarise one document chunk.

The map half of the map-reduce summariser, split out of
``_MapReduceSummariser`` so the fan-out is expressed as a core ``ZipMap`` rather
than a hand-rolled ``asyncio.gather`` inside a single knot body. Each chunk
becomes its own engine-scheduled invocation with its own ``Result``.

``ZipMap`` rather than ``Map``: the prompt embeds ``"Chunk {i} of {n}"`` and
``Map`` injects only the element, so the position labels arrive from
:class:`ChunkPositions` as a second zipped collection.

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.zip_map import ZipMap

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class ChunkSummariser(Knot):
    """Summarise a single chunk, positioned within the document."""

    _chunk_summary_system: ClassVar[PromptBinding] = PromptBinding(
        name=("specializations.document_processing.chunk_summariser.chunk_summary_system"),
        default=(
            "Summarise the supplied document chunk in 3-5 sentences. "
            "Preserve key facts and named entities."
        ),
    )

    def __init__(
        self,
        *,
        chunk: Knot | ZipMap | str,
        position: Knot | ZipMap | str,
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
        return LlmResponseText().extract(raw)
