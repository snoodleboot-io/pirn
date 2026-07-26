"""Characterization tests for the ``AgentAsToolMixin`` ↔ ``SubTapestry`` contract.

PIR-708 removes the unsound ``cast(SubTapestry, self)`` from
:meth:`~pirn_agents.tools.agent_as_tool_mixin.AgentAsToolMixin.as_tool` by making
the ``SubTapestry`` requirement structural rather than asserted. These tests pin
the behaviour that must survive that change:

1. ``agent.as_tool(...)`` builds an :class:`AgentTool` indistinguishable from the
   one :func:`~pirn_agents.tools.as_tool.as_tool` builds for the same agent and
   the same arguments — every keyword is a pure pass-through.
2. Every class that mixes in ``AgentAsToolMixin`` is a ``SubTapestry``, and its
   MRO carries ``SubTapestry`` exactly once.
3. The runtime guard still rejects a non-``SubTapestry`` agent with ``TypeError``
   through both the class and the free-function spelling.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.specializations.specialized_agents.research_agent import ResearchAgent
from pirn_agents.tools.agent_as_tool_mixin import AgentAsToolMixin
from pirn_agents.tools.agent_tool import AgentTool
from pirn_agents.tools.as_tool import as_tool
from tests.agent_tool_doubles import (
    NestingAgent,
    NoInputAgent,
    StubAgent,
    TopicMaxAgent,
    reset_doubles,
)
from tests.conftest import StubLLMProvider

MIXER_CLASSES: tuple[type, ...] = (
    ResearchAgent,
    StubAgent,
    NestingAgent,
    TopicMaxAgent,
    NoInputAgent,
)


def _tool_state(tool: AgentTool) -> dict[str, Any]:
    """Return a tool's constructor-derived state, excluding the wrapped agent."""
    return {key: value for key, value in vars(tool).items() if key != "_agent"}


def _construct_stub_agent(knot_id: str) -> StubAgent:
    """Build a registered ``StubAgent`` for use as a nested tool target."""
    with Tapestry():
        return StubAgent(_config=KnotConfig(id=knot_id))


class TestMixinMatchesFreeFunction(unittest.IsolatedAsyncioTestCase):
    """``AgentAsToolMixin.as_tool`` must be a pure delegation to ``as_tool``."""

    def setUp(self) -> None:
        reset_doubles()

    def test_defaults_match_the_free_function(self) -> None:
        # Arrange
        with Tapestry():
            via_method = StubAgent(_config=KnotConfig(id="method"))
            via_function = StubAgent(_config=KnotConfig(id="function"))

        # Act
        method_tool = via_method.as_tool()
        function_tool = as_tool(via_function)

        # Assert
        self.assertIsInstance(method_tool, AgentTool)
        self.assertEqual(_tool_state(method_tool), _tool_state(function_tool))
        self.assertIs(method_tool.agent, via_method)

    def test_every_keyword_passes_through_unchanged(self) -> None:
        # Arrange
        provider = StubLLMProvider(["Final Answer: ok"])
        budget = RunBudget(max_iterations=3, max_tokens=99)
        schema = {"type": "object", "properties": {"topic": {"type": "string"}}}
        with Tapestry():
            via_method = StubAgent(_config=KnotConfig(id="method"))
            via_function = StubAgent(_config=KnotConfig(id="function"))

        # Act
        method_tool = via_method.as_tool(
            name="helper",
            description="a helper",
            input_schema=schema,
            provider=provider,
            budget=budget,
            max_depth=2,
        )
        function_tool = as_tool(
            via_function,
            name="helper",
            description="a helper",
            input_schema=schema,
            provider=provider,
            budget=budget,
            max_depth=2,
        )

        # Assert
        self.assertEqual(_tool_state(method_tool), _tool_state(function_tool))
        self.assertEqual(method_tool.name, "helper")
        self.assertEqual(method_tool.description, "a helper")
        self.assertEqual(dict(method_tool.parameters_schema), schema)

    def test_invalid_max_depth_still_raises_through_the_method(self) -> None:
        # Arrange
        with Tapestry():
            agent = StubAgent(_config=KnotConfig(id="agent"))

        # Act / Assert
        with self.assertRaisesRegex(TypeError, "max_depth must be a positive int"):
            agent.as_tool(max_depth=0)

    async def test_method_built_tool_invokes_the_agent(self) -> None:
        # Arrange
        with Tapestry():
            agent = StubAgent(reply="did", _config=KnotConfig(id="agent"))

        # Act
        result = await agent.as_tool(name="helper").invoke({"topic": "thing"})

        # Assert
        self.assertIsNotNone(result.result)
        assert result.result is not None
        self.assertEqual(result.result.content, "did:thing")


class TestMixerSubTapestryContract(unittest.TestCase):
    """Every ``AgentAsToolMixin`` mixer is — and stays — a ``SubTapestry``."""

    def setUp(self) -> None:
        reset_doubles()

    def test_the_mixin_itself_is_a_sub_tapestry(self) -> None:
        # Arrange / Act / Assert — the requirement is structural, not asserted,
        # which is what lets ``as_tool`` drop its ``cast(SubTapestry, self)``.
        self.assertTrue(issubclass(AgentAsToolMixin, SubTapestry))

    def test_every_mixer_is_a_sub_tapestry_subclass(self) -> None:
        for mixer in MIXER_CLASSES:
            with self.subTest(mixer=mixer.__name__):
                # Arrange / Act / Assert
                self.assertTrue(issubclass(mixer, AgentAsToolMixin))
                self.assertTrue(issubclass(mixer, SubTapestry))

    def test_every_mixer_mro_carries_sub_tapestry_exactly_once(self) -> None:
        for mixer in MIXER_CLASSES:
            with self.subTest(mixer=mixer.__name__):
                # Arrange / Act
                mro = mixer.__mro__

                # Assert — C3 linearization succeeded and there is no duplication.
                self.assertEqual(mro.count(SubTapestry), 1)
                self.assertEqual(mro.count(AgentAsToolMixin), 1)
                self.assertLess(mro.index(AgentAsToolMixin), mro.index(SubTapestry))

    def test_research_agent_constructs_and_wraps_itself(self) -> None:
        # Arrange
        provider = StubLLMProvider(["Final Answer: ok"])
        search_tool = AgentTool(
            _construct_stub_agent("search-inner"),
            name="search",
            description="search the web",
        )

        # Act
        with Tapestry():
            agent = ResearchAgent(
                topic="quantum",
                llm=provider,
                search_tool=search_tool,
                _config=KnotConfig(id="research"),
            )
        tool = agent.as_tool()

        # Assert
        self.assertIsInstance(agent, SubTapestry)
        self.assertIs(tool.agent, agent)
        self.assertEqual(tool.name, "research_agent")


class TestNonSubTapestryRejection(unittest.TestCase):
    """The runtime guard is the single place a non-agent is refused."""

    def test_agent_tool_rejects_a_non_sub_tapestry(self) -> None:
        # Arrange / Act / Assert
        with self.assertRaisesRegex(TypeError, "must be a SubTapestry"):
            AgentTool(object())  # type: ignore[arg-type]

    def test_free_function_rejects_a_non_sub_tapestry(self) -> None:
        # Arrange / Act / Assert
        with self.assertRaisesRegex(TypeError, "must be a SubTapestry"):
            as_tool(object())  # type: ignore[arg-type]
