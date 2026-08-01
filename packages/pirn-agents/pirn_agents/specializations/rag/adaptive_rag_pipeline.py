"""``AdaptiveRAGPipeline`` — complexity-routed retrieval-augmented generation.

Classifies the query as simple, moderate, or complex via an LLM call, then
routes to:

- **simple** — direct :class:`LLMChatCall` with no retrieval.
- **moderate** — naive single-hop :class:`MemorySearchRetriever` + answer.
- **complex** — multi-hop decomposition (three sub-questions), retrieval per
  sub-question, merged context, then final answer.

Algorithm:
    1. Call the LLM with a classification prompt; expect one of SIMPLE,
       MODERATE, or COMPLEX in the response. Resolve the reply to an arm with
       :func:`_select_complexity_route`, which prefers an exact match and
       falls back to a most-specific-first substring test.
    2. **SIMPLE branch** — run a single :class:`LLMChatCall` directly on the
       query and wrap the result via :class:`RAGResponseBuilder`.
    3. **COMPLEX branch** — ask the LLM to decompose the query into three
       sub-questions; retrieve ``top_k`` hits per sub-question via one
       :class:`MemorySearchRetriever` each, merged by an :class:`Aggregator`
       so the retrievals are engine-scheduled siblings rather than a Python
       loop; build a prompt with :class:`RAGPromptBuilder`; call the LLM; wrap
       via :class:`RAGResponseBuilder`.
    4. **MODERATE branch** (default) — retrieve ``top_k`` hits for the
       original query; build prompt; call LLM; wrap via
       :class:`RAGResponseBuilder`.
    5. Return the selected arm's sink knot. Every arm is built into the inner
       tapestry ``SubTapestry.__call__`` already opened, so its knots belong to
       the run this pipeline reports; only ``classify`` and (on the COMPLEX
       path) ``decompose`` need their own inner run, because their values are
       required in Python before the rest of the graph can be built.

References:
    - Adaptive RAG: https://arxiv.org/abs/2403.14403
"""

from __future__ import annotations

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
from pirn_agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)

_ROUTE_SIMPLE = "simple"
_ROUTE_MODERATE = "moderate"
_ROUTE_COMPLEX = "complex"


def _merge_hits(**per_question: Any) -> list[Any]:
    """Flatten the per-sub-question retrieval results into one hit list.

    Used as an :class:`Aggregator` combine so the multi-hop retrievals are
    engine-scheduled siblings rather than a Python loop. Module-level and plain
    (not a closure) so the aggregator carries no captured state.

    Args:
        **per_question: One resolved retriever output per sub-question, keyed
            ``hits_0``, ``hits_1``, … Sorted by key so the merged order follows
            sub-question order regardless of completion order.

    Returns:
        The concatenated hits.
    """
    merged: list[Any] = []
    for key in sorted(per_question, key=lambda name: int(name.rsplit("_", 1)[1])):
        hits = per_question[key]
        if isinstance(hits, list):
            merged.extend(hits)
    return merged


def _select_complexity_route(complexity: str) -> str:
    """Map a classifier reply to the name of the arm that should answer it.

    The classification prompt asks for a single bare word, so an exact match
    is tried first and the well-behaved reply never depends on substring
    semantics at all. Padded replies are common enough to need a fallback,
    and that fallback tests COMPLEX before SIMPLE.

    The ordering is load-bearing. Both fallback tests are substring tests, so
    a reply naming *both* labels — ``"COMPLEX (not simple)"`` — matches either
    one, and whichever is tried first wins. Substring matching cannot resolve
    that, and neither can whole-word matching; the reply is genuinely
    ambiguous. COMPLEX is chosen because the two mistakes are not
    symmetrical: routing a simple query through multi-hop costs latency and
    tokens, whereas routing a complex query to the direct arm returns a wrong
    answer with ``succeeded=True``. Before PIR-770 SIMPLE was tried first, so
    the ladder failed in the expensive direction.

    An unrecognised reply routes to MODERATE. That is the documented default,
    not a consequence of the ordering.

    Args:
        complexity: The classifier reply, already stripped and upper-cased.

    Returns:
        One of ``"simple"``, ``"moderate"`` or ``"complex"``.
    """
    if complexity == "COMPLEX":
        return _ROUTE_COMPLEX
    if complexity == "SIMPLE":
        return _ROUTE_SIMPLE
    if complexity == "MODERATE":
        return _ROUTE_MODERATE
    if "COMPLEX" in complexity:
        return _ROUTE_COMPLEX
    if "SIMPLE" in complexity:
        return _ROUTE_SIMPLE
    return _ROUTE_MODERATE


class AdaptiveRAGPipeline(AgentPipeline):
    """Classify query complexity, then route to naive RAG, multi-hop RAG, or direct LLM."""

    _classify_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.adaptive_rag_pipeline.classify_prompt",
        default=(
            "Classify the complexity of the following question as one of: "
            "SIMPLE, MODERATE, or COMPLEX. "
            "SIMPLE means it can be answered directly without external context. "
            "MODERATE means a single retrieval step suffices. "
            "COMPLEX means it requires multiple reasoning steps or sub-questions. "
            "Reply with only the single word.\n\n"
            "Question: {{ query }}"
        ),
    )

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
        """Classify query complexity and route to the appropriate RAG strategy.

        Args:
            query: The user query string to classify and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"AdaptiveRAGPipeline: query must be a string, got {type(query).__name__}"
            )
        classify_prompt = type(self)._classify_prompt.render({"query": query})
        with Tapestry() as inner_classify:
            LLMChatCall(
                prompt=classify_prompt,
                llm=llm,
                _config=KnotConfig(id="classify"),
            )
        classify_result = await self._run_inner(inner_classify)
        complexity = str(classify_result.outputs.get("classify", "")).strip().upper()

        route = _select_complexity_route(complexity)

        # Each arm is built into the inner tapestry `SubTapestry.__call__` has
        # already opened, and returns its real sink knot. Previously every arm
        # opened its own `with Tapestry()`, ran it via `_run_inner`, pulled the
        # answer out, and handed back a `_ResultSource` closure wrapping the
        # precomputed value — so the arm's knots were invisible to the run this
        # pipeline reports. Only the decisions that must be resolved before the
        # graph can be built still need their own inner run.
        if route == _ROUTE_SIMPLE:
            answer = LLMChatCall(
                prompt=query,
                llm=llm,
                _config=KnotConfig(id="generate"),
            )
            return RAGResponseBuilder(answer=answer, _config=KnotConfig(id="response"))

        if route == _ROUTE_COMPLEX:
            decompose_prompt = type(self)._decompose_prompt.render({"query": query})
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
                combine=_merge_hits,
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
        return RAGResponseBuilder(answer=answer, _config=KnotConfig(id="response"))
