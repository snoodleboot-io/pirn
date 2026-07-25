"""Tests for :class:`AgentPatternRegistry`."""

from __future__ import annotations

import unittest

from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRAGPipeline
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
    StubTool,
)


class TestPatternResolution(unittest.TestCase):
    def test_react_maps_to_react_loop(self) -> None:
        assert AgentPatternRegistry.pattern_class("react") is ReActLoop

    def test_rag_aliases_map_to_naive_rag(self) -> None:
        assert AgentPatternRegistry.pattern_class("naive_rag") is NaiveRAGPipeline
        assert AgentPatternRegistry.pattern_class("rag") is NaiveRAGPipeline

    def test_unknown_pattern_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown pattern"):
            AgentPatternRegistry.pattern_class("nope")

    def test_pattern_names_are_sorted(self) -> None:
        names = AgentPatternRegistry.pattern_names()
        assert names == tuple(sorted(names))


class TestBuildValidation(unittest.TestCase):
    def test_react_requires_llm(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "'react' requires an llm"):
                AgentPatternRegistry.build("react", knot_id="a", input_value="hi", llm=None)

    def test_naive_rag_requires_memory(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "requires a memory store"):
                AgentPatternRegistry.build(
                    "naive_rag", knot_id="a", input_value="q", llm=llm, memory=None
                )

    def test_naive_rag_rejects_non_str_input(self) -> None:
        llm = StubLLMProvider(["x"])
        memory = StubMemoryStore([])
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "requires a str query input"):
                AgentPatternRegistry.build(
                    "naive_rag",
                    knot_id="a",
                    input_value=123,
                    llm=llm,
                    memory=memory,
                )

    def test_react_rejects_bad_message_sequence(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "must be an AgentMessage"):
                AgentPatternRegistry.build(
                    "react", knot_id="a", input_value=["not-a-message"], llm=llm
                )


class TestBuildEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_react_string_input_runs(self) -> None:
        # Arrange
        llm = StubLLMProvider(["Final Answer: done"])
        tool = StubTool(name="search", handler="hit")
        with Tapestry() as t:
            knot = AgentPatternRegistry.build(
                "react",
                knot_id="agent.react.test",
                input_value="what is foo?",
                llm=llm,
                tools=(tool,),
                options={"max_iterations": 3},
            )

        # Act
        run = await t.run(RunRequest())

        # Assert
        assert run.succeeded
        response = run.outputs[knot.knot_id]
        assert isinstance(response, AgentResponse)
        assert response.content == "done"

    async def test_react_accepts_message_sequence(self) -> None:
        llm = StubLLMProvider(["Final Answer: hey"])
        with Tapestry() as t:
            knot = AgentPatternRegistry.build(
                "react",
                knot_id="agent.react.msgs",
                input_value=(AgentMessage(role="user", content="hi"),),
                llm=llm,
                options={"max_iterations": 2},
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[knot.knot_id].content == "hey"

    async def test_naive_rag_runs(self) -> None:
        memory = StubMemoryStore([{"id": 1, "text": "ctx"}])
        llm = StubLLMProvider(["answer"])
        with Tapestry() as t:
            knot = AgentPatternRegistry.build(
                "naive_rag",
                knot_id="agent.rag.test",
                input_value="the query",
                llm=llm,
                memory=memory,
                options={"top_k": 1},
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[knot.knot_id].content == "answer"
        assert memory.search_queries == ["the query"]


if __name__ == "__main__":
    unittest.main()
