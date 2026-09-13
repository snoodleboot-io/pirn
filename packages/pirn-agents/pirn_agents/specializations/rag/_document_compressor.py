"""``_DocumentCompressor`` — extract one document's query-relevant span."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
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
