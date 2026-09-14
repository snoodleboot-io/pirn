"""``AdaptiveRAGPipeline`` — complexity-routed retrieval-augmented generation.

Classifies the query as simple, moderate, or complex via an LLM call, then
routes to:

- **simple** — direct :class:`LLMChatCall` with no retrieval.
- **moderate** — naive single-hop :class:`MemorySearchRetriever` + answer.
- **complex** — multi-hop decomposition (three sub-questions), retrieval per
  sub-question, merged context, then final answer.

Algorithm:
    1. Call the LLM with a classification prompt; expect one of SIMPLE,
       MODERATE, or COMPLEX in the response. Resolve the reply to a route name
       with :meth:`AdaptiveRAGPipeline._select_complexity_route`, which prefers
       an exact match and falls back to a most-specific-first substring test.
    2. Wire the route through a core :class:`~pirn.nodes.branch.branch.Branch`
       (ADR agents-speaks-core WS5b) instead of a Python ``if route == ...``:
       each arm's *entry* knot takes the matching
       :class:`~pirn.nodes.branch.branch_output.BranchOutput` as an implicit
       dependency, so the unselected arms' knots are never invoked (skip
       propagates from the closed branch through the whole arm) rather than
       merely having their result discarded.
    3. **SIMPLE arm** — a single :class:`LLMChatCall` directly on the query,
       gated on ``branch["simple"]``, wrapped via :class:`RAGResponseBuilder`.
    4. **MODERATE arm** — :class:`MemorySearchRetriever` (gated on
       ``branch["moderate"]``) retrieves ``top_k`` hits for the original
       query; build prompt; call LLM; wrap via :class:`RAGResponseBuilder`.
    5. **COMPLEX arm** — wrapped as its own
       :class:`~pirn_agents.specializations.rag._complex_rag_arm.ComplexRagArm`
       (gated on ``branch["complex"]``) because its decompose-then-fan-out
       shape needs a dynamic sub-question count resolved in Python before the
       retrieval knots can be built — see that class's docstring for why
       gating the *knot itself*, not just its entry input, is what makes this
       arm's decompose call lazy too.
    6. Fuse the three (mutually-exclusive) arm outcomes with an
       :class:`Aggregator` under ``ErrorPolicy.RECEIVE_ERRORS`` — exactly one
       arm resolves ``Ok``, the other two are ``Skipped`` — and return that
       fused answer wrapped as the pipeline's sink.

References:
    - Adaptive RAG: https://arxiv.org/abs/2403.14403
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag._complex_rag_arm import ComplexRagArm
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
from pirn_agents.types.messaging.agent_response import AgentResponse


class AdaptiveRAGPipeline(AgentPipeline):
    """Classify query complexity, then route to naive RAG, multi-hop RAG, or direct LLM."""

    @staticmethod
    def _route_selector(raw_reply: str) -> str:
        """``Branch`` selector: map the classifier's raw reply to a route name.

        Args:
            raw_reply: The classify knot's resolved (unprocessed) text.

        Returns:
            One of ``"simple"``, ``"moderate"`` or ``"complex"``.
        """
        return AdaptiveRAGPipeline._select_complexity_route(str(raw_reply).strip().upper())

    @staticmethod
    def _pick_selected_response(**arms: Result[AgentResponse]) -> AgentResponse:
        """``Aggregator`` combine: return whichever arm's branch was selected.

        Args:
            **arms: One raw :class:`~pirn.core.result.Result` per arm
                (``RECEIVE_ERRORS``), keyed by route name — exactly one is
                ``Ok`` since ``Branch`` selects exactly one arm and every
                arm's entry knot is gated on its own
                :class:`~pirn.nodes.branch.branch_output.BranchOutput`.

        Returns:
            The selected arm's :class:`AgentResponse`.

        Raises:
            RuntimeError: If the selected arm's own value was ``Err``, or no
                arm resolved ``Ok`` (an invariant violation).
        """
        for name, result in arms.items():
            if isinstance(result, Ok):
                return result.value
            if isinstance(result, Err):
                raise RuntimeError(
                    f"AdaptiveRAGPipeline: selected arm {name!r} failed: "
                    f"{result.record.exc_type}: {result.record.message}"
                )
        raise RuntimeError("AdaptiveRAGPipeline: no route arm was selected")

    @staticmethod
    def _select_complexity_route(complexity: str) -> str:
        """Map a classifier reply to the name of the arm that should answer it.

        The classification prompt asks for a single bare word, so an exact
        match is tried first and the well-behaved reply never depends on
        substring semantics at all. Padded replies are common enough to need
        a fallback, and that fallback tests COMPLEX before SIMPLE.

        The ordering is load-bearing. Both fallback tests are substring
        tests, so a reply naming *both* labels — ``"COMPLEX (not simple)"``
        — matches either one, and whichever is tried first wins. Substring
        matching cannot resolve that, and neither can whole-word matching;
        the reply is genuinely ambiguous. COMPLEX is chosen because the two
        mistakes are not symmetrical: routing a simple query through
        multi-hop costs latency and tokens, whereas routing a complex query
        to the direct arm returns a wrong answer with ``succeeded=True``.
        Before PIR-770 SIMPLE was tried first, so the ladder failed in the
        expensive direction.

        An unrecognised reply routes to MODERATE. That is the documented
        default, not a consequence of the ordering.

        Args:
            complexity: The classifier reply, already stripped and upper-cased.

        Returns:
            One of ``"simple"``, ``"moderate"`` or ``"complex"``.
        """
        if complexity == "COMPLEX":
            return AdaptiveRAGPipeline._route_complex
        if complexity == "SIMPLE":
            return AdaptiveRAGPipeline._route_simple
        if complexity == "MODERATE":
            return AdaptiveRAGPipeline._route_moderate
        if "COMPLEX" in complexity:
            return AdaptiveRAGPipeline._route_complex
        if "SIMPLE" in complexity:
            return AdaptiveRAGPipeline._route_simple
        return AdaptiveRAGPipeline._route_moderate

    #: Route names the classifier resolves to (Rule: no module-level constants).
    _route_simple: ClassVar[str] = "simple"
    _route_moderate: ClassVar[str] = "moderate"
    _route_complex: ClassVar[str] = "complex"

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
    ) -> Knot:
        """Classify query complexity and route to the appropriate RAG strategy.

        Args:
            query: The user query string to classify and answer.

        Returns:
            The sink knot whose output is the selected arm's
            :class:`AgentResponse`.
        """
        classify_prompt = type(self)._classify_prompt.render({"query": query})
        classify = LLMChatCall(
            prompt=classify_prompt,
            llm=llm,
            _config=KnotConfig(id="classify"),
        )
        branch = Branch(
            input=classify,
            selector=AdaptiveRAGPipeline._route_selector,
            branches=(
                type(self)._route_simple,
                type(self)._route_moderate,
                type(self)._route_complex,
            ),
            _config=KnotConfig(id="route"),
        )

        # Every arm below is unconditionally built into this graph, but only
        # the selected one ever calls its LLM/retrieval: each arm's entry knot
        # takes the matching BranchOutput as an implicit dependency (a plain
        # extra kwarg `process()` absorbs via `**_`), so a non-selected arm's
        # BranchOutput resolves Skipped and the whole arm chain skips with it
        # (ADR agents-speaks-core WS5b).
        simple_answer = LLMChatCall(
            prompt=query,
            llm=llm,
            _route_gate=branch[type(self)._route_simple],
            _config=KnotConfig(id="generate_simple"),
        )
        simple_response = RAGResponseBuilder(
            answer=simple_answer, _config=KnotConfig(id="response_simple")
        )

        moderate_retrieved = MemorySearchRetriever(
            store=memory,
            query=query,
            top_k=top_k,
            _route_gate=branch[type(self)._route_moderate],
            _config=KnotConfig(id="retrieve"),
        )
        moderate_prompt = RAGPromptBuilder(
            query=query,
            retrieved=moderate_retrieved,
            _config=KnotConfig(id="prompt_moderate"),
        )
        moderate_answer = LLMChatCall(
            prompt=moderate_prompt,
            llm=llm,
            _config=KnotConfig(id="generate_moderate"),
        )
        moderate_response = RAGResponseBuilder(
            answer=moderate_answer, _config=KnotConfig(id="response_moderate")
        )

        # The complex arm is gated as a whole knot, not just its entry input,
        # because its dynamic sub-question fan-out needs a nested resolve
        # inside process() -- see ComplexRagArm's docstring.
        complex_response = ComplexRagArm(
            query=query,
            memory=memory,
            llm=llm,
            top_k=top_k,
            route_gate=branch[type(self)._route_complex],
            _config=KnotConfig(id="response_complex"),
        )

        return Aggregator(
            combine=AdaptiveRAGPipeline._pick_selected_response,
            _config=KnotConfig(id="rag_result", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            simple=simple_response,
            moderate=moderate_response,
            complex=complex_response,
        )
