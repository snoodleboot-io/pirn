"""Unit tests for :class:`SafetyGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.control.safety_gate import SafetyGate
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_true_when_no_match(self) -> None:
        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="hello world")

        with Tapestry() as t:
            msg = m(_config=KnotConfig(id="m"))
            SafetyGate(
                message=msg,
                deny_patterns=("password", r"\bsecret\b"),
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True

    async def test_returns_false_when_match(self) -> None:
        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="my password is hunter2")

        with Tapestry() as t:
            msg = m(_config=KnotConfig(id="m"))
            SafetyGate(
                message=msg,
                deny_patterns=("password",),
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is False

    async def test_accepts_agent_response(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="all good")

        with Tapestry() as t:
            rr = r(_config=KnotConfig(id="r"))
            SafetyGate(
                message=rr,
                deny_patterns=("forbidden",),
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True


class TestConstruction:
    def test_rejects_invalid_regex(self) -> None:
        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="x")

        with Tapestry():
            msg = m(_config=KnotConfig(id="m"))
            with pytest.raises(ValueError, match="not a valid regex"):
                SafetyGate(
                    message=msg,
                    deny_patterns=("([abc",),
                    _config=KnotConfig(id="g"),
                )
