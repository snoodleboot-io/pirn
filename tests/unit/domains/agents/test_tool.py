"""Unit tests for :class:`Tool`."""

from __future__ import annotations

import unittest

from pirn_agents.tool import Tool


class TestToolInterface(unittest.IsolatedAsyncioTestCase):
    def test_name_raises_not_implemented(self) -> None:
        tool = Tool()
        with self.assertRaises(NotImplementedError):
            _ = tool.name

    def test_description_raises_not_implemented(self) -> None:
        tool = Tool()
        with self.assertRaises(NotImplementedError):
            _ = tool.description

    def test_parameters_schema_raises_not_implemented(self) -> None:
        tool = Tool()
        with self.assertRaises(NotImplementedError):
            _ = tool.parameters_schema

    async def test_invoke_raises_not_implemented(self) -> None:
        tool = Tool()
        with self.assertRaises(NotImplementedError):
            await tool.invoke({})

    def test_clear_credentials_is_noop_by_default(self) -> None:
        tool = Tool()
        tool._clear_credentials()  # must not raise
