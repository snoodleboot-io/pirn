"""ReDoS guard on guardrail and control regex patterns (H-4).

Native pirn-agents test for :class:`SafePatternCompiler` and the guard's use by
the ``SafetyCheck`` / ``HandoffCheck`` control knots. (Previously lived under
``pirn-core/tests`` as a cross-domain test; relocated here since it exercises
pirn-agents code only — pirn-core is imported, never tested.)

``SafetyCheck`` and ``HandoffCheck`` validate patterns in ``process()`` rather
than at construction (Knot Design Rule 3 — validation belongs in ``process()``,
never ``__init__``; PIR-856 removed the up-front constructor validation these
tests used to exercise), so the guard tests below call ``process()`` directly.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.tapestry import Tapestry

from pirn_agents.control.handoff_check import HandoffCheck
from pirn_agents.control.safety_check import SafetyCheck
from pirn_agents.security._safe_pattern_compiler import SafePatternCompiler
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse

_COMPILER = SafePatternCompiler()
_MAX = _COMPILER.max_pattern_length


class TestCompileSafePattern(unittest.TestCase):
    def test_valid_short_pattern_compiles(self) -> None:
        p = _COMPILER.compile_safe_pattern(r"\bpassword\b", index=0, owner="Test", field="patterns")
        assert p.pattern == r"\bpassword\b"

    def test_pattern_exceeding_max_length_rejected(self) -> None:
        long_pattern = "a" * (_MAX + 1)
        with self.assertRaises(ValueError) as ctx:
            _COMPILER.compile_safe_pattern(long_pattern, index=0, owner="Test", field="patterns")
        assert "maximum pattern length" in str(ctx.exception)

    def test_pattern_at_exact_max_length_accepted(self) -> None:
        pattern = "a" * _MAX
        p = _COMPILER.compile_safe_pattern(pattern, index=0, owner="Test", field="patterns")
        assert len(p.pattern) == _MAX

    def test_invalid_regex_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _COMPILER.compile_safe_pattern("(unclosed", index=0, owner="Test", field="patterns")
        assert "valid regex" in str(ctx.exception)

    def test_error_message_includes_owner_and_field(self) -> None:
        long_pattern = "x" * (_MAX + 1)
        with self.assertRaises(ValueError) as ctx:
            _COMPILER.compile_safe_pattern(
                long_pattern, index=2, owner="SafetyCheck", field="deny_patterns"
            )
        msg = str(ctx.exception)
        assert "SafetyCheck" in msg
        assert "deny_patterns[2]" in msg


class TestSafetyCheckReDoSGuard(unittest.IsolatedAsyncioTestCase):
    async def test_long_pattern_rejected_at_process_time(self) -> None:
        long_pattern = "a" * (_MAX + 1)
        message = AgentMessage(role="user", content="hello")

        @KnotFactory.knot
        async def m() -> AgentMessage:
            return message

        with Tapestry():
            msg = m(_config=KnotConfig(id="m"))
            check = SafetyCheck(
                message=msg,
                deny_patterns=(long_pattern,),
                _config=KnotConfig(id="g"),
            )

        with self.assertRaises(ValueError):
            await check.process(message=message, deny_patterns=(long_pattern,))

    async def test_empty_deny_patterns_rejected(self) -> None:
        message = AgentMessage(role="user", content="hello")

        @KnotFactory.knot
        async def m() -> AgentMessage:
            return message

        with Tapestry():
            msg = m(_config=KnotConfig(id="m"))
            check = SafetyCheck(message=msg, deny_patterns=(), _config=KnotConfig(id="g"))

        with self.assertRaises(ValueError, msg="empty deny_patterns should raise"):
            await check.process(message=message, deny_patterns=())


class TestHandoffCheckReDoSGuard(unittest.IsolatedAsyncioTestCase):
    async def test_long_pattern_rejected_at_process_time(self) -> None:
        long_pattern = "b" * (_MAX + 1)
        response = AgentResponse(content="ok", finish_reason="stop")

        @KnotFactory.knot
        async def r() -> AgentResponse:
            return response

        with Tapestry():
            resp = r(_config=KnotConfig(id="r"))
            check = HandoffCheck(
                response=resp,
                escalation_patterns=(long_pattern,),
                _config=KnotConfig(id="h"),
            )

        with self.assertRaises(ValueError):
            await check.process(response=response, escalation_patterns=(long_pattern,))
