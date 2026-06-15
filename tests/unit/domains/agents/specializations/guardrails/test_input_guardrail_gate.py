"""Tests for :class:`InputGuardrailGate`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.guardrails.input_guardrail_gate import (
    InputGuardrailGate,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_knot() -> InputGuardrailGate:
    with Tapestry():
        return InputGuardrailGate(
            messages=(),
            deny_patterns=(),
            _config=KnotConfig(id="gate"),
        )


class TestInputGuardrailGateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_redacts_pii_and_passes_clean_messages_through(self) -> None:
        messages = (
            AgentMessage(role="user", content="email me at me@x.com"),
            AgentMessage(role="user", content="hello world"),
        )
        with Tapestry() as t:
            InputGuardrailGate(
                messages=messages,
                deny_patterns=(r"DROP TABLE",),
                pii_patterns=(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                ),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        cleaned = result.outputs["gate"]
        assert isinstance(cleaned, tuple)
        assert cleaned[0].content == "email me at <redacted>"
        assert cleaned[1].content == "hello world"

    async def test_deny_pattern_match_fails_run(self) -> None:
        messages = (
            AgentMessage(role="user", content="please DROP TABLE users"),
        )
        with Tapestry() as t:
            InputGuardrailGate(
                messages=messages,
                deny_patterns=(r"DROP TABLE",),
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_deny_pattern_raises_at_process_time(self) -> None:
        k = _make_knot()
        messages = (AgentMessage(role="user", content="please DROP TABLE users"),)
        with self.assertRaises(ValueError):
            await k.process(messages=messages, deny_patterns=(r"DROP TABLE",))
