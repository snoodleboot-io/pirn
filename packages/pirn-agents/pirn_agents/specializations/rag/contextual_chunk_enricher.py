"""``ContextualChunkEnricher`` — prepend document context to each chunk.

Anthropic's *contextual retrieval*: before indexing, each chunk is prefixed with
a short, LLM-generated sentence situating it within its source document ("This
chunk is from the Q3 earnings section and discusses..."). The enriched text
embeds and retrieves far better than the bare chunk because the surrounding
context disambiguates pronouns, dates, and entities. This is an ingest-time knot.

Algorithm:
    1. Validate ``documents`` (list of Mappings), ``document_text`` (str), and
       ``llm`` (:class:`LLMProvider`).
    2. For each chunk, ask the LLM for a one-sentence context given the whole
       document, and prepend it to the chunk's text under a ``context`` key,
       keeping the original ``text`` in ``raw_text``.
    3. Return the enriched documents in input order.

References:
    - Anthropic, "Contextual Retrieval" (2024).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class ContextualChunkEnricher(Knot):
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
    ) -> list[Mapping[str, Any]]:
        """Enrich each chunk with a situating context sentence.

        Args:
            documents: The chunk mappings to enrich (each with a ``text`` key).
            document_text: The full source document the chunks came from.
            llm: The provider generating the context sentence.

        Returns:
            The enriched chunk mappings, each with ``context``, ``raw_text``, and
            a context-prefixed ``text``.

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
        enriched: list[Mapping[str, Any]] = []
        for doc in documents:
            chunk_text = self._doc_text(doc)
            prompt = (
                "Give a single short sentence that situates the following chunk within the "
                "document, so it can be understood in isolation. Reply with only the sentence.\n\n"
                f"Document:\n{document_text}\n\nChunk:\n{chunk_text}"
            )
            raw = await llm.chat([{"role": "user", "content": prompt}])
            context = self._extract_text(raw).strip()
            merged = dict(doc)
            merged["context"] = context
            merged["raw_text"] = chunk_text
            merged["text"] = f"{context}\n\n{chunk_text}" if context else chunk_text
            enriched.append(merged)
        return enriched

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        text = doc.get("text")
        if isinstance(text, str):
            return text
        document = doc.get("document")
        if isinstance(document, str):
            return document
        return " ".join(str(v) for v in doc.values())

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
