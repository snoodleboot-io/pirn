"""``HyDERAGPipeline`` — Hypothetical Document Embeddings RAG.

Two-pass retrieval: the LLM first sketches a *hypothetical* answer, the
sketch is used as the search query (embedding-space hits cluster around
the answer rather than the question), and a second LLM call produces
the actual answer over the retrieved hits plus the original question.

Stages composed inside the inner :class:`Tapestry`:

1. :class:`LLMChatCall` (hypothesis) — generate a draft answer.
2. :class:`MemorySearchRetriever` — top-k search over the hypothesis.
3. :class:`RAGPromptBuilder` — combine retrieved hits with the original
   query.
4. :class:`LLMChatCall` (final) — produce the actual answer.
5. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn.domains.agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn.domains.agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn.domains.agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class HyDERAGPipeline(SubTapestry):
    """Hypothesis-first RAG: draft answer → retrieve → final answer."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: MemoryStore,
        llm: LLMProvider,
        _config: KnotConfig,
        top_k: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                "HyDERAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "HyDERAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "HyDERAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._memory = memory
        self._llm = llm
        self._top_k = top_k
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        """Generate a hypothetical answer, retrieve on it, then produce the final answer via the LLM.

        Args:
            query: The user query string for which a hypothetical document is first generated.

        Returns:
            An AgentResponse containing the final LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "HyDERAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        hypothesis_prompt = (
            "Sketch a concise hypothetical answer to the following question. "
            "Use plausible terminology even if uncertain.\n\n"
            f"Question: {query}\nHypothetical answer:"
        )
        with Tapestry() as inner:
            hypothesis = LLMChatCall(
                prompt=hypothesis_prompt,
                llm=self._llm,
                _config=KnotConfig(id="hypothesis"),
            )
            retrieved = MemorySearchRetriever(
                store=self._memory,
                query=hypothesis,
                top_k=self._top_k,
                _config=KnotConfig(id="retrieve"),
            )
            prompt = RAGPromptBuilder(
                query=query,
                retrieved=retrieved,
                _config=KnotConfig(id="prompt"),
            )
            answer = LLMChatCall(
                prompt=prompt,
                llm=self._llm,
                _config=KnotConfig(id="generate"),
            )
            RAGResponseBuilder(
                answer=answer,
                _config=KnotConfig(id="response"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
