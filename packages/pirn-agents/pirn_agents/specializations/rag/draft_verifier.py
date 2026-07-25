"""``DraftVerifier`` — check a speculative draft against retrieved evidence.

The verification stage of Speculative RAG. It takes the fast draft and the
retrieved documents and asks the LLM to confirm the draft where the evidence
supports it or revise it where it does not, producing the final grounded,
source-citing :class:`AgentResponse`.

Algorithm:
    1. Validate ``query`` (str), ``draft`` (str), and ``llm``
       (:class:`LLMProvider`).
    2. Render the retrieved documents as numbered source blocks.
    3. Prompt the LLM to verify the draft against the sources and emit the
       corrected, citation-bearing answer.
    4. Return the result wrapped as an :class:`AgentResponse`.

References:
    - Wang et al., "Speculative RAG" (2024): https://arxiv.org/abs/2407.08223
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.types.agent_response import AgentResponse


class DraftVerifier(Knot):
    """Verify and, if needed, revise a draft answer against retrieved evidence."""

    def __init__(
        self,
        *,
        query: Knot | str,
        draft: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            draft=draft,
            documents=documents,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        draft: str,
        documents: list[Mapping[str, Any]],
        llm: LLMProvider,
        **_: Any,
    ) -> AgentResponse:
        """Verify ``draft`` against ``documents`` and return the final answer.

        Args:
            query: The original user question.
            draft: The speculative draft answer to verify.
            documents: The retrieved evidence to check the draft against.
            llm: The provider that verifies and revises.

        Returns:
            An :class:`AgentResponse` carrying the verified/revised answer.

        Raises:
            TypeError: If ``query``/``draft`` are not strings or ``llm`` is not
                an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(f"DraftVerifier: query must be a string, got {type(query).__name__}")
        if not isinstance(draft, str):
            raise TypeError(f"DraftVerifier: draft must be a string, got {type(draft).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"DraftVerifier: llm must be an LLMProvider, got {type(llm).__name__}")
        blocks: list[str] = []
        for index, doc in enumerate(documents):
            blocks.append(f"[{index + 1}] {self._doc_text(doc)}")
        context = "\n\n".join(blocks) if blocks else "(no documents retrieved)"
        prompt = (
            "A draft answer was written before sources were consulted. Verify it against "
            "the sources below: keep what they support, correct what they contradict, and "
            "cite the sources you rely on using their bracketed numbers.\n\n"
            f"Question: {query}\n\nDraft answer: {draft}\n\nSources:\n{context}\n\n"
            "Verified answer:"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        return AgentResponse(content=self._extract_text(raw), finish_reason="stop")

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for value in doc.values():
            parts.append(value if isinstance(value, str) else str(value))
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
