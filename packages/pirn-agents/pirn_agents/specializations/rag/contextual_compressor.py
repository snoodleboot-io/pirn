"""``ContextualCompressor`` — trim retrieved docs to the query-relevant span.

Contextual compression shrinks each retrieved document down to only the spans
that bear on the query, dropping documents with nothing relevant. Less
irrelevant text reaches the synthesis prompt, which improves answer quality and
cuts token cost. Each surviving document keeps its identity keys (``id``,
``score``, ...) so citations survive compression.

The per-document extraction is expressed as a graph rather than a hand-rolled
``for doc in documents: await llm.chat(...)`` loop: each document becomes its
own :class:`_DocumentCompressor` invocation, fanned out with a core
:class:`~pirn.nodes.map_markers.Map`, and folded back into the surviving list
with a :class:`~pirn.nodes.reduce_.Reduce`. The engine schedules the
per-document extractions concurrently — every ready sibling starts as its own
task (PIR-841) — so extraction runs *through* the engine, with its own
``Result``, history record, and lineage per document.

Algorithm:
    1. Validate ``query`` (str), ``documents`` (list of Mappings), and ``llm``
       (:class:`LLMProvider`).
    2. Fan out one :class:`_DocumentCompressor` invocation per document, each
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


class _DocumentCompressor(Knot):
    """Extract one document's query-relevant span via the LLM, or drop it.

    Algorithm:
        1. Render the compression prompt from ``query`` and the document's
           text.
        2. Call the LLM and extract plain text from its response.
        3. Reply ``NONE`` (case-insensitive) or an empty reply means nothing
           in the document is relevant — the document is not returned at all
           (represented as ``None`` here, filtered out by the reduce step).
        4. Otherwise return the document with ``text`` replaced by the
           extracted span, ``compressed=True``, and every other key preserved.
    """

    _compression_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.contextual_compressor.compression_prompt",
        default=(
            "Extract only the sentences from the document that are relevant to the "
            "query. Preserve wording exactly. If nothing is relevant, reply with only "
            "'NONE'.\n\nQuery: {{ query }}\n\nDocument:\n{{ text }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        document: Knot | Mapping[str, Any],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, document=document, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        query: str,
        document: Mapping[str, Any],
        llm: LLMProvider,
        **_: Any,
    ) -> Mapping[str, Any] | None:
        """Compress ``document`` to its query-relevant span, or ``None`` if empty.

        Args:
            query: The query the document is compressed against.
            document: The retrieved document mapping to compress.
            llm: The provider performing extraction.

        Returns:
            The compressed document mapping, or ``None`` when nothing in it is
            relevant to ``query``.
        """
        text = _DocumentCompressor._doc_text(document)
        prompt = _DocumentCompressor._compression_prompt.render({"query": query, "text": text})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        extracted = LlmResponseText().extract(raw).strip()
        if not extracted or extracted.upper() == "NONE":
            return None
        merged = dict(document)
        merged["text"] = extracted
        merged["compressed"] = True
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


class _DropEmptyCompressions:
    """Reduce ``combine`` target: drop documents compressed to nothing."""

    @staticmethod
    def combine(items: list[Mapping[str, Any] | None]) -> list[Mapping[str, Any]]:
        """Return ``items`` with every ``None`` (fully-compressed-away document) dropped."""
        return [doc for doc in items if doc is not None]


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
