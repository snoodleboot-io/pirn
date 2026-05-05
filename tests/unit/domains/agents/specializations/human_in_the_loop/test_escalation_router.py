"""Tests for :class:`EscalationRouter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.human_in_the_loop.escalation_router import (
    EscalationRouter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class TestEscalationRouterConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_numeric_threshold(self) -> None:
        response = AgentResponse(content="ok", finish_reason="stop")
        with self.assertRaisesRegex(TypeError, "threshold must be a float"):
            with Tapestry():
                EscalationRouter(
                    response=response,
                    threshold="high",  # type: ignore[arg-type]
                    _config=KnotConfig(id="er"),
                )


class TestEscalationRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_through_above_threshold(self) -> None:
        response = AgentResponse(
            content="ok",
            finish_reason="stop",
            usage={"confidence": 90},
        )
        with Tapestry() as t:
            EscalationRouter(
                response=response,
                threshold=0.5,
                _config=KnotConfig(id="er"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["er"] is response

    async def test_escalates_below_threshold(self) -> None:
        response = AgentResponse(
            content="unsure",
            finish_reason="stop",
            usage={"confidence": 0},
        )
        with Tapestry() as t:
            EscalationRouter(
                response=response,
                threshold=0.5,
                _config=KnotConfig(id="er"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["er"] is None

    async def test_escalates_when_confidence_missing(self) -> None:
        response = AgentResponse(content="no confidence", finish_reason="stop")
        with Tapestry() as t:
            EscalationRouter(
                response=response,
                threshold=0.5,
                _config=KnotConfig(id="er"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["er"] is None

    async def test_rejects_non_agent_response(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                EscalationRouter(
                    response="not-a-response",  # type: ignore[arg-type]
                    threshold=0.5,
                    _config=KnotConfig(id="er"),
                )
