"""``_ChunkTranslator`` — internal helper Knot for :class:`DocumentTranslationPipeline`.

Each chunk's translation is independent of every other chunk's — chunk N's
prompt never depends on chunk N-1's result — so this is a fan-out, not a
sequential loop: one :class:`~pirn_agents.specializations.document_processing._chunk_translation._ChunkTranslation`
knot per chunk, wired as the parents of an :class:`~pirn.nodes.aggregator.Aggregator`
that reassembles the concatenated translation in input order (PIR-867;
before this, the loop awaited ``llm.chat`` directly once per chunk, so no
chunk's call had its own lineage row).

Algorithm:
    1. Receive resolved ``chunks``, ``target_language``, and ``llm``.
    2. When ``chunks`` is empty, return a ``Parameter`` defaulting to ``""``
       — an ``Aggregator`` requires at least one parent.
    3. Otherwise build one ``_ChunkTranslation`` per chunk and wire them as
       the parents of an ``Aggregator`` whose combine concatenates the
       translations in the chunks' original order.

References:
    - Standard LLM translation prompting patterns.

Internal API.
"""

from __future__ import annotations

import functools
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.document_processing._chunk_translation import (
    _ChunkTranslation,
)


class _ChunkTranslator(AgentPipeline):
    """Translate each chunk via the LLM, concurrently, and concatenate."""

    def __init__(
        self,
        *,
        chunks: Knot | list[str],
        target_language: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            target_language=target_language,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, chunks: list[str], target_language: str, llm: LLMProvider, **_: Any
    ) -> Knot:
        """Wire one translation knot per chunk and return the concatenating sink.

        Args:
            chunks: The list of text chunks to translate.
            target_language: The language to translate each chunk into.
            llm: The LLM provider to call for translation.

        Returns:
            The sink of the inner pipeline: a ``Parameter`` defaulting to
            ``""`` when ``chunks`` is empty, or an :class:`Aggregator` over
            one ``_ChunkTranslation`` per chunk whose output is the
            concatenated translation, in the chunks' original order.
        """
        if not chunks:
            return Parameter("empty", str, default="", _config=KnotConfig(id="empty"))
        per_chunk: dict[str, Knot] = {
            f"chunk_{index}": _ChunkTranslation(
                chunk=chunk,
                target_language=target_language,
                llm=llm,
                _config=KnotConfig(id=f"translate_{index}"),
            )
            for index, chunk in enumerate(chunks)
        }
        return Aggregator(
            combine=functools.partial(self._concat_in_order, len(chunks)),
            _config=KnotConfig(id="concat"),
            **per_chunk,
        )

    @staticmethod
    def _concat_in_order(count: int, **by_key: str) -> str:
        """Concatenate every chunk's translation, in the chunks' original order."""
        return "".join(by_key[f"chunk_{index}"] for index in range(count))
