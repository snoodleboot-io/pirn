"""Tests for :class:`AgentBuilder` and the :class:`Agent` facade."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
    StubTool,
)


class TestBuilderValidation(unittest.TestCase):
    def test_llm_rejects_non_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an LLMProvider"):
            Agent.builder().llm("nope")  # type: ignore[arg-type]

    def test_memory_rejects_non_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a MemoryStore"):
            Agent.builder().memory("nope")  # type: ignore[arg-type]

    def test_tools_rejects_non_tool_element(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a Tool"):
            Agent.builder().tools(["nope"])  # type: ignore[list-item]

    def test_pattern_rejects_unknown(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown pattern"):
            Agent.builder().pattern("bogus")

    def test_build_without_pattern_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "no pattern selected"):
            Agent.builder().llm(StubLLMProvider(["x"])).input("hi").build()

    def test_build_without_input_raises(self) -> None:
        builder = Agent.builder().llm(StubLLMProvider(["x"])).pattern("react")
        with self.assertRaisesRegex(ValueError, "no input set"):
            builder.build()


class TestBuilderAccessors(unittest.TestCase):
    def test_escape_hatch_exposes_components(self) -> None:
        # Arrange
        llm = StubLLMProvider(["x"])
        tool = StubTool(name="search")
        builder = (
            Agent.builder()
            .llm(llm)
            .tools(Toolset([tool]))
            .pattern("react", max_iterations=6)
            .input("hi")
        )

        # Assert: every collected piece is readable back.
        assert builder.llm_provider is llm
        assert builder.tool_list == (tool,)
        assert builder.pattern_name == "react"
        assert builder.options == {"max_iterations": 6}
        assert builder.input_value == "hi"
        assert builder.pattern_class is ReActLoop

    def test_to_spec_snapshot(self) -> None:
        # Arrange
        builder = (
            Agent.builder()
            .llm(StubLLMProvider(["x"]))
            .tools([StubTool(name="t1")])
            .pattern("react", max_iterations=4)
            .input("hi")
        )

        # Act
        spec = builder.to_spec()

        # Assert: declarative snapshot uses reference labels.
        assert isinstance(spec, AgentSpec)
        assert spec.pattern == "react"
        assert spec.llm == "StubLLMProvider"
        assert spec.tools == ("t1",)
        assert spec.options == {"max_iterations": 4}


class TestBuilderStableIds(unittest.TestCase):
    def test_same_config_yields_same_id(self) -> None:
        # Arrange
        def make() -> AgentBuilder:
            return (
                Agent.builder()
                .llm(StubLLMProvider(["x"]))
                .tools([StubTool(name="t")])
                .pattern("react", max_iterations=5)
                .input("hi")
            )

        # Act / Assert: repeated builds of the same spec share a knot id.
        assert make().knot_id == make().knot_id

    def test_explicit_name_pins_id(self) -> None:
        builder = (
            Agent.builder()
            .llm(StubLLMProvider(["x"]))
            .pattern("react")
            .input("hi")
            .name("prod-agent")
        )
        assert builder.knot_id == "agent.prod-agent"


class TestBuilderBuildEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_react_agent_runs(self) -> None:
        # Arrange
        llm = StubLLMProvider(["Final Answer: 42"])
        tool = StubTool(name="search", handler="hit")
        with Tapestry() as t:
            agent = (
                Agent.builder()
                .llm(llm)
                .tools([tool])
                .pattern("react", max_iterations=3)
                .input("what is foo?")
                .build()
            )

        # Act
        run = await t.run(RunRequest())

        # Assert
        assert isinstance(agent, SubTapestry)
        assert run.succeeded
        response = run.outputs[agent.knot_id]
        assert isinstance(response, AgentResponse)
        assert response.content == "42"

    async def test_rag_agent_runs(self) -> None:
        memory = StubMemoryStore([{"id": 1, "text": "ctx"}])
        llm = StubLLMProvider(["answer"])
        with Tapestry() as t:
            agent = (
                Agent.builder()
                .llm(llm)
                .memory(memory)
                .pattern("naive_rag", top_k=1)
                .input("the query")
                .build()
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[agent.knot_id].content == "answer"

    async def test_generated_graph_matches_hand_wired(self) -> None:
        # Arrange: build the same agent two ways and compare knot ids + outputs.
        llm_a = StubLLMProvider(["Final Answer: same"])
        llm_b = StubLLMProvider(["Final Answer: same"])
        with Tapestry() as built_t:
            built = (
                Agent.builder().llm(llm_a).pattern("react", max_iterations=2).input("hi").build()
            )
        built_run = await built_t.run(RunRequest())

        with Tapestry() as hand_t:
            from pirn_agents.types.agent_message import AgentMessage

            hand = ReActLoop(
                messages=(AgentMessage(role="user", content="hi"),),
                llm=llm_b,
                tools=(),
                max_iterations=2,
                _config=KnotConfig(id=built.knot_id),
            )
        hand_run = await hand_t.run(RunRequest())

        # Assert: identical id and identical output content.
        assert built.knot_id == hand.knot_id
        assert built_run.outputs[built.knot_id].content == hand_run.outputs[hand.knot_id].content


class TestAgentFacade(unittest.TestCase):
    def test_builder_returns_fresh_builder(self) -> None:
        assert isinstance(Agent.builder(), AgentBuilder)
        assert Agent.builder() is not Agent.builder()

    def test_patterns_lists_supported_names(self) -> None:
        assert "react" in Agent.patterns()
        assert "naive_rag" in Agent.patterns()


if __name__ == "__main__":
    unittest.main()
