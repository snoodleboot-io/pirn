"""``AgenticRagPipeline`` — RAG exposed as a tool the agent drives in a loop.

Agentic RAG treats retrieval as an explicit, agent-callable action rather than a
fixed pipeline stage: the F6 :class:`~pirn_agents.tools.retrieval.rag_tool.RagTool`
is invoked, its answer is inspected, and — while a budget remains — the LLM may
issue a follow-up question that drives another tool call. The ``rag_tool`` is
validated as a standard :class:`~pirn_agents.tools.tool.Tool` (isinstance) and
called exactly like any other tool in the loop.

The loop is expressed as an
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
(see :class:`~pirn_agents.specializations.rag._agentic_rag_loop.AgenticRagLoop`)
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
       c. Otherwise a ``FollowUpDecision`` asks the LLM to reply
          ``DONE`` (answer is sufficient) or ``FOLLOWUP: <next question>``; on
          ``FOLLOWUP`` the loop continues with the new question, else it stops.
    3. Return the final answer as an :class:`AgentResponse`.

References:
    - Yao et al., "ReAct" (2022): https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import PositiveInt

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag._agentic_rag_loop import AgenticRagLoop
from pirn_agents.specializations.rag._agentic_rag_result import AgenticRagResult
from pirn_agents.specializations.rag._agentic_rag_state import AgenticRagState
from pirn_agents.tools.tool_factory import ToolFactory


class AgenticRagPipeline(AgentPipeline):
    """Drive the RAG tool in a bounded agent loop, refining the question."""

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
        loop = AgenticRagLoop(
            query=query,
            rag_tool=rag_tool,
            llm=llm,
            max_iterations=max_iterations,
            state=AgenticRagState(current_question=query),
            _config=KnotConfig(id="loop"),
        )
        return AgenticRagResult(state=loop, _config=KnotConfig(id="result"))
