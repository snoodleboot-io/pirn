"""``ChunkEnricher`` — prefix one chunk with a situating context sentence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.map import Map

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class ChunkEnricher(Knot):
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
        document: Knot | Map | Mapping[str, Any],
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
        chunk_text = ChunkEnricher._doc_text(document)
        prompt = ChunkEnricher._enrichment_prompt.render(
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
