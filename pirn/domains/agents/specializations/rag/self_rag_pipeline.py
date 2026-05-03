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


class SelfRAGPipeline(SubTapestry):
    """Generate, self-assess retrieval need, optionally retrieve, then regenerate."""

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
                "SelfRAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SelfRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "SelfRAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._memory = memory
        self._llm = llm
        self._top_k = top_k
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        """Generate a draft answer, assess retrieval need, optionally retrieve and regenerate.

        Args:
            query: The user query string to process.

        Returns:
            An AgentResponse containing the final LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "SelfRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        with Tapestry() as inner_draft:
            LLMChatCall(
                prompt=query,
                llm=self._llm,
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
                llm=self._llm,
                _config=KnotConfig(id="assess"),
            )
        assess_result = await self._run_inner(inner_assess)
        assessment = str(assess_result.outputs.get("assess", "")).strip().upper()

        if "YES" in assessment:
            with Tapestry() as inner_rag:
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
            rag_result = await self._run_inner(inner_rag)
            response = rag_result.outputs.get("response")
            if not isinstance(response, AgentResponse):
                return AgentResponse(content="", finish_reason="length")
            return response

        if not isinstance(draft_answer, str):
            return AgentResponse(content="", finish_reason="length")
        return AgentResponse(content=draft_answer, finish_reason="stop")
