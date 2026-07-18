"""Tests for :class:`AgentKnotIdFactory`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig

from pirn_agents.builder.agent_knot_id_factory import AgentKnotIdFactory


class TestAgentKnotIdFactory(unittest.TestCase):
    def test_derivation_is_deterministic(self) -> None:
        # Arrange / Act
        first = AgentKnotIdFactory.derive(pattern="react", llm="L", tools=["a"], options={"n": 1})
        second = AgentKnotIdFactory.derive(pattern="react", llm="L", tools=["a"], options={"n": 1})

        # Assert: same structure -> same id, no time/randomness.
        assert first == second

    def test_distinct_structure_yields_distinct_id(self) -> None:
        base = AgentKnotIdFactory.derive(pattern="react", options={"max_iterations": 4})
        changed = AgentKnotIdFactory.derive(pattern="react", options={"max_iterations": 6})
        assert base != changed

    def test_explicit_name_is_used_verbatim(self) -> None:
        derived = AgentKnotIdFactory.derive(pattern="react", name="my-agent")
        assert derived == "agent.my-agent"

    def test_derived_id_is_valid_knot_config_id(self) -> None:
        # Arrange
        derived = AgentKnotIdFactory.derive(pattern="naive_rag", memory="m", tools=["x", "y"])

        # Act / Assert: KnotConfig accepts the derived id without raising.
        assert KnotConfig(id=derived).id == derived

    def test_rejects_invalid_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "must match"):
            AgentKnotIdFactory.derive(pattern="react", name="bad name!")

    def test_rejects_empty_pattern(self) -> None:
        with self.assertRaisesRegex(ValueError, "pattern must be non-empty"):
            AgentKnotIdFactory.derive(pattern="")


if __name__ == "__main__":
    unittest.main()
