"""``MultiHopRAGPipeline`` — multi-hop retrieval-augmented generation.

Decomposes the question into sub-questions, retrieves context for each,
then synthesizes a final answer across all retrieved contexts.

Stages:

1. :class:`LLMChatCall` (decompose) — produce N sub-questions from the query.
2. For each sub-question: :class:`MemorySearchRetriever` — top-k hits.
3. :class:`RAGPromptBuilder` — fold all collected hits + original query.
4. :class:`LLMChatCall` (synthesize) — produce the final answer.
5. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.

Algorithm:
    1. Prompt the LLM to decompose the query into exactly ``num_hops``
       sub-questions (one per line) via :class:`LLMChatCall`.
    2. Parse the response into at most ``num_hops`` non-empty lines;
       fall back to ``[query]`` if parsing yields nothing.
    3. For each sub-question, retrieve ``top_k`` hits from ``memory``
       via :class:`MemorySearchRetriever` in separate inner tapestries;
       accumulate all hits into a single list.
    4. Build a unified prompt from the original query and all accumulated
       hits via :class:`RAGPromptBuilder`.
    5. Generate the final synthesized answer with :class:`LLMChatCall`.
    6. Wrap the answer as an :class:`AgentResponse` via
       :class:`RAGResponseBuilder` and return it.

References:
    - Multi-hop RAG: https://arxiv.org/abs/2402.03367
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn_agents.specializations.rag.multi_hop_result_extractor import (
    MultiHopResultExtractor,
)
from pirn_agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)


class MultiHopRAGPipeline(AgentPipeline):
    """Decompose question, retrieve per sub-question, synthesize final answer."""

    _decompose_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.multi_hop_rag_pipeline.decompose_prompt",
        default=(
            "Decompose the following question into exactly {{ num_hops }} "
            "concise sub-questions, one per line, with no numbering or bullets.\n\n"
            "Question: {{ query }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        num_hops: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            top_k=top_k,
            num_hops=num_hops,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, query: str, memory: MemoryStore, llm: LLMProvider, top_k: int, num_hops: int, **_: Any
    ) -> Knot:
        """Decompose the query, retrieve context per sub-question, and synthesize a final answer.

        Args:
            query: The user query string to decompose and answer via multi-hop retrieval.

        Returns:
            An AgentResponse containing the synthesized final answer.

        Raises:
            TypeError: If query is not a string.
        """
        decompose_prompt = type(self)._decompose_prompt.render(
            {"num_hops": num_hops, "query": query}
        )
        with Tapestry() as inner_decompose:
            LLMChatCall(
                prompt=decompose_prompt,
                llm=llm,
                _config=KnotConfig(id="decompose"),
            )
        decompose_result = await self._run_inner(inner_decompose)
        sub_questions_raw = str(decompose_result.outputs.get("decompose", query))
        sub_questions = [line.strip() for line in sub_questions_raw.splitlines() if line.strip()][
            :num_hops
        ]
        if not sub_questions:
            sub_questions = [query]

        # One run, not one per hop: the sub-questions are independent retrievals,
        # so they are siblings of an Aggregator and the engine runs them
        # concurrently (knot-design-rules Rule 11; PIR-874). A run per hop made
        # each hop's lineage an unrelated run and paid a round trip for each.
        with Tapestry() as inner_retrieve:
            per_hop: dict[str, Knot] = {
                f"hop_{index}": MemorySearchRetriever(
                    store=memory,
                    query=sub_q,
                    top_k=top_k,
                    _config=KnotConfig(id=f"hop_{index}"),
                )
                for index, sub_q in enumerate(sub_questions)
            }
            Aggregator(
                combine=functools.partial(MultiHopRAGPipeline._merge_hits, tuple(per_hop)),
                _config=KnotConfig(id="sub_retrieve"),
                **per_hop,
            )
        sub_result = await self._run_inner(inner_retrieve)
        all_hits: list[Any] = list(sub_result.outputs.get("sub_retrieve", []))

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
        raw = synth_result.outputs.get("response")
        return MultiHopResultExtractor(raw=raw, _config=KnotConfig(id="result"))

    @staticmethod
    def _merge_hits(
        order: tuple[str, ...], **hops: list[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        """Concatenate every hop's hits in sub-question order.

        The hops finish in any order once the engine runs them concurrently, so
        ``order`` fixes the sequence rather than arrival deciding it.

        Args:
            order: The hop keys, in sub-question order.
            hops: Each hop's hits, keyed by its knot id.

        Returns:
            Every hop's hits, concatenated.
        """
        merged: list[Mapping[str, Any]] = []
        for key in order:
            hits = hops.get(key)
            if isinstance(hits, list):
                merged.extend(hits)
        return merged
