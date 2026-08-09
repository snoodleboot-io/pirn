"""Tests for :class:`AgentSpec`."""

from __future__ import annotations

import unittest

from pirn_agents.builder.agent_spec import AgentSpec


class TestAgentSpecValidation(unittest.TestCase):
    def test_rejects_empty_pattern(self) -> None:
        # Arrange / Act / Assert
        with self.assertRaisesRegex(ValueError, "pattern must be a non-empty"):
            AgentSpec(pattern="")

    def test_rejects_non_str_pattern(self) -> None:
        with self.assertRaisesRegex(TypeError, "pattern must be a str"):
            AgentSpec(pattern=123)  # type: ignore[arg-type]

    def test_rejects_non_str_tool_reference(self) -> None:
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a str"):
            AgentSpec(pattern="react", tools=(1,))  # type: ignore[arg-type]

    def test_rejects_non_primitive_option_value(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a str/int/float/bool"):
            AgentSpec(pattern="react", options={"x": object()})  # type: ignore[dict-item]

    def test_preserves_bool_option_as_bool(self) -> None:
        # Arrange / Act
        spec = AgentSpec(pattern="react", options={"flag": True})

        # Assert: bool is not silently coerced to int.
        assert spec.options["flag"] is True


class TestAgentSpecFromDict(unittest.TestCase):
    def test_rejects_unknown_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown field"):
            AgentSpec.from_dict({"pattern": "react", "bogus": 1})

    def test_rejects_missing_pattern(self) -> None:
        with self.assertRaisesRegex(ValueError, "required field 'pattern'"):
            AgentSpec.from_dict({"llm": "x"})

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a mapping"):
            AgentSpec.from_dict(["pattern", "react"])  # type: ignore[arg-type]

    def test_rejects_string_tools(self) -> None:
        with self.assertRaisesRegex(TypeError, "tools must be a sequence"):
            AgentSpec.from_dict({"pattern": "react", "tools": "web"})

    def test_builds_from_full_mapping(self) -> None:
        # Arrange
        data = {
            "pattern": "react",
            "llm": "my-llm",
            "memory": "store",
            "tools": ["a", "b"],
            "options": {"max_iterations": 6},
        }

        # Act
        spec = AgentSpec.from_dict(data)

        # Assert
        assert spec.pattern == "react"
        assert spec.llm == "my-llm"
        assert spec.memory == "store"
        assert spec.tools == ("a", "b")
        assert spec.options == {"max_iterations": 6}


class TestAgentSpecComponents(unittest.TestCase):
    """Patterns need components beyond llm/memory/tools; the spec records them."""

    def test_components_are_references_keyed_by_parameter_name(self) -> None:
        spec = AgentSpec(pattern="graph_rag", components={"graph_memory": "Neo4jStore"})
        assert spec.components == {"graph_memory": "Neo4jStore"}

    def test_components_default_to_empty(self) -> None:
        assert AgentSpec(pattern="react").components == {}

    def test_a_live_object_is_rejected_in_place_of_a_reference(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a str reference"):
            AgentSpec(pattern="graph_rag", components={"graph_memory": object()})  # type: ignore[dict-item]

    def test_components_must_be_a_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "components must be a mapping"):
            AgentSpec(pattern="graph_rag", components=["graph_memory"])  # type: ignore[arg-type]

    def test_components_load_from_a_mapping(self) -> None:
        spec = AgentSpec.from_dict(
            {"pattern": "graph_rag", "components": {"graph_memory": "Neo4jStore"}}
        )
        assert spec.components == {"graph_memory": "Neo4jStore"}


class TestAgentSpecRoundTrip(unittest.TestCase):
    def test_to_dict_from_dict_preserves_all_fields(self) -> None:
        # Arrange
        original = AgentSpec(
            pattern="naive_rag",
            llm="llm-ref",
            memory="mem-ref",
            tools=("t1", "t2"),
            components={"embedder": "StubEmbedder"},
            options={"top_k": 3, "flag": True, "label": "x"},
        )

        # Act
        restored = AgentSpec.from_dict(original.to_dict())

        # Assert
        assert restored == original

    def test_audit_dict_matches_to_dict(self) -> None:
        spec = AgentSpec(pattern="react", tools=("t",))
        assert spec._pirn_audit_dict() == spec.to_dict()


if __name__ == "__main__":
    unittest.main()
