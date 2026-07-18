"""Tests for :class:`AgentSpecLoader` (JSON + YAML parsing)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader


class TestAgentSpecLoaderJson(unittest.TestCase):
    def test_from_json_parses_object(self) -> None:
        # Arrange
        text = json.dumps({"pattern": "react", "options": {"max_iterations": 4}})

        # Act
        spec = AgentSpecLoader.from_json(text)

        # Assert
        assert spec.pattern == "react"
        assert spec.options == {"max_iterations": 4}

    def test_from_json_rejects_non_object(self) -> None:
        with self.assertRaisesRegex(TypeError, "top-level JSON must be an object"):
            AgentSpecLoader.from_json("[1, 2, 3]")

    def test_from_json_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            AgentSpecLoader.from_json("{not json")

    def test_json_round_trip(self) -> None:
        # Arrange
        spec = AgentSpec(pattern="naive_rag", memory="m", tools=("t",), options={"top_k": 2})

        # Act
        restored = AgentSpecLoader.from_json(AgentSpecLoader.to_json(spec))

        # Assert
        assert restored == spec


class TestAgentSpecLoaderYaml(unittest.TestCase):
    def test_from_yaml_parses_mapping(self) -> None:
        # Arrange
        text = "pattern: react\ntools: [a, b]\noptions:\n  max_iterations: 6\n"

        # Act
        spec = AgentSpecLoader.from_yaml(text)

        # Assert
        assert spec.pattern == "react"
        assert spec.tools == ("a", "b")
        assert spec.options == {"max_iterations": 6}

    def test_from_yaml_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "top-level YAML must be a mapping"):
            AgentSpecLoader.from_yaml("- 1\n- 2\n")

    def test_yaml_round_trip(self) -> None:
        # Arrange
        spec = AgentSpec(
            pattern="react", llm="l", tools=("t1", "t2"), options={"max_iterations": 5}
        )

        # Act
        restored = AgentSpecLoader.from_yaml(AgentSpecLoader.to_yaml(spec))

        # Assert
        assert restored == spec


class TestAgentSpecLoaderPath(unittest.TestCase):
    def test_from_path_dispatches_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.json"
            path.write_text(json.dumps({"pattern": "react"}), encoding="utf-8")
            spec = AgentSpecLoader.from_path(path)
        assert spec.pattern == "react"

    def test_from_path_dispatches_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.yml"
            path.write_text("pattern: naive_rag\nmemory: m\n", encoding="utf-8")
            spec = AgentSpecLoader.from_path(path)
        assert spec.pattern == "naive_rag"
        assert spec.memory == "m"

    def test_from_path_rejects_unknown_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec.txt"
            path.write_text("pattern: react", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported suffix"):
                AgentSpecLoader.from_path(path)


if __name__ == "__main__":
    unittest.main()
