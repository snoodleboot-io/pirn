"""``AdaptiveRAGPipeline`` — complexity-routed retrieval-augmented generation.

Classifies the query as simple, moderate, or complex via an LLM call, then
routes to:

- **simple** — direct :class:`LLMChatCall` with no retrieval.
- **moderate** — naive single-hop :class:`MemorySearchRetriever` + answer.
- **complex** — multi-hop decomposition (three sub-questions), retrieval per
  sub-question, merged context, then final answer.

Algorithm:
    1. Call the LLM with a classification prompt; expect one of SIMPLE,
       MODERATE, or COMPLEX in the response.
    2. **SIMPLE branch** — run a single :class:`LLMChatCall` directly on the
       query and wrap the result via :class:`RAGResponseBuilder`.
    3. **COMPLEX branch** — ask the LLM to decompose the query into three
       sub-questions; retrieve ``top_k`` hits per sub-question via
       :class:`MemorySearchRetriever`; merge all hits; build a prompt with
       :class:`RAGPromptBuilder`; call the LLM; wrap via
       :class:`RAGResponseBuilder`.
    4. **MODERATE branch** (default) — retrieve ``top_k`` hits for the
       original query; build prompt; call LLM; wrap via
       :class:`RAGResponseBuilder`.
    5. Return the :class:`AgentResponse` from the selected branch.

References:
    - Adaptive RAG: https://arxiv.org/abs/2403.14403
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
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query, memory=memory, llm=llm, top_k=top_k, _config=_config, **kwargs
        )

    async def process(
        self, query: str, memory: MemoryStore, llm: LLMProvider, top_k: int, **_: Any
    ) -> AgentResponse:
        """Classify query complexity and route to the appropriate RAG strategy.

        Args:
            query: The user query string to classify and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
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
                llm=llm,
                _config=KnotConfig(id="classify"),
            )
        classify_result = await self._run_inner(inner_classify)
        complexity = str(classify_result.outputs.get("classify", "")).strip().upper()

        if "SIMPLE" in complexity:
            with Tapestry() as inner_direct:
                answer = LLMChatCall(
                    prompt=query,
                    llm=llm,
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
                    llm=llm,
                    _config=KnotConfig(id="decompose"),
                )
            decompose_result = await self._run_inner(inner_decompose)
            sub_questions_raw = str(decompose_result.outputs.get("decompose", query))
            sub_questions = [
                line.strip() for line in sub_questions_raw.splitlines() if line.strip()
            ][:3]
            if not sub_questions:
                sub_questions = [query]

            all_hits: list[Any] = []
            for sub_q in sub_questions:
                with Tapestry() as inner_retrieve:
                    MemorySearchRetriever(
                        store=memory,
                        query=sub_q,
                        top_k=top_k,
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
                    llm=llm,
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
                store=memory,
                query=query,
                top_k=top_k,
                _config=KnotConfig(id="retrieve"),
            )
            prompt = RAGPromptBuilder(
                query=query,
                retrieved=retrieved,
                _config=KnotConfig(id="prompt"),
            )
            answer = LLMChatCall(
                prompt=prompt,
                llm=llm,
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
