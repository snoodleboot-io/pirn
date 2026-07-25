"""Tests for :class:`ReActTerminationCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn_agents.specializations.react.react_termination_check import (
    ReActTerminationCheck,
)
from pirn_agents.types.agent_message import AgentMessage


class TestReActTerminationCheckProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ReActTerminationCheck:
        with Tapestry():
            src = MessagesPassthrough(
                messages=(AgentMessage(role="assistant", content="x"),),
                _config=KnotConfig(id="src"),
            )
            return ReActTerminationCheck(
                latest_response=src,
                max_iterations=10,
                current_iteration=1,
                _config=KnotConfig(id="gate"),
            )

    async def test_terminates_on_final_answer_marker(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="Final Answer: yes")
        result = await knot.process(latest_response=(msg,), max_iterations=10, current_iteration=1)
        assert result is True

    async def test_terminates_on_iteration_cap(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="still thinking")
        result = await knot.process(latest_response=(msg,), max_iterations=3, current_iteration=3)
        assert result is True

    async def test_does_not_terminate_when_under_cap_without_marker(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="thinking...")
        result = await knot.process(latest_response=(msg,), max_iterations=5, current_iteration=2)
        assert result is False

    async def test_rejects_zero_max_iterations(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="x")
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            await knot.process(latest_response=(msg,), max_iterations=0, current_iteration=1)

    async def test_rejects_negative_current_iteration(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="x")
        with self.assertRaisesRegex(ValueError, "current_iteration"):
            await knot.process(latest_response=(msg,), max_iterations=4, current_iteration=-1)

    async def test_user_message_does_not_trigger_final_answer(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="user", content="Final Answer: but from user")
        result = await knot.process(latest_response=(msg,), max_iterations=5, current_iteration=1)
        assert result is False
