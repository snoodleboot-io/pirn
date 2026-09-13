"""``AgenticRagPipeline`` — RAG exposed as a tool the agent drives in a loop.

Agentic RAG treats retrieval as an explicit, agent-callable action rather than a
fixed pipeline stage: the F6 :class:`~pirn_agents.tools.retrieval.rag_tool.RagTool`
is invoked, its answer is inspected, and — while a budget remains — the LLM may
issue a follow-up question that drives another tool call. The ``rag_tool`` is
validated as a standard :class:`~pirn_agents.tools.tool.Tool` (isinstance) and
called exactly like any other tool in the loop.

The loop is expressed as an
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
rather than a hand-rolled ``for iteration in range(max_iterations)`` that
awaited ``rag_tool.invoke`` and ``llm.chat`` directly: each round is a real
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation` knot, so the call
gets its own ``Result``, history record, and lineage, and can be scheduled,
cached, and replayed like any other engine knot. The follow-up decision — an
``await`` — lives inside the round's iteration tapestry rather than in ``step``
/``fold`` (both synchronous, per ``agent_loop_pipeline.py``), and is simply
omitted from the last allowed round's tapestry, so it is never built and never
paid for.

Algorithm:
    1. Validate ``query`` (str), ``rag_tool`` (:class:`Tool`), ``llm``
       (:class:`LLMProvider`), and ``max_iterations`` (positive int).
    2. Start with ``current_question = query``. Each round:
       a. A :class:`~pirn_agents.tools.tool_invocation.ToolInvocation` calls
          ``rag_tool`` with ``current_question`` and reads the ``answer``.
       b. On the final allowed round, stop.
       c. Otherwise a :class:`_FollowUpDecision` asks the LLM to reply
          ``DONE`` (answer is sufficient) or ``FOLLOWUP: <next question>``; on
          ``FOLLOWUP`` the loop continues with the new question, else it stops.
    3. Return the final answer as an :class:`AgentResponse`.

References:
    - Yao et al., "ReAct" (2022): https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry
from pydantic import PositiveInt

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass
class _AgenticRagState:
    """State threaded across agentic-RAG rounds."""

    current_question: str
    answer: str = ""
    iteration: int = 0
    done: bool = False


class _FollowUpDecision(Knot):
    """Ask the LLM whether the tool's answer resolves the original question."""

    def __init__(
        self,
        *,
        original_query: Knot | str,
        tool_result: Knot | ToolResult,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            tool_result=tool_result,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        tool_result: ToolResult,
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices."""
        answer = AgenticRagPipeline._tool_answer(tool_result.result)
        return await AgenticRagPipeline._next_question(llm, original_query, answer)


class _AgenticRagLoop(AgentLoopPipeline[_AgenticRagState]):
    """Drive the tool-call / follow-up-decision loop under a round budget."""

    def __init__(
        self,
        *,
        query: str,
        rag_tool: Tool,
        llm: LLMProvider,
        max_iterations: int,
        **kwargs: Any,
    ) -> None:
        self._query = query
        self._rag_tool = rag_tool
        self._llm = llm
        self._max_iterations = max_iterations
        super().__init__(**kwargs)

    def step(self, state: _AgenticRagState) -> tuple[Tapestry, _AgenticRagState] | None:
        """Build the next round, or return None to terminate.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with the state ``fold`` will receive,
            or ``None`` once the round budget is exhausted or the loop was
            told to stop.
        """
        if state.done or state.iteration >= self._max_iterations:
            return None
        is_last_round = state.iteration == self._max_iterations - 1

        with Tapestry() as t:
            call = ToolCall(
                tool_name=self._rag_tool.name,
                arguments={"question": state.current_question},
                call_id=f"agentic_rag_{state.iteration}",
            )
            invoke = ToolInvocation(tool=self._rag_tool, call=call, _config=KnotConfig(id="call"))
            if not is_last_round:
                _FollowUpDecision(
                    original_query=self._query,
                    tool_result=invoke,
                    llm=self._llm,
                    _config=KnotConfig(id="decide"),
                )
        return t, state

    def fold(self, state: _AgenticRagState, result: RunResult) -> _AgenticRagState:
        """Integrate one round's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state carrying the round's answer and next question.

        Raises:
            RuntimeError: If the tool call itself failed.
        """
        tool_result: ToolResult = result.outputs["call"]
        if tool_result.status is not ToolStatus.OK:
            raise RuntimeError(f"AgenticRagPipeline: rag_tool call failed: {tool_result.error}")
        answer = AgenticRagPipeline._tool_answer(tool_result.result)
        # Absent on the last round (no _FollowUpDecision was built) or when the
        # LLM's reply was not a FOLLOWUP instruction. Either way, stop.
        follow_up = result.outputs.get("decide")
        return _AgenticRagState(
            current_question=follow_up if follow_up is not None else state.current_question,
            answer=answer,
            iteration=state.iteration + 1,
            done=follow_up is None,
        )

    def step_id(self, state: _AgenticRagState, idx: int) -> str:
        """Name each round for run history."""
        return f"round_{idx}"


class _AgenticRagResult(Knot):
    """Extract the final answer from the loop's final state."""

    def __init__(
        self,
        *,
        state: Knot | _AgenticRagState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _AgenticRagState, **_: Any) -> AgentResponse:
        """Return the last round's answer as an :class:`AgentResponse`."""
        return AgentResponse(content=state.answer, finish_reason="stop")


class AgenticRagPipeline(AgentPipeline):
    """Drive the RAG tool in a bounded agent loop, refining the question."""

    _next_question_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.agentic_rag_pipeline.next_question_prompt",
        default=(
            "You are an agent answering a question with a retrieval tool. Given the "
            "original question and the tool's latest answer, reply with exactly 'DONE' if "
            "the answer fully resolves the question, or 'FOLLOWUP: <a more specific "
            "question>' otherwise.\n\nOriginal question: {{ query }}\n\n"
            "Latest answer: {{ answer }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        rag_tool: Knot | Tool,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_iterations: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            rag_tool=rag_tool,
            llm=llm,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        rag_tool: Tool,
        llm: LLMProvider,
        max_iterations: PositiveInt = 3,
        **_: Any,
    ) -> Knot:
        """Build the tool-call loop and return its answer-extracting sink knot.

        Args:
            query: The user question the agent must answer.
            rag_tool: The retrieval tool the agent calls each round.
            llm: The provider deciding whether to ask a follow-up.
            max_iterations: Hard upper bound on tool calls (>= 1).

        Returns:
            The sink knot whose output is the final :class:`AgentResponse`.
        """
        loop = _AgenticRagLoop(
            query=query,
            rag_tool=rag_tool,
            llm=llm,
            max_iterations=max_iterations,
            state=_AgenticRagState(current_question=query),
            _config=KnotConfig(id="loop"),
        )
        return _AgenticRagResult(state=loop, _config=KnotConfig(id="result"))

    @staticmethod
    async def _next_question(llm: LLMProvider, query: str, answer: str) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices."""
        prompt = AgenticRagPipeline._next_question_prompt.render({"query": query, "answer": answer})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = LlmResponseText().extract(raw).strip()
        if reply.upper().startswith("FOLLOWUP:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None

    @staticmethod
    def _tool_answer(result: Any) -> str:
        """Pull the answer string out of a RAG-tool result."""
        if isinstance(result, Mapping):
            answer = result.get("answer")
            if isinstance(answer, str):
                return answer
        return str(result)
