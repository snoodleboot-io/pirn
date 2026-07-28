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
from pirn_agents.types.messaging.agent_message import AgentMessage


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
                already_terminated=False,
                _config=KnotConfig(id="gate"),
            )

    async def test_terminates_on_final_answer_marker(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="Final Answer: yes")
        result = await knot.process(
            latest_response=(msg,),
            max_iterations=10,
            current_iteration=1,
            already_terminated=False,
        )
        assert result is True

    async def test_terminates_on_iteration_cap(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="still thinking")
        result = await knot.process(
            latest_response=(msg,),
            max_iterations=3,
            current_iteration=3,
            already_terminated=False,
        )
        assert result is True

    async def test_does_not_terminate_when_under_cap_without_marker(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="thinking...")
        result = await knot.process(
            latest_response=(msg,),
            max_iterations=5,
            current_iteration=2,
            already_terminated=False,
        )
        assert result is False

    async def test_rejects_zero_max_iterations(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="x")
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            await knot.process(
                latest_response=(msg,),
                max_iterations=0,
                current_iteration=1,
                already_terminated=False,
            )

    async def test_rejects_negative_current_iteration(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="x")
        with self.assertRaisesRegex(ValueError, "current_iteration"):
            await knot.process(
                latest_response=(msg,),
                max_iterations=4,
                current_iteration=-1,
                already_terminated=False,
            )

    async def test_user_message_does_not_trigger_final_answer(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="user", content="Final Answer: but from user")
        result = await knot.process(
            latest_response=(msg,),
            max_iterations=5,
            current_iteration=1,
            already_terminated=False,
        )
        assert result is False

    async def test_termination_latches_when_already_terminated(self) -> None:
        """A step running after the final answer emits no marker of its own.

        Without the latch the gate reopens and a later accumulator appends over
        the answer, which is the PIR-753 answer-loss defect.
        """
        knot = self._make()
        result = await knot.process(
            latest_response=(),
            max_iterations=10,
            current_iteration=2,
            already_terminated=True,
        )
        assert result is True

    async def test_latch_wins_over_a_non_terminating_latest_response(self) -> None:
        knot = self._make()
        msg = AgentMessage(role="assistant", content="I am still pondering.")
        result = await knot.process(
            latest_response=(msg,),
            max_iterations=10,
            current_iteration=2,
            already_terminated=True,
        )
        assert result is True

    async def test_latch_is_validated_before_it_is_honoured(self) -> None:
        """The latch must not bypass argument validation."""
        knot = self._make()
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            await knot.process(
                latest_response=(),
                max_iterations=0,
                current_iteration=1,
                already_terminated=True,
            )
