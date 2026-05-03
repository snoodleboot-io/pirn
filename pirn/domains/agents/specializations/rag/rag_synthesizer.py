"""``RAGSynthesizer`` — synthesize a grounded answer from retrieved documents.

Takes retrieved documents plus the original query, calls the LLM to produce
an answer that cites source passages, and returns an :class:`AgentResponse`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class RAGSynthesizer(Knot):
    """Synthesize a grounded answer from retrieved documents + query."""

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "RAGSynthesizer: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(
            query=query,
            documents=documents,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        **_: Any,
    ) -> AgentResponse:
        """Synthesize a grounded answer from retrieved documents and return it as an AgentResponse.

        Args:
            query: The original user query to answer.
            documents: The list of retrieved document Mappings to use as context.

        Returns:
            An AgentResponse containing the synthesized, source-citing answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "RAGSynthesizer: query must be a string, "
                f"got {type(query).__name__}"
            )
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
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
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
