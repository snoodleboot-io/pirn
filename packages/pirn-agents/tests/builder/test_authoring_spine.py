"""The four authoring surfaces are one spine, not four ways in (PIR-732).

Before this, the declarative surface was write-only: ``AgentBuilder.to_spec``
could serialise a configuration and ``AgentSpecLoader`` could parse one back,
but nothing consumed a spec — a config file could *describe* an agent that
could not be run. ``AgentBuilder.from_spec`` closes that, and these tests pin
the spine end to end:

* fluent → spec → fluent round-trips to the same configuration and the same
  knot id, so the two surfaces really are one thing seen twice;
* a YAML config reaches the engine and produces an answer;
* presets are named entries into the same builder, not a parallel path — the
  builder a preset hands back is the one it builds from, so the recipe can be
  read as data before it is committed to;
* the registry is the single pattern table all of them consult.
"""

from __future__ import annotations

import unittest

from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.builder.agent_presets import AgentPresets
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore, StubTool


class TestSpecRoundTrip(unittest.TestCase):
    """Fluent out to data, data back to fluent — the same configuration."""

    def _configured(self) -> tuple[AgentBuilder, AgentReferences]:
        llm = StubLLMProvider(["x"])
        tool = StubTool(name="search")
        builder = (
            Agent.builder().llm(llm).tools([tool]).pattern("react", max_iterations=4).input("hi")
        )
        references = AgentReferences().register("StubLLMProvider", llm).register_tools([tool])
        return builder, references

    def test_from_spec_reproduces_the_spec(self) -> None:
        # Arrange
        builder, references = self._configured()
        spec = builder.to_spec()

        # Act
        restored = AgentBuilder.from_spec(spec, references=references)

        # Assert: the data survives the trip in both directions.
        assert restored.to_spec() == spec

    def test_from_spec_reproduces_the_knot_id(self) -> None:
        """Same configuration must mean the same id, whichever door it came through."""
        # Arrange
        builder, references = self._configured()

        # Act
        restored = AgentBuilder.from_spec(builder.to_spec(), references=references).input("hi")

        # Assert
        assert restored.knot_id == builder.knot_id

    def test_from_spec_resolves_live_objects_not_labels(self) -> None:
        # Arrange
        builder, references = self._configured()

        # Act
        restored = AgentBuilder.from_spec(builder.to_spec(), references=references)

        # Assert: the builder holds the object, not the string that named it.
        assert restored.llm_provider is builder.llm_provider
        assert restored.tool_list == builder.tool_list

    def test_a_spec_carries_no_input(self) -> None:
        """A spec is a shape, not a question — one spec serves many inputs."""
        # Arrange
        builder, references = self._configured()

        # Act
        restored = AgentBuilder.from_spec(builder.to_spec(), references=references)

        # Assert
        assert restored.input_value is None
        with self.assertRaisesRegex(ValueError, "no input set"):
            with Tapestry():
                restored.build()

    def test_pattern_specific_components_survive_the_trip(self) -> None:
        # Arrange: a component neither llm, memory, nor tools.
        store = StubMemoryStore([])
        builder = (
            Agent.builder()
            .llm(StubLLMProvider(["x"]))
            .component("graph_memory", store)
            .pattern("graph_rag", hop_count=2)
        )
        references = (
            AgentReferences()
            .register("StubLLMProvider", builder.llm_provider)
            .register("StubMemoryStore", store)
        )

        # Act
        restored = AgentBuilder.from_spec(builder.to_spec(), references=references)

        # Assert
        assert restored.components["graph_memory"] is store
        assert restored.options == {"hop_count": 2}


class TestSpecValidation(unittest.TestCase):
    def test_a_label_with_no_reference_fails_loudly(self) -> None:
        """A typo in a config must not silently wire a knot to nothing."""
        spec = AgentSpec(pattern="react", llm="typoed-llm")
        with self.assertRaises(KeyError):
            AgentBuilder.from_spec(spec, references=AgentReferences())

    def test_an_unknown_pattern_is_rejected(self) -> None:
        spec = AgentSpec(pattern="not_a_pattern")
        with self.assertRaisesRegex(ValueError, "unknown pattern"):
            AgentBuilder.from_spec(spec, references=AgentReferences())

    def test_a_resolved_object_of_the_wrong_type_is_rejected(self) -> None:
        """References are resolved, then still type-checked by the setters."""
        spec = AgentSpec(pattern="react", llm="not-really-an-llm")
        references = AgentReferences().register("not-really-an-llm", object())
        with self.assertRaisesRegex(TypeError, "must be an LLMProvider"):
            AgentBuilder.from_spec(spec, references=references)

    def test_from_spec_requires_a_spec(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an AgentSpec"):
            AgentBuilder.from_spec({"pattern": "react"}, references=AgentReferences())  # type: ignore[arg-type]

    def test_from_spec_requires_a_references_table(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an AgentReferences"):
            AgentBuilder.from_spec(AgentSpec(pattern="react"), references={})  # type: ignore[arg-type]


class TestConfigDrivenAgentRuns(unittest.IsolatedAsyncioTestCase):
    """The headline: a YAML config now reaches the engine."""

    async def test_a_yaml_spec_builds_and_answers(self) -> None:
        # Arrange
        memory = StubMemoryStore([{"id": 1, "text": "ctx"}])
        llm = StubLLMProvider(["answer"])
        spec = AgentSpecLoader.from_json(
            '{"pattern": "naive_rag", "llm": "my-llm", "memory": "kb", "options": {"top_k": 1}}'
        )
        references = AgentReferences().register("my-llm", llm).register("kb", memory)

        # Act
        with Tapestry() as t:
            agent = Agent.from_spec(spec, references=references).input("the query").build()
        run = await t.run(RunRequest())

        # Assert
        assert isinstance(agent, SubTapestry)
        assert run.succeeded, run.exceptions
        assert run.outputs[agent.knot_id].content == "answer"
        assert memory.search_queries == ["the query"]

    async def test_one_spec_serves_many_inputs(self) -> None:
        # Arrange
        spec = AgentSpec(pattern="naive_rag", llm="my-llm", memory="kb", options={"top_k": 1})
        memory = StubMemoryStore([{"id": 1, "text": "ctx"}])
        llm = StubLLMProvider(["first", "second"])
        references = AgentReferences().register("my-llm", llm).register("kb", memory)

        # Act
        with Tapestry() as t:
            first = Agent.from_spec(spec, references=references).input("q1").name("a").build()
            second = Agent.from_spec(spec, references=references).input("q2").name("b").build()
        run = await t.run(RunRequest())

        # Assert: two agents, one description.
        assert run.succeeded, run.exceptions
        assert {run.outputs[first.knot_id].content, run.outputs[second.knot_id].content} == {
            "first",
            "second",
        }


class TestPresetsAreEntriesIntoTheSpine(unittest.IsolatedAsyncioTestCase):
    def test_builder_for_matches_the_named_preset(self) -> None:
        """Same recipe, whether taken as a builder or as a finished graph."""
        # Arrange
        llm = StubLLMProvider(["Final Answer: ok"])
        memory = StubMemoryStore([])

        # Act
        from_builder = AgentPresets.builder_for(
            "rag_chat", llm=llm, memory=memory, input="q", top_k=3
        )
        with Tapestry():
            built = AgentPresets.rag_chat(llm=llm, memory=memory, input="q", top_k=3)

        # Assert: identical configuration means an identical derived id.
        assert from_builder.knot_id == built.knot_id

    def test_a_preset_is_readable_as_data_before_building(self) -> None:
        # Arrange / Act
        spec = AgentPresets.builder_for(
            "rag_chat", llm=StubLLMProvider(["x"]), memory=StubMemoryStore([]), input="q"
        ).to_spec()

        # Assert: the recipe, as a spec, without a Tapestry or a graph.
        assert spec.pattern == "naive_rag"
        assert spec.options == {"top_k": 5}

    def test_a_preset_builder_can_be_adjusted_before_building(self) -> None:
        # Arrange
        builder = AgentPresets.builder_for(
            "rag_chat", llm=StubLLMProvider(["x"]), memory=StubMemoryStore([]), input="q"
        )

        # Act: keep chaining — it is an ordinary builder.
        adjusted = builder.pattern("naive_rag", top_k=9)

        # Assert
        assert adjusted.options == {"top_k": 9}

    def test_names_lists_the_presets_and_unknown_is_rejected(self) -> None:
        assert AgentPresets.names() == ("coding", "rag_chat", "research")
        with self.assertRaisesRegex(ValueError, "unknown preset"):
            AgentPresets.builder_for("nope")


class TestOnePatternTable(unittest.TestCase):
    def test_every_surface_consults_the_same_registry(self) -> None:
        # Arrange / Act: the fluent door and the declarative door, same typo.
        with self.assertRaisesRegex(ValueError, "unknown pattern"):
            Agent.builder().pattern("not_a_pattern")
        with self.assertRaisesRegex(ValueError, "unknown pattern"):
            AgentBuilder.from_spec(AgentSpec(pattern="not_a_pattern"), references=AgentReferences())

    def test_the_declarative_door_reaches_every_pattern_too(self) -> None:
        """S1 widened the table; S3 must not leave the spec path on the old three."""
        # Arrange
        spec = AgentSpec(pattern="hyde_rag", llm="l", memory="m", options={"top_k": 1})
        references = (
            AgentReferences()
            .register("l", StubLLMProvider(["x"]))
            .register("m", StubMemoryStore([]))
        )

        # Act
        builder = AgentBuilder.from_spec(spec, references=references)

        # Assert
        assert builder.pattern_name == "hyde_rag"
        assert builder.missing_components == ()


if __name__ == "__main__":
    unittest.main()
