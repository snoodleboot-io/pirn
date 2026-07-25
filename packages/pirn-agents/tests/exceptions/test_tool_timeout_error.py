"""Unit tests for :class:`ToolTimeoutError`."""

from __future__ import annotations

import unittest

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError
from pirn_agents.exceptions.tool_timeout_error import ToolTimeoutError


class TestToolTimeoutError(unittest.TestCase):
    def test_message_names_tool_and_timeout(self) -> None:
        err = ToolTimeoutError("search", timeout=1.5)
        assert err.tool_name == "search"
        assert err.timeout == 1.5
        assert str(err) == "Tool 'search' timed out after 1.5s"

    def test_message_with_call_id(self) -> None:
        err = ToolTimeoutError("search", timeout=2.0, call_id="c1")
        assert str(err) == "Tool 'search' timed out after 2.0s (call_id=c1)"

    def test_is_tool_invocation_error(self) -> None:
        assert isinstance(ToolTimeoutError("x", 1.0), ToolInvocationError)
