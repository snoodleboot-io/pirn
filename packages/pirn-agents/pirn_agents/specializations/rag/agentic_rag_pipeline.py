"""``AgenticRagPipeline`` — RAG exposed as a tool the agent drives in a loop.

Agentic RAG treats retrieval as an explicit, agent-callable action rather than a
fixed pipeline stage: the F6 :class:`~pirn_agents.tools.retrieval.rag_tool.RagTool`
is invoked, its answer is inspected, and — while a budget remains — the LLM may
issue a follow-up question that drives another tool call. The ``rag_tool`` is
validated as a standard :class:`~pirn_agents.tools.tool.Tool` (isinstance) and
called exactly like any other tool in the loop.

The loop is expressed as an
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
(see :class:`~pirn_agents.specializations.rag._agentic_rag_loop._AgenticRagLoop`)
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
       c. Otherwise a ``_FollowUpDecision`` asks the LLM to reply
          ``DONE`` (answer is sufficient) or ``FOLLOWUP: <next question>``; on
          ``FOLLOWUP`` the loop continues with the new question, else it stops.
    3. Return the final answer as an :class:`AgentResponse`.

References:
    - Yao et al., "ReAct" (2022): https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import PositiveInt

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.rag._agentic_rag_loop import _AgenticRagLoop
from pirn_agents.specializations.rag._agentic_rag_result import _AgenticRagResult
from pirn_agents.specializations.rag._agentic_rag_state import _AgenticRagState
from pirn_agents.tools.tool_factory import ToolFactory


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
        rag_tool: Knot | Any,
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
        rag_tool: ToolFactory,
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
