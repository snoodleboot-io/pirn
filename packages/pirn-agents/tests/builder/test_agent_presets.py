"""Tests for :class:`AgentPresets`."""

from __future__ import annotations

import tempfile
import unittest

from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent_presets import AgentPresets
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
    StubTool,
)


class TestResearchPreset(unittest.IsolatedAsyncioTestCase):
    async def test_builds_and_runs_with_default_web_tools(self) -> None:
        # Arrange: LLM answers immediately so no tool is invoked (backend-free).
        llm = StubLLMProvider(["Final Answer: researched"])
        with Tapestry() as t:
            agent = AgentPresets.research(llm=llm, input="what changed?")

        # Act
        run = await t.run(RunRequest())

        # Assert
        assert isinstance(agent, SubTapestry)
        assert run.succeeded
        assert run.outputs[agent.knot_id].content == "researched"

    async def test_accepts_tool_override(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        tool = StubTool(name="custom")
        with Tapestry() as t:
            agent = AgentPresets.research(llm=llm, input="q", tools=[tool])
        run = await t.run(RunRequest())
        assert run.succeeded
        assert isinstance(run.outputs[agent.knot_id], AgentResponse)


class TestRagChatPreset(unittest.IsolatedAsyncioTestCase):
    async def test_builds_and_runs(self) -> None:
        memory = StubMemoryStore([{"id": 1, "text": "fact"}])
        llm = StubLLMProvider(["chat answer"])
        with Tapestry() as t:
            agent = AgentPresets.rag_chat(llm=llm, memory=memory, input="hello", top_k=1)
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[agent.knot_id].content == "chat answer"
        assert memory.search_queries == ["hello"]


class TestCodingPreset(unittest.IsolatedAsyncioTestCase):
    async def test_builds_and_runs_with_filesystem_tools(self) -> None:
        llm = StubLLMProvider(["Final Answer: coded"])
        with tempfile.TemporaryDirectory() as root:
            with Tapestry() as t:
                agent = AgentPresets.coding(llm=llm, input="write code", root=root)
            run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[agent.knot_id].content == "coded"

    async def test_accepts_tool_override(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        tool = StubTool(name="only")
        with Tapestry() as t:
            agent = AgentPresets.coding(llm=llm, input="q", root="/unused", tools=[tool])
        run = await t.run(RunRequest())
        assert run.succeeded


class TestPresetsProviderNeutral(unittest.TestCase):
    def test_presets_require_caller_supplied_llm(self) -> None:
        # Arrange / Act / Assert: passing a non-provider is rejected — no vendor
        # default is silently substituted.
        with self.assertRaises(TypeError):
            with Tapestry():
                AgentPresets.research(llm="not-a-provider", input="q")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
