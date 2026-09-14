"""``ContextualChunkEnricher`` — prepend document context to each chunk.

Anthropic's *contextual retrieval*: before indexing, each chunk is prefixed with
a short, LLM-generated sentence situating it within its source document ("This
chunk is from the Q3 earnings section and discusses..."). The enriched text
embeds and retrieves far better than the bare chunk because the surrounding
context disambiguates pronouns, dates, and entities. This is an ingest-time knot.

The per-chunk enrichment is expressed as a graph rather than a hand-rolled
``for doc in documents: await llm.chat(...)`` loop: each chunk becomes its own
:class:`~pirn_agents.specializations.rag.chunk_enricher.ChunkEnricher`
invocation, fanned out with a core :class:`~pirn.nodes.map_markers.Map`, and
folded back into the enriched list (preserving input order) with a
:class:`~pirn.nodes.reduce_.Reduce`. The engine schedules the per-chunk
invocations concurrently — every ready sibling starts as its own task
(PIR-841) — so enrichment runs *through* the engine, with its own ``Result``,
history record, and lineage per chunk.

Algorithm:
    1. Validate ``documents`` (list of Mappings), ``document_text`` (str), and
       ``llm`` (:class:`LLMProvider`).
    2. Fan out one ``ChunkEnricher`` invocation per chunk, each asking
       the LLM for a one-sentence context given the whole document, and
       prepending it to the chunk's text under a ``context`` key, keeping the
       original ``text`` in ``raw_text``.
    3. A :class:`~pirn.nodes.reduce_.Reduce` passes the enriched documents
       through unchanged, in input order.
    4. Return the enriched documents.

References:
    - Anthropic, "Contextual Retrieval" (2024).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.chunk_enricher import ChunkEnricher
from pirn_agents.specializations.rag.pass_through_enriched import PassThroughEnriched


class ContextualChunkEnricher(AgentPipeline):
    """Prefix each chunk with an LLM-generated situating context sentence."""

    def __init__(
        self,
        *,
        documents: Knot | list[Mapping[str, Any]],
        document_text: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            documents=documents,
            document_text=document_text,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        documents: list[Mapping[str, Any]],
        document_text: str,
        llm: LLMProvider,
        **_: Any,
    ) -> Knot:
        """Build the enrichment graph and return its enriched-documents sink knot.

        Args:
            documents: The chunk mappings to enrich (each with a ``text`` key).
            document_text: The full source document the chunks came from.
            llm: The provider generating the context sentence.

        Returns:
            The sink knot whose output is the enriched chunk mappings, each
            with ``context``, ``raw_text``, and a context-prefixed ``text``.

        Raises:
            TypeError: If ``document_text`` is not a string or ``llm`` is not an
                LLMProvider.
        """
        if not isinstance(document_text, str):
            raise TypeError(
                "ContextualChunkEnricher: document_text must be a string, "
                f"got {type(document_text).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ContextualChunkEnricher: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not documents:
            return Parameter(
                "empty", list[Mapping[str, Any]], default=[], _config=KnotConfig(id="empty")
            )

        documents_knot = Parameter(
            "documents",
            list[Mapping[str, Any]],
            default=documents,
            _config=KnotConfig(id="documents"),
        )
        enriched = ChunkEnricher(
            document=Map(documents_knot),
            document_text=document_text,
            llm=llm,
            _config=KnotConfig(id="enrich_each"),
        )
        return Reduce(
            of=enriched,
            combine=PassThroughEnriched.combine,
            _config=KnotConfig(id="enriched"),
        )
