"""Tests for :class:`ReActTerminationCheck`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn.domains.agents.specializations.react.react_termination_check import (
    ReActTerminationCheck,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


class TestReActTerminationCheckConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_max_iterations(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            with Tapestry():
                source = MessagesPassthrough(
                    messages=(AgentMessage(role="assistant", content="x"),),
                    _config=KnotConfig(id="src"),
                )
                ReActTerminationCheck(
                    latest_response=source,
                    max_iterations=0,
                    current_iteration=1,
                    _config=KnotConfig(id="gate"),
                )

    async def test_rejects_bad_current_iteration_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "current_iteration"):
            with Tapestry():
                source = MessagesPassthrough(
                    messages=(AgentMessage(role="assistant", content="x"),),
                    _config=KnotConfig(id="src"),
                )
                ReActTerminationCheck(
                    latest_response=source,
                    max_iterations=4,
                    current_iteration="not-an-int",  # type: ignore[arg-type]
                    _config=KnotConfig(id="gate"),
                )


class TestReActTerminationCheckHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_terminates_on_final_answer_marker(self) -> None:
        with Tapestry() as t:
            source = MessagesPassthrough(
                messages=(
                    AgentMessage(role="assistant", content="Final Answer: yes"),
                ),
                _config=KnotConfig(id="src"),
            )
            ReActTerminationCheck(
                latest_response=source,
                max_iterations=10,
                current_iteration=1,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["gate"] is True

    async def test_terminates_on_iteration_cap(self) -> None:
        with Tapestry() as t:
            source = MessagesPassthrough(
                messages=(
                    AgentMessage(role="assistant", content="still thinking"),
                ),
                _config=KnotConfig(id="src"),
            )
            ReActTerminationCheck(
                latest_response=source,
                max_iterations=3,
                current_iteration=3,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["gate"] is True

    async def test_does_not_terminate_when_under_cap_without_marker(self,) -> None:
        with Tapestry() as t:
            source = MessagesPassthrough(
                messages=(
                    AgentMessage(role="assistant", content="thinking..."),
                ),
                _config=KnotConfig(id="src"),
            )
            ReActTerminationCheck(
                latest_response=source,
                max_iterations=5,
                current_iteration=2,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["gate"] is False
