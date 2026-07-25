"""Unit tests for :class:`ToolCancelledError`."""

from __future__ import annotations

import unittest

from pirn_agents.exceptions.tool_cancelled_error import ToolCancelledError
from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class TestToolCancelledError(unittest.TestCase):
    def test_message_names_tool(self) -> None:
        err = ToolCancelledError("search")
        assert err.tool_name == "search"
        assert str(err) == "Tool 'search' was cancelled"

    def test_message_with_call_id(self) -> None:
        err = ToolCancelledError("search", call_id="c1")
        assert str(err) == "Tool 'search' was cancelled (call_id=c1)"

    def test_is_tool_invocation_error(self) -> None:
        assert isinstance(ToolCancelledError("x"), ToolInvocationError)
