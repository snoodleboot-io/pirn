"""``BrowserAgent`` — ReAct loop driving a browser-automation tool.

A :class:`SubTapestry` that composes :class:`ReActLoop` with a single
caller-supplied :class:`Tool` standing in for a browser-automation
backend (e.g. Playwright). The tool's :meth:`invoke` is expected to
accept ``{"action": ..., "args": ...}`` and return a result string. The
seed prompt instructs the LLM to issue browser actions step-by-step
until it has enough information to write a final answer.

The browser tool itself is supplied by the caller; this knot does not
ship a concrete browser backend.

Algorithm:
    1. Receive the ``goal`` string, ``llm`` provider, ``browser_tool``,
       and ``max_steps`` limit.
    2. Validate types and constraints in :meth:`process` (not
       ``__init__``).
    3. Build a two-message seed prompt: a system message describing the
       browser-action format and a user message containing the goal.
    4. Construct an inner :class:`Tapestry` containing a single
       :class:`ReActLoop` wired to the LLM and browser tool.
    5. Execute the inner tapestry via :meth:`SubTapestry._run_inner` and
       extract the ``react_loop`` output.
    6. Return the :class:`AgentResponse`; fall back to an empty response
       with ``finish_reason="length"`` if the output is absent.

Math:
    No numeric computation. ``max_steps`` bounds the ReAct iteration
    count via :class:`ReActLoop`.

References:
    - ReAct: Yao et al., 2022 (arXiv 2210.03629).
    - Playwright browser automation: https://playwright.dev
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
        llm: Knot | LLMProvider,
        browser_tool: Knot | Tool,
        max_steps: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            goal=goal,
            llm=llm,
            browser_tool=browser_tool,
            max_steps=max_steps,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        goal: str,
        llm: LLMProvider,
        browser_tool: Tool,
        max_steps: int,
        **_: Any,
    ) -> AgentResponse:
        """Run the ReAct loop with the browser tool to accomplish the goal and return the result.

        Args:
            goal: The non-empty goal description instructing the agent what to accomplish.
            llm: The LLM provider used to drive the ReAct loop.
            browser_tool: The browser automation tool the ReAct loop may invoke.
            max_steps: Maximum number of ReAct iterations before stopping.

        Returns:
            An AgentResponse containing the final answer from the ReAct loop.

        Raises:
            TypeError: If goal is not a non-empty string.
            TypeError: If llm is not an LLMProvider instance.
            TypeError: If browser_tool is not a Tool instance.
            ValueError: If max_steps is not a positive integer.
        """
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
                    f"by emitting Action: {browser_tool.name} calls "
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
                llm=llm,
                tools=(browser_tool,),
                max_iterations=max_steps,
                _config=KnotConfig(id="react_loop"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("react_loop")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
