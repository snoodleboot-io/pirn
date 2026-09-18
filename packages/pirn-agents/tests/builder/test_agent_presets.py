"""Tests for :class:`AgentPresets`."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock

from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent_presets import AgentPresets
from pirn_agents.types.messaging.agent_response import AgentResponse
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
        assert run.outputs[agent.knot_id].data == "researched"

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
        assert run.outputs[agent.knot_id].data == "chat answer"
        assert memory.search_queries == ["hello"]


class TestCodingPreset(unittest.IsolatedAsyncioTestCase):
    async def test_builds_and_runs_with_filesystem_tools(self) -> None:
        llm = StubLLMProvider(["Final Answer: coded"])
        with tempfile.TemporaryDirectory() as root:
            with Tapestry() as t:
                agent = AgentPresets.coding(llm=llm, input="write code", root=root)
            run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[agent.knot_id].data == "coded"

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
                AgentPresets.research(llm="not-a-provider", input="q")


class TestPresetShapeIsALoadedCorePipelineDocument(unittest.IsolatedAsyncioTestCase):
    """Each preset's shape comes from pirn_agents/builder/presets/*.yaml (WS6a)."""

    def test_each_preset_document_matches_its_hardcoded_fallback(self) -> None:
        """The two must agree, or the ImportError fallback silently drifts."""
        for name in ("research", "rag_chat", "coding"):
            spec = AgentPresets._preset_spec(name)
            assert spec.pattern == AgentPresets._fallback_pattern[name]
            assert spec.options == AgentPresets._fallback_options[name]

    def test_a_preset_builder_carries_the_documents_pattern_and_options(self) -> None:
        # Arrange / Act
        builder = AgentPresets.builder_for(
            "rag_chat", llm=StubLLMProvider(["x"]), memory=StubMemoryStore([]), input="q"
        )

        # Assert: naive_rag/top_k come from rag_chat.yaml, not a Python literal.
        assert builder.pattern_name == "naive_rag"
        assert builder.options == {"top_k": 5}

    def test_falls_back_to_the_hardcoded_shape_when_yaml_is_not_installed(self) -> None:
        """AgentPresets is a base-install feature -- it must not need the yaml extra."""
        # Arrange / Act: block `import yaml`, exactly like
        # test_agent_spec_loader_missing_yaml.py does for AgentSpecLoader.
        with mock.patch.dict("sys.modules", {"yaml": None}):
            spec = AgentPresets._preset_spec("coding")

        # Assert: same shape as the YAML document would have given.
        assert spec.pattern == "react"
        assert spec.options == {"max_iterations": 8}

    async def test_presets_still_run_without_yaml(self) -> None:
        llm = StubLLMProvider(["Final Answer: ok"])
        with mock.patch.dict("sys.modules", {"yaml": None}), Tapestry() as t:
            agent = AgentPresets.research(llm=llm, input="q", tools=[])
        run = await t.run(RunRequest())
        assert run.succeeded, run.exceptions
        assert run.outputs[agent.knot_id].data == "ok"


if __name__ == "__main__":
    unittest.main()
