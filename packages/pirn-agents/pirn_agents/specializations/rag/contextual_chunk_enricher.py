"""``ContextualChunkEnricher`` — prepend document context to each chunk.

Anthropic's *contextual retrieval*: before indexing, each chunk is prefixed with
a short, LLM-generated sentence situating it within its source document ("This
chunk is from the Q3 earnings section and discusses..."). The enriched text
embeds and retrieves far better than the bare chunk because the surrounding
context disambiguates pronouns, dates, and entities. This is an ingest-time knot.

The per-chunk enrichment is expressed as a graph rather than a hand-rolled
``for doc in documents: await llm.chat(...)`` loop: each chunk becomes its own
:class:`_ChunkEnricher` invocation, fanned out with a core
:class:`~pirn.nodes.map_markers.Map`, and folded back into the enriched list
(preserving input order) with a :class:`~pirn.nodes.reduce_.Reduce`. The engine
schedules the per-chunk invocations concurrently — every ready sibling starts
as its own task (PIR-841) — so enrichment runs *through* the engine, with its
own ``Result``, history record, and lineage per chunk.

Algorithm:
    1. Validate ``documents`` (list of Mappings), ``document_text`` (str), and
       ``llm`` (:class:`LLMProvider`).
    2. Fan out one :class:`_ChunkEnricher` invocation per chunk, each asking
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
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _ChunkEnricher(Knot):
    """Prefix one chunk with an LLM-generated situating context sentence."""

    _enrichment_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.contextual_chunk_enricher.enrichment_prompt",
        default=(
            "Give a single short sentence that situates the following chunk within the "
            "document, so it can be understood in isolation. Reply with only the sentence.\n\n"
            "Document:\n{{ document_text }}\n\nChunk:\n{{ chunk_text }}"
        ),
    )

    def __init__(
        self,
        *,
        document: Knot | Mapping[str, Any],
        document_text: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            document=document,
            document_text=document_text,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        document: Mapping[str, Any],
        document_text: str,
        llm: LLMProvider,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Enrich ``document`` with a situating context sentence.

        Args:
            document: The chunk mapping to enrich (with a ``text`` key).
            document_text: The full source document the chunk came from.
            llm: The provider generating the context sentence.

        Returns:
            The enriched chunk mapping, with ``context``, ``raw_text``, and a
            context-prefixed ``text``.
        """
        chunk_text = _ChunkEnricher._doc_text(document)
        prompt = _ChunkEnricher._enrichment_prompt.render(
            {"document_text": document_text, "chunk_text": chunk_text}
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        context = LlmResponseText().extract(raw).strip()
        merged = dict(document)
        merged["context"] = context
        merged["raw_text"] = chunk_text
        merged["text"] = f"{context}\n\n{chunk_text}" if context else chunk_text
        return merged

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        text = doc.get("text")
        if isinstance(text, str):
            return text
        document = doc.get("document")
        if isinstance(document, str):
            return document
        return " ".join(str(v) for v in doc.values())


class _PassThroughEnriched:
    """Reduce ``combine`` target: surface the enriched documents unchanged."""

    @staticmethod
    def combine(items: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Return ``items`` as a plain list, preserving Map's input order."""
        return list(items)


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
            return ResolvedValueKnot(value=[], _config=KnotConfig(id="empty"))

        documents_knot = ResolvedValueKnot(value=documents, _config=KnotConfig(id="documents"))
        enriched = _ChunkEnricher(
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | Mapping`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            document=Map(documents_knot),  # pyright: ignore[reportArgumentType]
            document_text=document_text,
            llm=llm,
            _config=KnotConfig(id="enrich_each"),
        )
        return Reduce(
            of=enriched,
            combine=_PassThroughEnriched.combine,
            _config=KnotConfig(id="enriched"),
        )
