"""``FlareLoop`` — the sentence-by-sentence FLARE generation loop as a core node.

Replaces the hand-rolled ``for _step in range(max_sentences): await
llm.chat(...)`` (with a nested, conditionally-awaited retrieval + regenerate
call) that ran entirely outside the engine (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory).

Each round wires:

* ``generate`` — the next sentence, as ``DONE`` or ``CONF=<f>: <text>``.
* ``needs_retrieval`` — a :class:`~pirn.nodes.check.Check`
  (:class:`~pirn_agents.specializations.rag.needs_retrieval_check.NeedsRetrievalCheck`)
  reading ``generate``'s reply, the confidence threshold, and the retrieval
  budget spent so far.
* ``gated_reply`` — ``Gate(input=generate, check=needs_retrieval)``: the
  tentative sentence, retrieval, and regeneration all skip together when the
  gate is closed, the same escalation-stops-here shape ``AttemptTier`` and
  ``ReflexionLoop`` use — so a confident sentence never pays for retrieval.
* ``retrieve`` / ``regenerate`` — only reached when the gate is open.

``afold`` reads whichever reply is present (``regenerate`` when retrieval
ran, else ``generate``'s own parsed sentence) and integrates it into state.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.flare_regenerate_prompt_builder import (
    FlareRegeneratePromptBuilder,
)
from pirn_agents.specializations.rag.flare_reply_parser import FlareReplyParser
from pirn_agents.specializations.rag.flare_sentence_extractor import FlareSentenceExtractor
from pirn_agents.specializations.rag.flare_state import FlareState
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.memory_search_retriever import MemorySearchRetriever
from pirn_agents.specializations.rag.needs_retrieval_check import NeedsRetrievalCheck

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class FlareLoop(AgentLoopPipeline[FlareState]):
    """Generate one sentence per round, retrieving forward on low confidence."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _generate_id: ClassVar[str] = "generate"
    _regenerate_id: ClassVar[str] = "regenerate"

    _generation_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.flare_active_rag_pipeline.generation_prompt",
        default=(
            "Answer the question one sentence at a time. Reply with 'DONE' if the answer is "
            "complete, otherwise reply exactly 'CONF=<0-1>: <the next sentence>' where the number "
            "is your confidence.\n\nQuestion: {{ query }}\n\nAnswer so far: {{ so_far }}"
        ),
    )

    def __init__(
        self,
        *,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        confidence_threshold: float,
        max_sentences: int,
        max_retrieval_calls: int,
        top_k: int,
        **kwargs: Any,
    ) -> None:
        self._query = query
        self._memory = memory
        self._llm = llm
        self._confidence_threshold = confidence_threshold
        self._max_sentences = max_sentences
        self._max_retrieval_calls = max_retrieval_calls
        self._top_k = top_k
        super().__init__(**kwargs)

    def step(self, state: FlareState) -> tuple[Tapestry, FlareState] | None:
        """Build the next round, or None once done or the sentence cap is reached.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with ``state``, or ``None`` once
            ``state.done`` or ``state.index`` has reached the cap.
        """
        if state.done or state.index >= self._max_sentences:
            return None

        prompt = self._generate_prompt(self._query, state.parts)

        round_tapestry = Tapestry()
        with round_tapestry:
            generate = LLMChatCall(
                prompt=prompt, llm=self._llm, _config=KnotConfig(id=self._generate_id)
            )
            needs_retrieval = NeedsRetrievalCheck(
                reply=generate,
                confidence_threshold=self._confidence_threshold,
                retrieval_calls_so_far=state.retrieval_calls,
                max_retrieval_calls=self._max_retrieval_calls,
                _config=KnotConfig(id="needs_retrieval"),
            )
            gated_reply = Gate(
                input=generate, check=needs_retrieval, _config=KnotConfig(id="gated_reply")
            )
            sentence = FlareSentenceExtractor(reply=gated_reply, _config=KnotConfig(id="sentence"))
            retrieved = MemorySearchRetriever(
                store=self._memory,
                query=sentence,
                top_k=self._top_k,
                _config=KnotConfig(id="retrieve"),
            )
            prompt_builder = FlareRegeneratePromptBuilder(
                query=self._query,
                sentence=sentence,
                docs=retrieved,
                _config=KnotConfig(id="regenerate_prompt"),
            )
            LLMChatCall(
                prompt=prompt_builder, llm=self._llm, _config=KnotConfig(id=self._regenerate_id)
            )
        return round_tapestry, state

    def fold(self, state: FlareState, result: RunResult) -> FlareState:
        """Integrate this round's reply (regenerated, when retrieval ran) into state.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state with the round's sentence appended (if non-empty),
            ``done`` set on a ``DONE`` reply, and the retrieval budget
            updated when retrieval ran.
        """
        reply = result.outputs[self._generate_id]
        index = state.index + 1
        if FlareReplyParser.is_done(reply):
            return FlareState(
                parts=state.parts, retrieval_calls=state.retrieval_calls, done=True, index=index
            )

        _confidence, sentence = FlareReplyParser.parse(reply)
        regenerated = result.outputs.get(self._regenerate_id)
        retrieval_calls = state.retrieval_calls
        if regenerated is not None:
            sentence = regenerated
            retrieval_calls += 1

        parts = (*state.parts, sentence) if sentence else state.parts
        return FlareState(parts=parts, retrieval_calls=retrieval_calls, done=False, index=index)

    def step_id(self, state: FlareState, idx: int) -> str:
        """Name each round for run history."""
        return f"sentence_{idx}"

    @classmethod
    def _generate_prompt(cls, query: str, parts: tuple[str, ...]) -> str:
        """Render the next-sentence generation prompt from the query and answer so far."""
        so_far = " ".join(parts) if parts else "(nothing yet)"
        return cls._generation_prompt.render({"query": query, "so_far": so_far})
