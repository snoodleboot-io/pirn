"""Tests for :class:`AgentPatternRegistry`."""

from __future__ import annotations

import unittest

from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.pattern_seed_kind import PatternSeedKind
from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRAGPipeline
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse
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

    def test_canonical_names_exclude_aliases(self) -> None:
        assert "rag" not in AgentPatternRegistry.canonical_names()
        assert "naive_rag" in AgentPatternRegistry.canonical_names()

    def test_resolving_a_name_does_not_import_the_pattern(self) -> None:
        """`.pattern(...)` validates names; it must not drag in the whole surface."""
        descriptor = AgentPatternRegistry.descriptor("graph_rag")
        assert descriptor.module_name.endswith("graph_rag_pipeline")
        assert descriptor.class_name == "GraphRAGPipeline"


class TestDerivedContract(unittest.TestCase):
    """Required/optional parameters come from the constructor, not a hand table."""

    def test_required_components_are_the_defaultless_parameters(self) -> None:
        assert AgentPatternRegistry.required_components("naive_rag") == ("memory", "llm")

    def test_optional_parameters_are_the_defaulted_ones(self) -> None:
        assert AgentPatternRegistry.optional_parameters("naive_rag") == ("top_k",)

    def test_the_seed_is_not_a_required_component(self) -> None:
        assert "query" not in AgentPatternRegistry.required_components("naive_rag")

    def test_a_pattern_beyond_the_original_three_reports_its_own_needs(self) -> None:
        assert AgentPatternRegistry.required_components("graph_rag") == ("graph_memory", "llm")

    def test_describe_summarises_the_build_contract(self) -> None:
        described = AgentPatternRegistry.describe("react")
        assert described["class"] == "ReActLoop"
        assert described["seed"] == "messages"
        assert described["seed_kind"] == PatternSeedKind.MESSAGES.value
        assert described["optional"] == ["max_iterations"]


class TestBuildValidation(unittest.TestCase):
    def test_react_requires_llm(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, r"'react' requires \['llm'\]"):
                AgentPatternRegistry.build(
                    "react", knot_id="a", input_value="hi", components={"tools": ()}
                )

    def test_naive_rag_requires_memory(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaisesRegex(ValueError, r"'naive_rag' requires \['memory'\]"):
                AgentPatternRegistry.build(
                    "naive_rag", knot_id="a", input_value="q", components={"llm": llm}
                )

    def test_a_component_the_pattern_does_not_take_is_rejected(self) -> None:
        """Silently ignoring it would wire a graph different from the one asked for."""
        llm = StubLLMProvider(["x"])
        memory = StubMemoryStore([])
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "takes no component 'tools'"):
                AgentPatternRegistry.build(
                    "naive_rag",
                    knot_id="a",
                    input_value="q",
                    components={"llm": llm, "memory": memory, "tools": ()},
                )

    def test_a_mistyped_option_is_rejected(self) -> None:
        llm = StubLLMProvider(["x"])
        memory = StubMemoryStore([])
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "takes no option 'topk'"):
                AgentPatternRegistry.build(
                    "naive_rag",
                    knot_id="a",
                    input_value="q",
                    components={"llm": llm, "memory": memory},
                    options={"topk": 3},
                )

    def test_supplying_the_seed_as_a_component_is_rejected(self) -> None:
        llm = StubLLMProvider(["x"])
        memory = StubMemoryStore([])
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "input seed"):
                AgentPatternRegistry.build(
                    "naive_rag",
                    knot_id="a",
                    input_value="q",
                    components={"llm": llm, "memory": memory, "query": "other"},
                )

    def test_react_rejects_bad_message_sequence(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "must be an AgentMessage"):
                AgentPatternRegistry.build(
                    "react",
                    knot_id="a",
                    input_value=["not-a-message"],
                    components={"llm": llm, "tools": ()},
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
                components={"llm": llm, "tools": (tool,)},
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
                components={"llm": llm, "tools": ()},
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
                components={"llm": llm, "memory": memory},
                options={"top_k": 1},
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs[knot.knot_id].content == "answer"
        assert memory.search_queries == ["the query"]

    async def test_a_pattern_outside_the_original_three_builds_and_runs(self) -> None:
        """The point of PIR-730: `hyde_rag` was reachable only by hand-wiring."""
        memory = StubMemoryStore([{"id": 1, "text": "ctx"}])
        llm = StubLLMProvider(["hypothetical doc", "answer"])
        with Tapestry() as t:
            knot = AgentPatternRegistry.build(
                "hyde_rag",
                knot_id="agent.hyde.test",
                input_value="the query",
                components={"llm": llm, "memory": memory},
                options={"top_k": 1},
            )
        run = await t.run(RunRequest())
        assert run.succeeded, run.exceptions
        assert run.outputs[knot.knot_id].content == "answer"


if __name__ == "__main__":
    unittest.main()
