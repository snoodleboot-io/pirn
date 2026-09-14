"""``CorrectiveRouter`` — fall back to a tool when retrieval comes up empty.

Inputs:
    relevant_docs: docs that survived a :class:`RelevanceGate`. When
        empty, the fallback tool is invoked with the query.
    query: the original user query.

Output: a ``list[Mapping[str, Any]]`` of "documents" that downstream
prompt-builder knots can format. Tool fallback wraps the tool result
in a single-doc list of the form ``[{"source": "fallback", "content": ...}]``.

The fallback call is a real
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation` knot rather than an
``await fallback_tool.invoke(...)`` inside ``process()``, so the call gets its
own ``Result``, history record, and lineage. ``process()`` builds one of two
tiny inner graphs depending on whether ``relevant_docs`` is empty, per the
``MultiSourceLoader`` pattern in ``docs/guides/sub-tapestry.md`` §4.

Algorithm:
    1. Validate that ``fallback_tool`` is a :class:`Tool` and ``query`` is
       a string.
    2. If ``relevant_docs`` is non-empty, the sink is a
       :class:`~pirn.core.parameter.Parameter`
       surfacing a shallow copy of the list unchanged.
    3. Otherwise the sink is a
       :class:`~pirn_agents.specializations.rag.fallback_document.FallbackDocument`,
       downstream of a :class:`~pirn_agents.tools.tool_invocation.ToolInvocation`
       that calls ``fallback_tool.invoke({"input": query})``; its output is
       ``[{"source": "fallback", "content": str(result)}]``.

References:
    - Corrective RAG: https://arxiv.org/abs/2401.15884
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.interfaces.router import Router
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.fallback_document import FallbackDocument
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_invocation import ToolInvocation


class CorrectiveRouter(AgentPipeline, Router):
    """Forward relevant docs, or invoke ``fallback_tool`` when none qualify."""

    def __init__(
        self,
        *,
        query: Knot | str,
        relevant_docs: Knot,
        fallback_tool: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            relevant_docs=relevant_docs,
            fallback_tool=fallback_tool,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        relevant_docs: list[Mapping[str, Any]],
        fallback_tool: ToolFactory,
        **_: Any,
    ) -> Knot:
        """Build the fallback graph and return the appropriate sink knot.

        Args:
            query: The original user query used as input when the fallback
                tool is invoked.
            relevant_docs: The list of documents that survived the relevance
                gate.
            fallback_tool: The tool invoked when ``relevant_docs`` is empty.

        Returns:
            The sink knot whose output is ``relevant_docs`` unchanged when
            non-empty, otherwise a single-entry list from the fallback tool.

        Raises:
            TypeError: If query is not a string or fallback_tool is not a Tool.
        """
        try:
            fallback_tool = ToolFactory.of(fallback_tool)
        except TypeError as exc:
            raise TypeError(
                "CorrectiveRouter: fallback_tool must be a Tool, "
                f"got {type(fallback_tool).__name__}"
            ) from exc
        if not isinstance(query, str):
            raise TypeError(f"CorrectiveRouter: query must be a string, got {type(query).__name__}")
        if relevant_docs:
            return Parameter(
                "relevant",
                list[Mapping[str, Any]],
                default=list(relevant_docs),
                _config=KnotConfig(id="relevant"),
            )
        call = ToolCall(
            tool_name=fallback_tool.name,
            arguments={"input": query},
            call_id="corrective_fallback",
        )
        invoke = ToolInvocation(tool=fallback_tool, call=call, _config=KnotConfig(id="call"))
        return FallbackDocument(tool_result=invoke, _config=KnotConfig(id="fallback"))
