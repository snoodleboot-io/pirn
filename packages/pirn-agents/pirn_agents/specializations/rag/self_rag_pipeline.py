"""``SelfRAGPipeline`` — self-reflective retrieval-augmented generation.

Generates an initial answer, then calls the LLM to assess whether
retrieval is needed, retrieves if so, and regenerates a final answer
with the retrieved context.

Stages:

1. :class:`LLMChatCall` (initial) — generate a draft answer to the query.
2. Assess whether retrieval is needed via a second :class:`LLMChatCall`.
3. Conditionally :class:`MemorySearchRetriever` + :class:`RAGPromptBuilder`
   + final :class:`LLMChatCall` when retrieval is needed.
4. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.

Algorithm:
    1. Receive ``query``, ``memory``, ``llm``, and ``top_k``.
    2. Validate inputs: ``query`` string, ``memory`` MemoryStore, ``llm``
       LLMProvider, ``top_k`` positive integer.
    3. Run a first inner tapestry to generate a draft answer.
    4. Run a second inner tapestry to assess (YES/NO) whether retrieval
       would improve the answer.
    5. If YES: run a third inner tapestry that retrieves from ``memory``,
       builds a context-augmented prompt, calls the LLM, and packages
       the result as an :class:`AgentResponse`.
    6. If NO: return the draft answer wrapped in an
       :class:`AgentResponse` directly.

Math:
    No quantitative computation — self-assessment is a binary LLM
    classification step with no numeric scoring.

References:
    - Asai et al., "Self-RAG: Learning to Retrieve, Generate, and
      Critique through Self-Reflection" (NeurIPS 2023):
      https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn_agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn_agents.types.agent_response import AgentResponse


class SelfRAGPipeline(SubTapestry):
    """Generate, self-assess retrieval need, optionally retrieve, then regenerate."""

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
            query=query,
            memory=memory,
            llm=llm,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        top_k: int = 5,
        **_: Any,
    ) -> Any:
        """Generate a draft answer, assess retrieval need, optionally retrieve and regenerate.

        Args:
            query: The user query string to process.
            memory: The MemoryStore to search if retrieval is needed.
            llm: The LLMProvider used for draft generation, assessment, and final answer.
            top_k: The number of top memories to retrieve if retrieval is triggered.

        Returns:
            An AgentResponse containing the final LLM-generated answer.

        Raises:
            TypeError: If query is not a string or memory/llm are wrong types.
            ValueError: If top_k is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(f"SelfRAGPipeline: query must be a string, got {type(query).__name__}")
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"SelfRAGPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SelfRAGPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"SelfRAGPipeline: top_k must be a positive int, got {top_k!r}")
        with Tapestry() as inner_draft:
            LLMChatCall(
                prompt=query,
                llm=llm,
                _config=KnotConfig(id="draft"),
            )
        draft_result = await self._run_inner(inner_draft)
        draft_answer = draft_result.outputs.get("draft", "")

        assess_prompt = (
            "Given the following question and draft answer, decide if "
            "retrieval of additional context is needed to give a more "
            "accurate or complete answer. Reply with only YES or NO.\n\n"
            f"Question: {query}\nDraft answer: {draft_answer}"
        )
        with Tapestry() as inner_assess:
            LLMChatCall(
                prompt=assess_prompt,
                llm=llm,
                _config=KnotConfig(id="assess"),
            )
        assess_result = await self._run_inner(inner_assess)
        assessment = str(assess_result.outputs.get("assess", "")).strip().upper()

        if "YES" in assessment:
            with Tapestry() as inner_rag:
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
            rag_result = await self._run_inner(inner_rag)
            final_response: AgentResponse = rag_result.outputs.get("response") or AgentResponse(
                content="", finish_reason="length"
            )
        else:
            final_response = (
                AgentResponse(content=draft_answer, finish_reason="stop")
                if isinstance(draft_answer, str)
                else AgentResponse(content="", finish_reason="length")
            )

        _resp = final_response

        class _ResultSource(Source):
            async def process(self, **_: Any) -> AgentResponse:
                return _resp

        return _ResultSource(_config=KnotConfig(id="result"))
