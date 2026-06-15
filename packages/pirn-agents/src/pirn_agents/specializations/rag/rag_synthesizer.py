"""``RAGSynthesizer`` — synthesize a grounded answer from retrieved documents.

Takes retrieved documents plus the original query, calls the LLM to produce
an answer that cites source passages, and returns an :class:`AgentResponse`.

Algorithm:
    1. Receive ``query`` string and ``documents`` list of Mappings.
    2. Validate that ``query`` is a string.
    3. For each document, extract its textual content into ``[i] text``
       blocks (1-indexed).
    4. Join blocks as ``Sources`` context, or use
       ``"(no documents retrieved)"`` when the list is empty.
    5. Assemble a citation-prompting system message and call the LLM.
    6. Extract the text from the raw LLM response and return it wrapped
       in an :class:`AgentResponse` with ``finish_reason="stop"``.

Math:
    No quantitative computation — grounding is a pure text-assembly and
    LLM-call operation.

References:
    - Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive
      NLP Tasks" (NeurIPS 2020): https://arxiv.org/abs/2005.11401
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.types.agent_response import AgentResponse


class RAGSynthesizer(Knot):
    """Synthesize a grounded answer from retrieved documents + query."""

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
    ) -> AgentResponse:
        """Synthesize a grounded answer from retrieved documents and return it as an AgentResponse.

        Args:
            query: The original user query to answer.
            documents: The list of retrieved document Mappings to use as context.
            llm: The LLMProvider used to generate the synthesized answer.

        Returns:
            An AgentResponse containing the synthesized, source-citing answer.

        Raises:
            TypeError: If query is not a string or llm is not an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(f"RAGSynthesizer: query must be a string, got {type(query).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"RAGSynthesizer: llm must be an LLMProvider, got {type(llm).__name__}")
        doc_blocks: list[str] = []
        for index, doc in enumerate(documents):
            text = self._doc_text(doc)
            doc_blocks.append(f"[{index + 1}] {text}")
        context = "\n\n".join(doc_blocks) if doc_blocks else "(no documents retrieved)"
        prompt = (
            "Answer the following question using only the provided source "
            "passages. Cite each passage you draw on using its bracketed "
            "number (e.g. [1]).\n\n"
            f"Question: {query}\n\n"
            f"Sources:\n{context}\n\n"
            "Answer:"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        content = self._extract_text(raw)
        return AgentResponse(content=content, finish_reason="stop")

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for value in doc.values():
            if isinstance(value, str):
                parts.append(value)
            else:
                parts.append(str(value))
        return " ".join(parts)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
