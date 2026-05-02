"""``ResearchAgent`` — ReAct loop wrapped around a search tool.

A :class:`SubTapestry` that composes :class:`ReActLoop` with a single
caller-supplied :class:`Tool` (typically a web search tool) and an LLM
prompted to investigate the topic step-by-step.

The research transcript is seeded with a system message instructing the
LLM to issue ``Action: <search-tool-name>`` calls until it has enough
material to write a final summary. The :class:`ReActLoop` is bounded by
``max_searches`` to put a hard ceiling on tool invocations.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.react.react_loop import ReActLoop
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ResearchAgent(SubTapestry):
    """ReAct-driven research; returns a summary :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        llm: LLMProvider,
        search_tool: Tool,
        _config: KnotConfig,
        max_searches: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ResearchAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(search_tool, Tool):
            raise TypeError(
                "ResearchAgent: search_tool must be a Tool, "
                f"got {type(search_tool).__name__}"
            )
        if not isinstance(max_searches, int) or max_searches <= 0:
            raise ValueError(
                "ResearchAgent: max_searches must be a positive int, "
                f"got {max_searches!r}"
            )
        self._llm = llm
        self._search_tool = search_tool
        self._max_searches = max_searches
        super().__init__(topic=topic, _config=_config, **kwargs)

    async def process(self, topic: str, **_: Any) -> AgentResponse:
        if not isinstance(topic, str) or not topic:
            raise TypeError(
                "ResearchAgent: topic must be a non-empty string, "
                f"got {topic!r}"
            )
        seed_messages = (
            AgentMessage(
                role="system",
                content=(
                    "You are a research assistant. Investigate the user's "
                    f"topic by emitting Action: {self._search_tool.name} "
                    "calls. After gathering enough material, emit a "
                    "Final Answer: line summarising your findings."
                ),
            ),
            AgentMessage(role="user", content=f"Research topic: {topic}"),
        )
        with Tapestry() as inner:
            ReActLoop(
                messages=seed_messages,
                llm=self._llm,
                tools=(self._search_tool,),
                max_iterations=self._max_searches,
                _config=KnotConfig(id="react_loop"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("react_loop")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
