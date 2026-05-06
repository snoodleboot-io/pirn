"""Unit tests for :class:`TerminationCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.control.termination_check import TerminationCheck
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> TerminationCheck:
    @knot
    async def _r() -> AgentResponse:
        return AgentResponse(content="x")

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="r"))
        return TerminationCheck(
            response=upstream,
            max_iterations=5,
            current_iteration=1,
            _config=KnotConfig(id="g"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_terminates_on_stop_finish_reason(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="done", finish_reason="stop"),
            max_iterations=5,
            current_iteration=1,
        )
        assert result is True

    async def test_terminates_at_max_iterations(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="thinking", finish_reason="tool_use"),
            max_iterations=3,
            current_iteration=3,
        )
        assert result is True

    async def test_continues_when_below_cap_and_unfinished(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="thinking", finish_reason="tool_use"),
            max_iterations=5,
            current_iteration=2,
        )
        assert result is False

    async def test_rejects_zero_max_iterations(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await k.process(
                response=AgentResponse(content="x"),
                max_iterations=0,
                current_iteration=0,
            )

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                response="not a response",  # type: ignore[arg-type]
                max_iterations=5,
                current_iteration=1,
            )
