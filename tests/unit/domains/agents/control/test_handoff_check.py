"""Unit tests for :class:`HandoffCheck`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.control.handoff_check import HandoffCheck
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_true_when_match(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="please escalate this issue")

        with Tapestry() as t:
            rr = r(_config=KnotConfig(id="r"))
            HandoffCheck(
                response=rr,
                escalation_patterns=("escalate", r"speak to a human"),
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True

    async def test_returns_false_when_no_match(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="here is your answer")

        with Tapestry() as t:
            rr = r(_config=KnotConfig(id="r"))
            HandoffCheck(
                response=rr,
                escalation_patterns=("escalate",),
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["g"] is False


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_patterns(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="x")

        with Tapestry():
            rr = r(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                HandoffCheck(
                    response=rr,
                    escalation_patterns=(),
                    _config=KnotConfig(id="g"),
                )

    def test_rejects_invalid_regex(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="x")

        with Tapestry():
            rr = r(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "valid regex"):
                HandoffCheck(
                    response=rr,
                    escalation_patterns=("([abc",),
                    _config=KnotConfig(id="g"),
                )
