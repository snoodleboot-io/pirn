"""``FlareActiveRagPipeline`` — forward-looking active retrieval (FLARE).

FLARE generates the answer one sentence at a time. Each candidate sentence comes
with a confidence; when a sentence is low-confidence, the pipeline pauses, uses
that tentative sentence as a search query, retrieves evidence, and regenerates
the sentence grounded in what it found — retrieving *forward* only when the model
is unsure. Retrieval calls are hard-bounded by ``max_retrieval_calls``.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), and the numeric budgets.
    2. Drive the rounds with a
       :class:`~pirn_agents.specializations.rag._flare_loop.FlareLoop`
       (``LoopSubTapestry``): each round's generation call is a real,
       individually-traceable knot, and the conditional retrieval +
       regeneration call is gated by a core
       :class:`~pirn.nodes.check.Check`/:class:`~pirn.nodes.gate.gate.Gate`
       pair rather than a Python ``if`` inside a hand-rolled loop (ADR
       agents-speaks-core WS5b).
    3. Extract the assembled answer as an :class:`AgentResponse` with
       :class:`~pirn_agents.specializations.rag._flare_result_extractor.FlareResultExtractor`.

References:
    - Jiang et al., "Active Retrieval Augmented Generation" (FLARE, EMNLP 2023):
      https://arxiv.org/abs/2305.06983
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pydantic import PositiveInt

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag._flare_loop import FlareLoop
from pirn_agents.specializations.rag._flare_result_extractor import FlareResultExtractor
from pirn_agents.specializations.rag._flare_state import FlareState


class FlareActiveRagPipeline(AgentPipeline):
    """Generate sentence-by-sentence, retrieving forward on low confidence."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        confidence_threshold: Knot | float = 0.5,
        max_sentences: Knot | int = 5,
        max_retrieval_calls: Knot | int = 3,
        top_k: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            confidence_threshold=confidence_threshold,
            max_sentences=max_sentences,
            max_retrieval_calls=max_retrieval_calls,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        confidence_threshold: float = 0.5,
        max_sentences: PositiveInt = 5,
        max_retrieval_calls: PositiveInt = 3,
        top_k: PositiveInt = 3,
        **_: Any,
    ) -> Knot:
        """Run the FLARE loop and return the assembled answer as a source knot.

        Args:
            query: The question to answer.
            memory: The memory store searched on low-confidence sentences.
            llm: The provider generating and regenerating sentences.
            confidence_threshold: Confidence below which retrieval fires.
            max_sentences: Hard cap on generated sentences.
            max_retrieval_calls: Hard cap on retrieval calls.
            top_k: Hits fetched per retrieval.

        Returns:
            The sink knot whose output is the final :class:`AgentResponse`.
        """
        initial = Parameter(
            "flare_state",
            FlareState,
            default=FlareState(parts=(), retrieval_calls=0, done=False, index=0),
        )
        loop = FlareLoop(
            query=query,
            memory=memory,
            llm=llm,
            confidence_threshold=float(confidence_threshold),
            max_sentences=int(max_sentences),
            max_retrieval_calls=int(max_retrieval_calls),
            top_k=int(top_k),
            state=initial,
            _config=KnotConfig(id="flare_loop"),
        )
        return FlareResultExtractor(state=loop, _config=KnotConfig(id="result"))
