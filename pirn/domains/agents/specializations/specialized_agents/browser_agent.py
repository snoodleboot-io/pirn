"""``BrowserAgent`` — ReAct loop driving a browser-automation tool.

A :class:`SubTapestry` that composes :class:`ReActLoop` with a single
caller-supplied :class:`Tool` standing in for a browser-automation
backend (e.g. Playwright). The tool's :meth:`invoke` is expected to
accept ``{"action": ..., "args": ...}`` and return a result string. The
seed prompt instructs the LLM to issue browser actions step-by-step
until it has enough information to write a final answer.

The browser tool itself is supplied by the caller; this knot does not
ship a concrete browser backend.
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


class BrowserAgent(SubTapestry):
    """ReAct-driven browser automation agent."""

    def __init__(
        self,
        *,
        goal: Knot | str,
        llm: LLMProvider,
        browser_tool: Tool,
        _config: KnotConfig,
        max_steps: int = 10,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "BrowserAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(browser_tool, Tool):
            raise TypeError(
                "BrowserAgent: browser_tool must be a Tool, "
                f"got {type(browser_tool).__name__}"
            )
        if not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError(
                "BrowserAgent: max_steps must be a positive int, "
                f"got {max_steps!r}"
            )
        self._llm = llm
        self._browser_tool = browser_tool
        self._max_steps = max_steps
        super().__init__(goal=goal, _config=_config, **kwargs)

    async def process(self, goal: str, **_: Any) -> AgentResponse:
        """Run the ReAct loop with the browser tool to accomplish the goal and return the result.

        Args:
            goal: The non-empty goal description instructing the agent what to accomplish.

        Returns:
            An AgentResponse containing the final answer from the ReAct loop.

        Raises:
            TypeError: If goal is not a non-empty string.
        """
        if not isinstance(goal, str) or not goal:
            raise TypeError(
                "BrowserAgent: goal must be a non-empty string, "
                f"got {goal!r}"
            )
        seed_messages = (
            AgentMessage(
                role="system",
                content=(
                    "You are a browser-automation agent. Drive the browser "
                    f"by emitting Action: {self._browser_tool.name} calls "
                    "with Action Input describing the action and arguments "
                    "(e.g. 'navigate https://example.com'). When the goal "
                    "is achieved, emit Final Answer: <result>."
                ),
            ),
            AgentMessage(role="user", content=f"Goal: {goal}"),
        )
        with Tapestry() as inner:
            ReActLoop(
                messages=seed_messages,
                llm=self._llm,
                tools=(self._browser_tool,),
                max_iterations=self._max_steps,
                _config=KnotConfig(id="react_loop"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("react_loop")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
