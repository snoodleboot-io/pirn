"""``ContextualCompressor`` — trim retrieved docs to the query-relevant span.

Contextual compression shrinks each retrieved document down to only the spans
that bear on the query, dropping documents with nothing relevant. Less
irrelevant text reaches the synthesis prompt, which improves answer quality and
cuts token cost. Each surviving document keeps its identity keys (``id``,
``score``, ...) so citations survive compression.

The per-document extraction is expressed as a graph rather than a hand-rolled
``for doc in documents: await llm.chat(...)`` loop: each document becomes its
own :class:`~pirn_agents.specializations.rag._document_compressor._DocumentCompressor`
invocation, fanned out with a core :class:`~pirn.nodes.map_markers.Map`, and
folded back into the surviving list with a :class:`~pirn.nodes.reduce_.Reduce`.
The engine schedules the per-document extractions concurrently — every ready
sibling starts as its own task (PIR-841) — so extraction runs *through* the
engine, with its own ``Result``, history record, and lineage per document.

Algorithm:
    1. Validate ``query`` (str), ``documents`` (list of Mappings), and ``llm``
       (:class:`LLMProvider`).
    2. Fan out one ``_DocumentCompressor`` invocation per document, each
       asking the LLM to extract only the query-relevant text, or reply
       ``NONE`` when nothing is relevant.
    3. A :class:`~pirn.nodes.reduce_.Reduce` drops documents compressed to
       nothing and, for the rest, replaces ``text`` with the compressed span
       while preserving all other keys.
    4. Return the surviving compressed documents in input order.

References:
    - Contextual compression retriever (LangChain).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.rag._document_compressor import _DocumentCompressor
from pirn_agents.specializations.rag._drop_empty_compressions import _DropEmptyCompressions


class ContextualCompressor(AgentPipeline):
    """Compress each retrieved document to only its query-relevant content."""

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            documents=documents,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        llm: LLMProvider,
        **_: Any,
    ) -> Knot:
        """Build the compression graph and return its surviving-documents sink knot.

        Args:
            query: The query the documents are compressed against.
            documents: The retrieved document mappings to compress.
            llm: The provider performing extraction.

        Returns:
            The sink knot whose output is the surviving compressed documents,
            preserving identity keys.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"ContextualCompressor: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ContextualCompressor: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not documents:
            return ResolvedValueKnot(value=[], _config=KnotConfig(id="empty"))

        documents_knot = ResolvedValueKnot(value=documents, _config=KnotConfig(id="documents"))
        compressed = _DocumentCompressor(
            query=query,
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | Mapping`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            document=Map(documents_knot),  # pyright: ignore[reportArgumentType]
            llm=llm,
            _config=KnotConfig(id="compress_each"),
        )
        return Reduce(
            of=compressed,
            combine=_DropEmptyCompressions.combine,
            _config=KnotConfig(id="surviving"),
        )
