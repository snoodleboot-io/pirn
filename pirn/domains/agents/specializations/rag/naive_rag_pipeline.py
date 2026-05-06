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

Algorithm:
    1. Receive a ``query`` string.
    2. Wire a :class:`MemorySearchRetriever` to fetch the ``top_k`` nearest
       memories from the :class:`MemoryStore`.
    3. Wire a :class:`RAGPromptBuilder` to merge the query and retrieved
       hits into a single context-augmented prompt string.
    4. Wire a :class:`LLMChatCall` to generate an answer from the prompt.
    5. Wire a :class:`RAGResponseBuilder` to package the raw answer as an
       :class:`AgentResponse`.
    6. Run the inner :class:`Tapestry` and return the ``AgentResponse``.

Math:
    No quantitative computation — top-k retrieval and prompt assembly are
    string operations delegated entirely to the wired child knots.

References:
    - Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive
      NLP Tasks" (NeurIPS 2020): https://arxiv.org/abs/2005.11401
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
    ) -> AgentResponse:
        """Retrieve top-k memories, build a prompt, generate an answer, and return it as an AgentResponse.

        Args:
            query: The user query string to retrieve context for and answer.
            memory: The MemoryStore to search for relevant entries.
            llm: The LLMProvider used to generate the answer.
            top_k: The number of top memories to retrieve.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string or memory/llm are wrong types.
            ValueError: If top_k is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                "NaiveRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
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
        with Tapestry() as inner:
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
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
