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

Algorithm:
    1. Prompt the LLM to sketch a concise hypothetical answer to the
       query via :class:`LLMChatCall` (hypothesis step).
    2. Use the hypothesis text as the search query in
       :class:`MemorySearchRetriever` to retrieve ``top_k`` hits whose
       embeddings cluster near the expected answer space.
    3. Build a final prompt from the retrieved hits and the *original*
       query via :class:`RAGPromptBuilder`.
    4. Generate the actual answer with a second :class:`LLMChatCall`.
    5. Wrap the answer as an :class:`AgentResponse` via
       :class:`RAGResponseBuilder` and return it.

References:
    - HyDE (Hypothetical Document Embeddings): https://arxiv.org/abs/2212.10496
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
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


class HyDERAGPipeline(SubTapestry):
    """Hypothesis-first RAG: draft answer → retrieve → final answer."""

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
    ) -> Any:
        """Generate a hypothetical answer, retrieve on it, then produce the final answer via the LLM.

        Args:
            query: The user query string for which a hypothetical document is first generated.

        Returns:
            An AgentResponse containing the final LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        hypothesis_prompt = (
            "Sketch a concise hypothetical answer to the following question. "
            "Use plausible terminology even if uncertain.\n\n"
            f"Question: {query}\nHypothetical answer:"
        )
        hypothesis = LLMChatCall(
            prompt=hypothesis_prompt,
            llm=llm,
            _config=KnotConfig(id="hypothesis"),
        )
        retrieved = MemorySearchRetriever(
            store=memory,
            query=hypothesis,
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
        return RAGResponseBuilder(
            answer=answer,
            _config=KnotConfig(id="response"),
        )
