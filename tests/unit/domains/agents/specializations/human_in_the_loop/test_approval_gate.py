"""Tests for :class:`ApprovalCheck`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.human_in_the_loop.approval_check import (
    ApprovalCheck,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> ApprovalCheck:
    with Tapestry():
        return ApprovalCheck(
            response=AgentResponse(content="ok", finish_reason="stop"),
            _config=KnotConfig(id="ag"),
        )


class TestApprovalCheckProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_when_auto_approve(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="draft", finish_reason="stop")
        result = await k.process(response=response, auto_approve=True)
        assert result is True

    async def test_returns_false_without_auto_approve(self) -> None:
        k = _make_knot()
        response = AgentResponse(content="draft", finish_reason="stop")
        result = await k.process(response=response, auto_approve=False)
        assert result is False

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", auto_approve=False)  # type: ignore[arg-type]
