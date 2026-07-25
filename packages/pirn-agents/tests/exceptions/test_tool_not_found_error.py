"""Unit tests for :class:`ToolNotFoundError`."""

from __future__ import annotations

import unittest

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError


class TestToolNotFoundError(unittest.TestCase):
    def test_message_names_tool(self) -> None:
        err = ToolNotFoundError("search")
        assert err.tool_name == "search"
        assert str(err) == "Tool 'search' not found"

    def test_message_with_call_id(self) -> None:
        err = ToolNotFoundError("search", call_id="c1")
        assert str(err) == "Tool 'search' not found (call_id=c1)"

    def test_is_tool_invocation_error(self) -> None:
        assert isinstance(ToolNotFoundError("x"), ToolInvocationError)
