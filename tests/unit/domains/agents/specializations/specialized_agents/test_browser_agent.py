"""Tests for :class:`BrowserAgent`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.specialized_agents.browser_agent import (
    BrowserAgent,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


class TestBrowserAgentConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_tool(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        with Tapestry():
            k = BrowserAgent.__new__(BrowserAgent)
            object.__setattr__(k, "_config", KnotConfig(id="browser"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                goal="open page",
                llm=llm,
                browser_tool="not-a-tool",  # type: ignore[arg-type]
                max_steps=10,
            )

    async def test_rejects_zero_max_steps(self) -> None:
        llm = StubLLMProvider(["Final Answer: done"])
        tool = StubTool(name="browser")
        with Tapestry():
            k = BrowserAgent.__new__(BrowserAgent)
            object.__setattr__(k, "_config", KnotConfig(id="browser"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                goal="open page",
                llm=llm,
                browser_tool=tool,
                max_steps=0,
            )


class TestBrowserAgentHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_drives_browser_to_final_answer(self) -> None:
        llm = StubLLMProvider(
            [
                "Action: browser\nAction Input: navigate https://example.com",
                "Final Answer: page title is Example Domain",
            ]
        )
        tool = StubTool(
            name="browser",
            handler="navigated to https://example.com (title: Example Domain)",
        )
        with Tapestry() as t:
            BrowserAgent(
                goal="open example.com and read the title",
                llm=llm,
                browser_tool=tool,
                max_steps=4,
                _config=KnotConfig(id="browser"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["browser"]
        assert isinstance(response, AgentResponse)
        assert response.finish_reason == "stop"
        assert "Example Domain" in response.content
        assert tool.invocations == [
            {"input": "navigate https://example.com"}
        ]
