# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``ComplexRagArm`` — the multi-hop decomposition arm, gated behind route selection.

Wrapped as its own :class:`~pirn.nodes.sub_tapestry.SubTapestry` so the engine
can skip *calling* it entirely, rather than merely discarding its result:
``route_gate`` is an implicit dependency (not declared on ``process()``, so it
plays no role beyond wiring — see ``Knot.__init__``'s "implicit dependencies"
support) on the ``simple``/``complex`` :class:`~pirn.nodes.branch.branch.Branch`
arm this knot is wired under in
:class:`~pirn_agents.specializations.rag.adaptive_rag_pipeline.AdaptiveRAGPipeline`.
When that arm is not selected, ``route_gate`` resolves to ``Skipped``, and a
``SubTapestry`` (like any knot) is never invoked when one of its parents —
declared or implicit — is ``Skipped``: its own decompose LLM call, the
per-sub-question retrievals, and the final generation call all go unpaid for
(ADR agents-speaks-core WS5b).

Only the classification step's inner run needed this treatment: the moderate
and simple arms need no dynamic fan-out, so their own entry knots take
``route_gate`` directly (see ``AdaptiveRAGPipeline``) without needing a
dedicated wrapper class.

Internal API. See PIR-856.
"""

from __future__ import annotations

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
from pirn_agents.specializations.rag.memory_search_retriever import MemorySearchRetriever
from pirn_agents.specializations.rag.rag_prompt_builder import RAGPromptBuilder
from pirn_agents.specializations.rag.rag_response_builder import RAGResponseBuilder


class ComplexRagArm(AgentPipeline):
    """Decompose into sub-questions, retrieve per sub-question, then answer."""

    _decompose_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.adaptive_rag_pipeline.decompose_prompt",
        default=(
            "Decompose the following question into exactly three concise "
            "sub-questions, one per line, no numbering or bullets.\n\n"
            "Question: {{ query }}"
        ),
    )

    def __init__(
        self,
        *,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        top_k: int,
        route_gate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            top_k=top_k,
            route_gate=route_gate,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _merge_hits(**per_question: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Flatten the per-sub-question retrieval results into one hit list.

        Each keyword is one ``MemorySearchRetriever``'s hit list, named
        ``hits_<index>``; the lists are concatenated in sub-question order.
        """
        merged: list[Mapping[str, Any]] = []
        for key in sorted(per_question, key=lambda name: int(name.rsplit("_", 1)[1])):
            hits = per_question[key]
            if isinstance(hits, list):
                merged.extend(hits)
        return merged

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        top_k: int,
        **_: Any,
    ) -> Knot:
        """Decompose, retrieve per sub-question, and answer.

        Args:
            query: The original user query.
            memory: Store searched per sub-question.
            llm: Provider used for decomposition and the final answer.
            top_k: Hits retrieved per sub-question.

        Returns:
            The sink knot whose output is the :class:`AgentResponse`.
        """
        decompose_prompt = type(self)._decompose_prompt.render({"query": query})
        with Tapestry() as inner_decompose:
            LLMChatCall(
                prompt=decompose_prompt,
                llm=llm,
                _config=KnotConfig(id="decompose"),
            )
        decompose_result = await self._run_inner(inner_decompose)
        sub_questions_raw = str(decompose_result.outputs.get("decompose", query))
        sub_questions = [line.strip() for line in sub_questions_raw.splitlines() if line.strip()][
            :3
        ]
        if not sub_questions:
            sub_questions = [query]

        retrievers = {
            f"hits_{index}": MemorySearchRetriever(
                store=memory,
                query=sub_q,
                top_k=top_k,
                _config=KnotConfig(id=f"sub_retrieve_{index}"),
            )
            for index, sub_q in enumerate(sub_questions)
        }
        merged = Aggregator(
            combine=ComplexRagArm._merge_hits,
            _config=KnotConfig(id="merge"),
            **retrievers,
        )
        prompt_knot = RAGPromptBuilder(
            query=query,
            retrieved=merged,
            _config=KnotConfig(id="prompt"),
        )
        answer_knot = LLMChatCall(
            prompt=prompt_knot,
            llm=llm,
            _config=KnotConfig(id="generate"),
        )
        return RAGResponseBuilder(answer=answer_knot, _config=KnotConfig(id="response"))
