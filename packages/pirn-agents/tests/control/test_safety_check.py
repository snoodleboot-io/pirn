"""Unit tests for :class:`SafetyCheck`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.tapestry import Tapestry

from pirn_agents.control.safety_check import SafetyCheck
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse


def _make_knot() -> SafetyCheck:
    @KnotFactory.knot
    async def _m() -> AgentMessage:
        return AgentMessage(role="user", content="x")

    with Tapestry():
        upstream = _m(_config=KnotConfig(id="m"))
        return SafetyCheck(
            message=upstream,
            deny_patterns=("deny",),
            _config=KnotConfig(id="g"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_when_no_match(self) -> None:
        k = _make_knot()
        result = await k.process(
            message=AgentMessage(role="user", content="hello world"),
            deny_patterns=("password", r"\bsecret\b"),
        )
        assert result is True

    async def test_returns_false_when_match(self) -> None:
        k = _make_knot()
        result = await k.process(
            message=AgentMessage(role="user", content="my password is hunter2"),
            deny_patterns=("password",),
        )
        assert result is False

    async def test_accepts_agent_response(self) -> None:
        k = _make_knot()
        result = await k.process(
            message=AgentResponse(content="all good"),
            deny_patterns=("forbidden",),
        )
        assert result is True

    async def test_rejects_invalid_regex(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "not a valid regex"):
            await k.process(
                message=AgentMessage(role="user", content="x"),
                deny_patterns=("([abc",),
            )

    async def test_rejects_wrong_type(self) -> None:
        k = _make_knot()
        result = await k({"message": "not a message", "deny_patterns": ("x",)})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
