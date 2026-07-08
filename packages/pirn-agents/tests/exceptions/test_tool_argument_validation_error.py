"""Unit tests for :class:`ToolArgumentValidationError`."""

from __future__ import annotations

import unittest

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class TestToolArgumentValidationError(unittest.TestCase):
    def test_carries_detail(self) -> None:
        detail = {"q": "must be a string"}
        err = ToolArgumentValidationError("search", detail=detail)
        assert err.tool_name == "search"
        assert err.detail == detail

    def test_message_includes_tool_and_detail(self) -> None:
        detail = {"q": "required"}
        err = ToolArgumentValidationError("search", detail=detail)
        assert "search" in str(err)
        assert "required" in str(err)

    def test_message_with_call_id(self) -> None:
        err = ToolArgumentValidationError("search", detail={"q": "bad"}, call_id="c1")
        assert str(err).endswith("(call_id=c1)")

    def test_is_tool_invocation_error(self) -> None:
        assert isinstance(
            ToolArgumentValidationError("x", detail={}), ToolInvocationError
        )
