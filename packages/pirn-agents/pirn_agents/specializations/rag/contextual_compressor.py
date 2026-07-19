"""``ContextualCompressor`` — trim retrieved docs to the query-relevant span.

Contextual compression shrinks each retrieved document down to only the spans
that bear on the query, dropping documents with nothing relevant. Less
irrelevant text reaches the synthesis prompt, which improves answer quality and
cuts token cost. Each surviving document keeps its identity keys (``id``,
``score``, ...) so citations survive compression.

Algorithm:
    1. Validate ``query`` (str), ``documents`` (list of Mappings), and ``llm``
       (:class:`LLMProvider`).
    2. For each document, ask the LLM to extract only the query-relevant text,
       or reply ``NONE`` when nothing is relevant.
    3. Drop documents compressed to nothing; for the rest, replace ``text`` with
       the compressed span while preserving all other keys.
    4. Return the surviving compressed documents in input order.

References:
    - Contextual compression retriever (LangChain).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider


class ContextualCompressor(Knot):
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
    ) -> list[Mapping[str, Any]]:
        """Compress each document to its query-relevant span, dropping empties.

        Args:
            query: The query the documents are compressed against.
            documents: The retrieved document mappings to compress.
            llm: The provider performing extraction.

        Returns:
            The surviving compressed documents, preserving identity keys.

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
        compressed: list[Mapping[str, Any]] = []
        for doc in documents:
            text = self._doc_text(doc)
            prompt = (
                "Extract only the sentences from the document that are relevant to the "
                "query. Preserve wording exactly. If nothing is relevant, reply with only "
                f"'NONE'.\n\nQuery: {query}\n\nDocument:\n{text}"
            )
            raw = await llm.chat([{"role": "user", "content": prompt}])
            extracted = self._extract_text(raw).strip()
            if not extracted or extracted.upper() == "NONE":
                continue
            merged = dict(doc)
            merged["text"] = extracted
            merged["compressed"] = True
            compressed.append(merged)
        return compressed

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
