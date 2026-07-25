"""``SubQuestionRagPipeline`` — decompose → per-sub-question retrieve → synthesize.

A :class:`SubTapestry` that wires:

1. :class:`SubQuestionDecomposer` — split the compound query into sub-questions.
2. :class:`SubQuestionRetriever` — retrieve for every sub-question concurrently
   and union the deduplicated hits.
3. :class:`RAGSynthesizer` — synthesize one grounded answer to the **original**
   query over the combined evidence.

Decomposition raises recall on compound questions: each facet is retrieved
independently, so evidence that a single blended query would rank too low still
reaches synthesis.

References:
    - Khattab et al., "Demonstrate-Search-Predict" (2022):
      https://arxiv.org/abs/2212.14024
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.sub_question_decomposer import SubQuestionDecomposer
from pirn_agents.specializations.rag.sub_question_retriever import SubQuestionRetriever


class SubQuestionRagPipeline(SubTapestry):
    """Decompose the query, retrieve per sub-question, then synthesize one answer."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_sub_questions: Knot | int = 4,
        top_k: Knot | int = 3,
        max_concurrency: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            max_sub_questions=max_sub_questions,
            top_k=top_k,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        max_sub_questions: int = 4,
        top_k: int = 3,
        max_concurrency: int = 4,
        **_: Any,
    ) -> Any:
        """Wire decomposition → per-sub-question retrieval → synthesis.

        Args:
            query: The compound user query to decompose and answer.
            memory: The memory store searched per sub-question.
            llm: The provider used for decomposition and synthesis.
            max_sub_questions: Upper bound on the number of sub-questions.
            top_k: Number of hits fetched per sub-question.
            max_concurrency: Maximum concurrent sub-question searches.

        Returns:
            The :class:`RAGSynthesizer` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SubQuestionRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"SubQuestionRagPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SubQuestionRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        sub_questions = SubQuestionDecomposer(
            query=query,
            llm=llm,
            max_sub_questions=max_sub_questions,
            _config=KnotConfig(id="decompose"),
        )
        documents = SubQuestionRetriever(
            sub_questions=sub_questions,
            store=memory,
            top_k=top_k,
            max_concurrency=max_concurrency,
            _config=KnotConfig(id="retrieve"),
        )
        return RAGSynthesizer(
            query=query,
            documents=documents,
            llm=llm,
            _config=KnotConfig(id="synthesize"),
        )
