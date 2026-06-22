"""Unit tests for :class:`HandoffCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_agents.control.handoff_check import HandoffCheck
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> HandoffCheck:
    @knot
    async def _r() -> AgentResponse:
        return AgentResponse(content="x")

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="r"))
        return HandoffCheck(
            response=upstream,
            escalation_patterns=("escalate",),
            _config=KnotConfig(id="g"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_when_match(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="please escalate this issue"),
            escalation_patterns=("escalate", r"speak to a human"),
        )
        assert result is True

    async def test_returns_false_when_no_match(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="here is your answer"),
            escalation_patterns=("escalate",),
        )
        assert result is False

    async def test_case_insensitive_match(self) -> None:
        k = _make_knot()
        result = await k.process(
            response=AgentResponse(content="ESCALATE please"),
            escalation_patterns=("escalate",),
        )
        assert result is True

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                response="not a response",  # type: ignore[arg-type]
                escalation_patterns=("escalate",),
            )

    async def test_rejects_empty_patterns(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                response=AgentResponse(content="x"),
                escalation_patterns=(),
            )

    async def test_rejects_invalid_regex(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "valid regex"):
            await k.process(
                response=AgentResponse(content="x"),
                escalation_patterns=("([abc",),
            )
