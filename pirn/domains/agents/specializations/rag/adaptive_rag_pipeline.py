"""``AdaptiveRAGPipeline`` — complexity-routed retrieval-augmented generation.

Classifies the query as simple, moderate, or complex via an LLM call, then
routes to:

- **simple** — direct :class:`LLMChatCall` with no retrieval.
- **moderate** — naive single-hop :class:`MemorySearchRetriever` + answer.
- **complex** — multi-hop decomposition (three sub-questions), retrieval per
  sub-question, merged context, then final answer.
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


class AdaptiveRAGPipeline(SubTapestry):
    """Classify query complexity, then route to naive RAG, multi-hop RAG, or direct LLM."""

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
                "AdaptiveRAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "AdaptiveRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "AdaptiveRAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._memory = memory
        self._llm = llm
        self._top_k = top_k
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        """Classify query complexity and route to the appropriate RAG strategy.

        Args:
            query: The user query string to classify and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "AdaptiveRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        classify_prompt = (
            "Classify the complexity of the following question as one of: "
            "SIMPLE, MODERATE, or COMPLEX. "
            "SIMPLE means it can be answered directly without external context. "
            "MODERATE means a single retrieval step suffices. "
            "COMPLEX means it requires multiple reasoning steps or sub-questions. "
            "Reply with only the single word.\n\n"
            f"Question: {query}"
        )
        with Tapestry() as inner_classify:
            LLMChatCall(
                prompt=classify_prompt,
                llm=self._llm,
                _config=KnotConfig(id="classify"),
            )
        classify_result = await self._run_inner(inner_classify)
        complexity = str(classify_result.outputs.get("classify", "")).strip().upper()

        if "SIMPLE" in complexity:
            with Tapestry() as inner_direct:
                answer = LLMChatCall(
                    prompt=query,
                    llm=self._llm,
                    _config=KnotConfig(id="generate"),
                )
                RAGResponseBuilder(
                    answer=answer,
                    _config=KnotConfig(id="response"),
                )
            result = await self._run_inner(inner_direct)
            response = result.outputs.get("response")
            if not isinstance(response, AgentResponse):
                return AgentResponse(content="", finish_reason="length")
            return response

        if "COMPLEX" in complexity:
            decompose_prompt = (
                "Decompose the following question into exactly three concise "
                "sub-questions, one per line, no numbering or bullets.\n\n"
                f"Question: {query}"
            )
            with Tapestry() as inner_decompose:
                LLMChatCall(
                    prompt=decompose_prompt,
                    llm=self._llm,
                    _config=KnotConfig(id="decompose"),
                )
            decompose_result = await self._run_inner(inner_decompose)
            sub_questions_raw = str(
                decompose_result.outputs.get("decompose", query)
            )
            sub_questions = [
                line.strip()
                for line in sub_questions_raw.splitlines()
                if line.strip()
            ][:3]
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

        with Tapestry() as inner_naive:
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
        naive_result = await self._run_inner(inner_naive)
        response = naive_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
