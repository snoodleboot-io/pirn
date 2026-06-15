"""Security tests: H-4 — ReDoS guard on guardrail and control regex patterns."""

from __future__ import annotations

import unittest

from pirn_agents._regex_utils import _max_pattern_length, compile_safe_pattern


class TestCompileSafePattern(unittest.TestCase):
    def test_valid_short_pattern_compiles(self) -> None:
        p = compile_safe_pattern(r"\bpassword\b", index=0, owner="Test", field="patterns")
        assert p.pattern == r"\bpassword\b"

    def test_pattern_exceeding_max_length_rejected(self) -> None:
        long_pattern = "a" * (_max_pattern_length + 1)
        with self.assertRaises(ValueError) as ctx:
            compile_safe_pattern(long_pattern, index=0, owner="Test", field="patterns")
        assert "maximum pattern length" in str(ctx.exception)

    def test_pattern_at_exact_max_length_accepted(self) -> None:
        pattern = "a" * _max_pattern_length
        p = compile_safe_pattern(pattern, index=0, owner="Test", field="patterns")
        assert len(p.pattern) == _max_pattern_length

    def test_invalid_regex_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            compile_safe_pattern("(unclosed", index=0, owner="Test", field="patterns")
        assert "valid regex" in str(ctx.exception)

    def test_error_message_includes_owner_and_field(self) -> None:
        long_pattern = "x" * (_max_pattern_length + 1)
        with self.assertRaises(ValueError) as ctx:
            compile_safe_pattern(long_pattern, index=2, owner="SafetyCheck", field="deny_patterns")
        msg = str(ctx.exception)
        assert "SafetyCheck" in msg
        assert "deny_patterns[2]" in msg


class TestSafetyCheckReDoSGuard(unittest.TestCase):
    def test_long_pattern_rejected_at_construction(self) -> None:
        from pirn.core.knot_config import KnotConfig
        from pirn.core.knot_factory import knot
        from pirn_agents.control.safety_check import SafetyCheck
        from pirn_agents.types.agent_message import AgentMessage
        from pirn.tapestry import Tapestry

        long_pattern = "a" * (_max_pattern_length + 1)

        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="hello")

        with self.assertRaises(ValueError):
            with Tapestry():
                msg = m(_config=KnotConfig(id="m"))
                SafetyCheck(
                    message=msg,
                    deny_patterns=(long_pattern,),
                    _config=KnotConfig(id="g"),
                )

    def test_empty_deny_patterns_rejected(self) -> None:
        from pirn.core.knot_config import KnotConfig
        from pirn.core.knot_factory import knot
        from pirn_agents.control.safety_check import SafetyCheck
        from pirn_agents.types.agent_message import AgentMessage
        from pirn.tapestry import Tapestry

        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="hello")

        with self.assertRaises(ValueError, msg="empty deny_patterns should raise"):
            with Tapestry():
                msg = m(_config=KnotConfig(id="m"))
                SafetyCheck(message=msg, deny_patterns=(), _config=KnotConfig(id="g"))


class TestHandoffCheckReDoSGuard(unittest.TestCase):
    def test_long_pattern_rejected_at_construction(self) -> None:
        from pirn.core.knot_config import KnotConfig
        from pirn.core.knot_factory import knot
        from pirn_agents.control.handoff_check import HandoffCheck
        from pirn_agents.types.agent_response import AgentResponse
        from pirn.tapestry import Tapestry

        long_pattern = "b" * (_max_pattern_length + 1)

        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="ok", finish_reason="stop")

        with self.assertRaises(ValueError):
            with Tapestry():
                resp = r(_config=KnotConfig(id="r"))
                HandoffCheck(
                    response=resp,
                    escalation_patterns=(long_pattern,),
                    _config=KnotConfig(id="h"),
                )
