"""Tests for :class:`ApprovalGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.human_in_the_loop.approval_gate import (
    ApprovalGate,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestApprovalGateConstruction:
    async def test_rejects_non_bool_auto_approve(self) -> None:
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="auto_approve must be a bool"):
            with Tapestry():
                ApprovalGate(
                    response=response,
                    auto_approve="yes",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ag"),
                )


@pytest.mark.asyncio
class TestApprovalGateAutoApprove:
    async def test_returns_true_when_auto_approve(self) -> None:
        response = AgentResponse(content="draft", finish_reason="stop")
        with Tapestry() as t:
            ApprovalGate(
                response=response,
                auto_approve=True,
                _config=KnotConfig(id="ag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ag"] is True

    async def test_returns_false_without_auto_approve(self) -> None:
        response = AgentResponse(content="draft", finish_reason="stop")
        with Tapestry() as t:
            ApprovalGate(
                response=response,
                auto_approve=False,
                _config=KnotConfig(id="ag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ag"] is False

    async def test_rejects_non_agent_response(self) -> None:
        with pytest.raises(TypeError):
            with Tapestry():
                ApprovalGate(
                    response="not-a-response",  # type: ignore[arg-type]
                    auto_approve=True,
                    _config=KnotConfig(id="ag"),
                )
