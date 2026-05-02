"""``NaiveRAGPipeline`` — straight-line retrieval-augmented generation.

A :class:`SubTapestry` that wires:

1. :class:`MemorySearchRetriever` — fetches top-k memories matching the
   query.
2. :class:`RAGPromptBuilder` — folds the retrieved hits and the query
   into a single prompt string.
3. :class:`LLMChatCall` — generates the answer via the supplied
   :class:`LLMProvider`.
4. :class:`RAGResponseBuilder` — wraps the generated text as an
   :class:`AgentResponse`.

This is the baseline shape; richer variants (HyDE, corrective, graph)
override individual stages but follow the same retrieve-→-prompt-→-
generate-→-package skeleton.
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


class NaiveRAGPipeline(SubTapestry):
    """Retrieve top-k memories, prompt the LLM, return an :class:`AgentResponse`."""

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
                "NaiveRAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "NaiveRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "NaiveRAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._memory = memory
        self._llm = llm
        self._top_k = top_k
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        if not isinstance(query, str):
            raise TypeError(
                "NaiveRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        with Tapestry() as inner:
            retrieved = MemorySearchRetriever(
                store=self._memory,
                query=query,
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
