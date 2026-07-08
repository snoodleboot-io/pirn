"""Unit tests for :class:`ToolInvocationError`."""

from __future__ import annotations

import unittest

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class TestToolInvocationError(unittest.TestCase):
    def test_message_without_call_id(self) -> None:
        err = ToolInvocationError("something failed")
        assert err.message == "something failed"
        assert err.call_id is None
        assert str(err) == "something failed"

    def test_message_with_call_id(self) -> None:
        err = ToolInvocationError("something failed", call_id="c1")
        assert err.call_id == "c1"
        assert str(err) == "something failed (call_id=c1)"

    def test_is_exception(self) -> None:
        assert isinstance(ToolInvocationError("x"), Exception)

    def test_raisable(self) -> None:
        with self.assertRaises(ToolInvocationError):
            raise ToolInvocationError("boom")
