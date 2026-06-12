"""``ResearchAgent`` — ReAct loop wrapped around a search tool.

A :class:`SubTapestry` that composes :class:`ReActLoop` with a single
caller-supplied :class:`Tool` (typically a web search tool) and an LLM
prompted to investigate the topic step-by-step.

The research transcript is seeded with a system message instructing the
LLM to issue ``Action: <search-tool-name>`` calls until it has enough
material to write a final summary. The :class:`ReActLoop` is bounded by
``max_searches`` to put a hard ceiling on tool invocations.

Algorithm:
    1. Receive ``topic`` (str), ``llm``, ``search_tool``, and
       ``max_searches`` as plain values.
    2. Validate that ``topic`` is a non-empty string and ``max_searches``
       is a positive integer.
    3. Build seed messages and construct an inner :class:`Tapestry`
       containing :class:`ReActLoop`.
    4. Run the inner tapestry and extract the ``AgentResponse`` output.

Math:
    None.

References:
    None.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.react.react_loop import ReActLoop
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.nodes.sub_tapestry import SubTapestry


class ResearchAgent(SubTapestry):
    """ReAct-driven research; returns a summary :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        llm: Knot | LLMProvider,
        search_tool: Knot | Tool,
        _config: KnotConfig,
        max_searches: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            topic=topic,
            llm=llm,
            search_tool=search_tool,
            max_searches=max_searches,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        topic: str,
        llm: LLMProvider,
        search_tool: Tool,
        max_searches: int = 5,
        **_: Any,
    ) -> Any:
        """Run the search-backed ReAct loop on the topic and return a summary AgentResponse.

        Args:
            topic: The non-empty research topic string to investigate.
            llm: The LLM provider used by the ReAct loop.
            search_tool: The Tool used for web/document search.
            max_searches: Maximum number of search iterations (must be positive).

        Returns:
            An AgentResponse containing a summary of the research findings.

        Raises:
            TypeError: If topic is not a non-empty string or search_tool is not a Tool.
            ValueError: If max_searches is not a positive integer.
        """
        if not isinstance(topic, str) or not topic:
            raise TypeError(f"ResearchAgent: topic must be a non-empty string, got {topic!r}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ResearchAgent: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(search_tool, Tool):
            raise TypeError(
                f"ResearchAgent: search_tool must be a Tool, got {type(search_tool).__name__}"
            )
        if not isinstance(max_searches, int) or max_searches <= 0:
            raise ValueError(
                f"ResearchAgent: max_searches must be a positive int, got {max_searches!r}"
            )
        seed_messages = (
            AgentMessage(
                role="system",
                content=(
                    "You are a research assistant. Investigate the user's "
                    f"topic by emitting Action: {search_tool.name} "
                    "calls. After gathering enough material, emit a "
                    "Final Answer: line summarising your findings."
                ),
            ),
            AgentMessage(role="user", content=f"Research topic: {topic}"),
        )
        return ReActLoop(
            messages=seed_messages,
            llm=llm,
            tools=(search_tool,),
            max_iterations=max_searches,
            _config=KnotConfig(id="react_loop"),
        )
