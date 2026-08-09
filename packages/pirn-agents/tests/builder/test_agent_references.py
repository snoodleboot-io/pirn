"""Tests for :class:`AgentReferences` — spec labels to live objects."""

from __future__ import annotations

import unittest

from pirn_agents.builder.agent_references import AgentReferences
from tests.specializations.conftest import StubLLMProvider, StubTool


class TestRegistration(unittest.TestCase):
    def test_register_binds_a_label(self) -> None:
        llm = StubLLMProvider(["x"])
        assert AgentReferences().register("my-llm", llm).resolve("my-llm") is llm

    def test_register_is_chainable(self) -> None:
        references = AgentReferences().register("a", 1).register("b", 2)
        assert references.labels() == ("a", "b")

    def test_initial_mapping_is_registered(self) -> None:
        assert AgentReferences({"a": 1}).resolve("a") == 1

    def test_initial_must_be_a_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "initial must be a mapping"):
            AgentReferences(["a"])  # type: ignore[arg-type]

    def test_label_must_be_a_non_empty_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "label must be a str"):
            AgentReferences().register(1, "x")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "non-empty"):
            AgentReferences().register("", "x")

    def test_register_tools_uses_each_tool_name(self) -> None:
        # Arrange: this is the label `AgentBuilder.to_spec` writes for tools.
        tools = [StubTool(name="search"), StubTool(name="fetch")]

        # Act
        references = AgentReferences().register_tools(tools)

        # Assert
        assert references.labels() == ("fetch", "search")
        assert references.resolve("search") is tools[0]

    def test_register_tools_rejects_a_non_tool(self) -> None:
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a Tool"):
            AgentReferences().register_tools(["nope"])  # type: ignore[list-item]


class TestResolution(unittest.TestCase):
    def test_an_unknown_label_raises_and_lists_what_is_known(self) -> None:
        """The usual cause is a typo in a hand-written config, so say the options."""
        references = AgentReferences().register("my-llm", object())

        with self.assertRaises(KeyError) as caught:
            references.resolve("my-lmm")

        message = str(caught.exception)
        assert "unknown reference" in message
        assert "my-llm" in message

    def test_membership_is_queryable(self) -> None:
        references = AgentReferences().register("a", 1)
        assert "a" in references
        assert "b" not in references

    def test_a_registered_none_is_still_a_hit(self) -> None:
        """Resolution keys on registration, not truthiness."""
        assert AgentReferences().register("a", None).resolve("a") is None


if __name__ == "__main__":
    unittest.main()
