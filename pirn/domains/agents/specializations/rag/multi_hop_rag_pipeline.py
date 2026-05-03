"""``MultiHopRAGPipeline`` — multi-hop retrieval-augmented generation.

Decomposes the question into sub-questions, retrieves context for each,
then synthesizes a final answer across all retrieved contexts.

Stages:

1. :class:`LLMChatCall` (decompose) — produce N sub-questions from the query.
2. For each sub-question: :class:`MemorySearchRetriever` — top-k hits.
3. :class:`RAGPromptBuilder` — fold all collected hits + original query.
4. :class:`LLMChatCall` (synthesize) — produce the final answer.
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


class MultiHopRAGPipeline(SubTapestry):
    """Decompose question, retrieve per sub-question, synthesize final answer."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: MemoryStore,
        llm: LLMProvider,
        _config: KnotConfig,
        top_k: int = 5,
        num_hops: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                "MultiHopRAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "MultiHopRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "MultiHopRAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        if not isinstance(num_hops, int) or num_hops <= 0:
            raise ValueError(
                "MultiHopRAGPipeline: num_hops must be a positive int, "
                f"got {num_hops!r}"
            )
        self._memory = memory
        self._llm = llm
        self._top_k = top_k
        self._num_hops = num_hops
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        """Decompose the query, retrieve context per sub-question, and synthesize a final answer.

        Args:
            query: The user query string to decompose and answer via multi-hop retrieval.

        Returns:
            An AgentResponse containing the synthesized final answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "MultiHopRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        decompose_prompt = (
            f"Decompose the following question into exactly {self._num_hops} "
            "concise sub-questions, one per line, with no numbering or bullets.\n\n"
            f"Question: {query}"
        )
        with Tapestry() as inner_decompose:
            LLMChatCall(
                prompt=decompose_prompt,
                llm=self._llm,
                _config=KnotConfig(id="decompose"),
            )
        decompose_result = await self._run_inner(inner_decompose)
        sub_questions_raw = str(decompose_result.outputs.get("decompose", query))
        sub_questions = [
            line.strip()
            for line in sub_questions_raw.splitlines()
            if line.strip()
        ][: self._num_hops]
        if not sub_questions:
            sub_questions = [query]

        all_hits: list[Any] = []
        for sub_q in sub_questions:
            with Tapestry() as inner_retrieve:
                MemorySearchRetriever(
                    store=self._memory,
                    query=sub_q,
                    top_k=self._top_k,
                    _config=KnotConfig(id="sub_retrieve"),
                )
            sub_result = await self._run_inner(inner_retrieve)
            hits = sub_result.outputs.get("sub_retrieve", [])
            if isinstance(hits, list):
                all_hits.extend(hits)

        with Tapestry() as inner_synth:
            prompt_knot = RAGPromptBuilder(
                query=query,
                retrieved=all_hits,
                _config=KnotConfig(id="prompt"),
            )
            answer_knot = LLMChatCall(
                prompt=prompt_knot,
                llm=self._llm,
                _config=KnotConfig(id="generate"),
            )
            RAGResponseBuilder(
                answer=answer_knot,
                _config=KnotConfig(id="response"),
            )
        synth_result = await self._run_inner(inner_synth)
        response = synth_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
