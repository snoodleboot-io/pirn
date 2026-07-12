"""``SpeculativeRagPipeline`` — draft while retrieving, then verify.

A :class:`SubTapestry` that wires two **independent** branches which the engine
runs concurrently, then joins them:

1. :class:`SpeculativeDraftGenerator` — draft an answer from the query alone.
2. :class:`MemorySearchRetriever` — retrieve evidence for the query.
3. :class:`DraftVerifier` — verify the draft against the retrieved evidence and
   emit the final grounded :class:`AgentResponse`.

Because the draft does not depend on retrieval, its latency is hidden behind the
retrieval latency; the verify pass then adds grounding without a second full
generation from scratch.

References:
    - Wang et al., "Speculative RAG" (2024): https://arxiv.org/abs/2407.08223
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.draft_verifier import DraftVerifier
from pirn_agents.specializations.rag.memory_search_retriever import MemorySearchRetriever
from pirn_agents.specializations.rag.speculative_draft_generator import SpeculativeDraftGenerator


class SpeculativeRagPipeline(SubTapestry):
    """Draft concurrently with retrieval, then verify the draft against evidence."""

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
        """Wire the concurrent draft + retrieval branches into verification.

        Args:
            query: The user query to draft, retrieve for, and verify.
            memory: The memory store searched for evidence.
            llm: The provider used for drafting and verification.
            top_k: Number of evidence documents retrieved.

        Returns:
            The :class:`DraftVerifier` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SpeculativeRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"SpeculativeRagPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SpeculativeRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        draft = SpeculativeDraftGenerator(
            query=query,
            llm=llm,
            _config=KnotConfig(id="draft"),
        )
        retrieved = MemorySearchRetriever(
            store=memory,
            query=query,
            top_k=top_k,
            _config=KnotConfig(id="retrieve"),
        )
        return DraftVerifier(
            query=query,
            draft=draft,
            documents=retrieved,
            llm=llm,
            _config=KnotConfig(id="verify"),
        )
