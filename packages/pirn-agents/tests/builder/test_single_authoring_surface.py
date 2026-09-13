"""Ratchet: the builder's pattern table is core's registry, not a second one (WS6a).

``agents-vocabulary-drift-20260913.md`` named the authoring surface's central
defect: ``AgentPatternRegistry`` was a 65-row hardcoded name -> "module:Class"
table, disjoint from the sweet_tea registry core's YAML loader resolves
``callable:`` references through, and ``AgentSpec`` was a flat, bespoke schema
with no converter to core's ``PipelineSpec`` and no path through
``tapestry-check``. Zero uses of core's ``load_pipeline``/``PipelineSpec``/
``KnotSpec`` existed anywhere in ``pirn_agents``.

This test pins the three claims that close that gap, so a future change
cannot silently reopen a second namespace:

(a) every name :meth:`AgentPatternRegistry.pattern_names` advertises resolves
    through sweet_tea's ``AbstractInverterFactory[Knot]`` — the exact lookup
    core's YAML loader uses for a ``callable:`` reference — to the same class
    the builder itself would construct;
(b) :class:`~pirn_agents.builder.agent_spec.AgentSpec` round-trips losslessly
    through core's :class:`~pirn.yaml_loader.specs.pipeline_spec.PipelineSpec`
    via ``to_pipeline_spec``/``from_pipeline_spec``;
(c) :meth:`~pirn_agents.builder.agent.Agent.patterns` reports exactly the set
    of pattern-labelled entries in that same registry — one source of names,
    not a builder-side list kept in step by hand.

Run this file against the state before WS6a's fix (``git stash`` the
``builder/`` changes) and (a) and (c) fail with ``SweetTeaError``/set
mismatches; (b) fails with ``AttributeError`` because the methods do not
exist. That is the frozen inventory this ratchet burns down.
"""

from __future__ import annotations

import json
import unittest
import warnings

from pirn.core.knot import Knot
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec
from sweet_tea.abstract_inverter_factory import AbstractInverterFactory
from sweet_tea.registry import Registry

from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader


class TestPatternNamesResolveThroughCoreRegistry(unittest.TestCase):
    """(a) One registry: a pattern name is a core-registry key, not agents-only."""

    def test_every_pattern_name_resolves_through_the_core_registry(self) -> None:
        # Arrange / Act / Assert.
        for name in AgentPatternRegistry.pattern_names():
            resolved = AbstractInverterFactory[Knot].create(name)
            assert resolved is AgentPatternRegistry.pattern_class(name), (
                f"{name!r} resolves to a different class through the core registry "
                f"than through AgentPatternRegistry.pattern_class"
            )

    def test_the_registry_is_non_trivial(self) -> None:
        """Guard: the walk above is not vacuously true over an empty table."""
        assert len(AgentPatternRegistry.pattern_names()) > 60

    def test_every_resolved_class_is_a_sub_tapestry(self) -> None:
        for name in AgentPatternRegistry.pattern_names():
            assert issubclass(AbstractInverterFactory[Knot].create(name), SubTapestry)


class TestAgentSpecRoundTripsThroughPipelineSpec(unittest.TestCase):
    """(b) AgentSpec is a projection of core's PipelineSpec, not a parallel schema."""

    def test_a_pattern_only_spec_round_trips(self) -> None:
        # Arrange
        spec = AgentSpec(pattern="react", options={"max_iterations": 4})

        # Act
        pipeline_spec = spec.to_pipeline_spec()
        restored = AgentSpec.from_pipeline_spec(pipeline_spec)

        # Assert
        assert isinstance(pipeline_spec, PipelineSpec)
        assert restored == spec

    def test_a_spec_with_every_reference_kind_round_trips(self) -> None:
        # Arrange: llm, memory, tools, and a pattern-specific component.
        spec = AgentSpec(
            pattern="graph_rag",
            llm="my-llm",
            tools=("search", "calc"),
            components={"graph_memory": "neo4j"},
            options={"hop_count": 2},
        )

        # Act
        restored = AgentSpec.from_pipeline_spec(spec.to_pipeline_spec())

        # Assert
        assert restored == spec

    def test_a_naive_rag_spec_with_memory_round_trips(self) -> None:
        # Arrange
        spec = AgentSpec(pattern="naive_rag", llm="l", memory="m", options={"top_k": 3})

        # Act
        restored = AgentSpec.from_pipeline_spec(spec.to_pipeline_spec())

        # Assert
        assert restored == spec

    def test_the_pipeline_spec_names_the_pattern_as_a_knot_callable(self) -> None:
        """The projection actually uses core vocabulary, not a re-badged dict."""
        # Arrange / Act
        pipeline_spec = AgentSpec(pattern="react", options={"max_iterations": 3}).to_pipeline_spec()

        # Assert: exactly one knot node, naming the pattern the way a core
        # pipeline document names any other knot.
        from pirn.yaml_loader.specs.knot_spec import KnotSpec

        knot_nodes = [n for n in pipeline_spec.nodes if isinstance(n, KnotSpec)]
        assert len(knot_nodes) == 1
        assert knot_nodes[0].callable == "react"
        assert knot_nodes[0].config == {"max_iterations": 3}


class TestOneNamespaceOfPatternNames(unittest.TestCase):
    """(c) Agent.patterns() reports the registry's names, not a second list.

    Every name :meth:`AgentPatternRegistry.pattern_names` reports is confirmed
    (not merely declared) to resolve, through sweet_tea's Registry, to the
    exact class this table names for it — see
    :meth:`AgentPatternRegistry._resolves_uniquely_to`. A name is either
    reachable there via the ``"pattern"``-labelled alias
    :meth:`AgentPatternRegistry.register_with_core_registry` added, or — for
    the handful whose short name already equals their class's own
    auto-registered key (e.g. ``"reranker"``) — via that pre-existing entry,
    left alone rather than duplicated into an ambiguous lookup. Both cases
    are "the registry", not a second, builder-only list.
    """

    def test_agent_patterns_equals_the_registrys_confirmed_pattern_names(self) -> None:
        # Assert: the same one list, reachable from both doors.
        assert Agent.patterns() == AgentPatternRegistry.pattern_names()

    def test_every_reported_name_is_a_registry_key_in_the_pirn_library(self) -> None:
        # Arrange
        pirn_keys = {entry.key for entry in Registry.entries() if entry.library == "pirn"}

        # Act / Assert
        for name in Agent.patterns():
            assert name in pirn_keys

    def test_a_name_not_declared_here_is_not_reported_even_if_registered_elsewhere(self) -> None:
        """The registry can hold thousands of unrelated entries; only ours count."""
        # Arrange / Act / Assert: a real, unrelated pirn-core registry key.
        assert "knot" not in Agent.patterns()


class TestAgentSpecLoaderAcceptsBothDialects(unittest.TestCase):
    """``AgentSpecLoader`` reads a core pipeline document, and warns on the old one."""

    def test_a_core_pipeline_document_loads_with_no_warning(self) -> None:
        # Arrange: exactly the shape to_pipeline_spec() emits.
        spec = AgentSpec(pattern="react", options={"max_iterations": 4})
        document = json.dumps(
            {
                "name": "agent",
                "nodes": [
                    {"id": "agent:seed", "type": "parameter", "type_": "Any"},
                    {
                        "id": "agent",
                        "type": "knot",
                        "callable": "react",
                        "config": {"max_iterations": 4},
                    },
                ],
            }
        )

        # Act
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored = AgentSpecLoader.from_json(document)

        # Assert
        assert restored == spec

    def test_the_legacy_flat_dialect_still_loads_but_warns(self) -> None:
        # Arrange
        document = json.dumps({"pattern": "react", "options": {"max_iterations": 4}})

        # Act / Assert
        with self.assertWarns(DeprecationWarning):
            spec = AgentSpecLoader.from_json(document)
        assert spec == AgentSpec(pattern="react", options={"max_iterations": 4})

    def test_a_hand_authored_core_pipeline_document_round_trips_via_to_pipeline_spec(self) -> None:
        """The exact document to_pipeline_spec() would write, read back losslessly."""
        # Arrange
        spec = AgentSpec(pattern="naive_rag", llm="l", memory="m", options={"top_k": 2})
        pipeline_spec = spec.to_pipeline_spec()
        document = pipeline_spec.model_dump(mode="json")

        # Act
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored = AgentSpecLoader.from_mapping(document)

        # Assert
        assert restored == spec


if __name__ == "__main__":
    unittest.main()
