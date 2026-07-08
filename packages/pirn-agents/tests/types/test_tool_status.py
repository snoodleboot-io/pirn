"""Unit tests for :class:`ToolStatus`."""

from __future__ import annotations

import unittest

from pirn_agents.types.tool_status import ToolStatus


class TestToolStatus(unittest.TestCase):
    def test_members_and_values(self) -> None:
        assert ToolStatus.OK.value == "ok"
        assert ToolStatus.ERROR.value == "error"
        assert ToolStatus.TIMEOUT.value == "timeout"
        assert ToolStatus.CANCELLED.value == "cancelled"

    def test_is_str_subclass(self) -> None:
        assert isinstance(ToolStatus.OK, str)
        assert ToolStatus.OK == "ok"

    def test_lookup_by_value(self) -> None:
        assert ToolStatus("timeout") is ToolStatus.TIMEOUT
