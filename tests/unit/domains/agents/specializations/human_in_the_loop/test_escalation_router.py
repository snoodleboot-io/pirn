"""Tests for :class:`EscalationRouter`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.human_in_the_loop.escalation_router import (
    EscalationRouter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> EscalationRouter:
    with Tapestry():
        return EscalationRouter(
            response=AgentResponse(content="ok", finish_reason="stop"),
            threshold=0.8,
            _config=KnotConfig(id="er"),
        )


class TestEscalationRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_through_above_threshold(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="ok", finish_reason="stop", usage={"confidence": 90})
        result = await k.process(response=response, threshold=0.5)
        assert result is response

    async def test_escalates_below_threshold(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="unsure", finish_reason="stop", usage={"confidence": 0})
        result = await k.process(response=response, threshold=0.5)
        assert result is None

    async def test_escalates_when_confidence_missing(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="no confidence", finish_reason="stop")
        result = await k.process(response=response, threshold=0.5)
        assert result is None

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", threshold=0.5)  # type: ignore[arg-type]
