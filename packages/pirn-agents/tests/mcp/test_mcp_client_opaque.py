"""Contract test for the :class:`McpClient` opaque-boundary decision (WS1·S6).

PIR-681 resolves the boundary in favour of a defensive opaque `McpClient`: it
stays an internal object (the graph-travelling values are the already-opaque
`McpConnector` / `McpTool` wrappers), but it inherits `PirnOpaqueValue` so a live
client accidentally injected as a config value still crosses the content-addressed
Knot IO boundary opaquely (identity token) rather than being descended into.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_connector import McpConnector
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.mcp.mcp_transport import McpTransport
from pirn_agents.tool import Tool


class TestMcpClientOpaqueBoundary(unittest.TestCase):
    def test_client_is_opaque_value(self) -> None:
        # Arrange / Act / Assert: the defensive decision — McpClient is opaque.
        self.assertTrue(issubclass(McpClient, PirnOpaqueValue))

    def test_client_audit_dict_is_identity_token(self) -> None:
        # Arrange: a client bound to a bare (unconnected) transport double.
        client = McpClient(_InertTransport())

        # Act: the opaque serialiser emits the default identity token.
        token = client._pirn_audit_dict()

        # Assert: an identity token, not a descent into live transport state.
        self.assertIsInstance(token, str)
        self.assertIn("McpClient@", token)

    def test_wrappers_remain_opaque(self) -> None:
        # Arrange / Act / Assert: the intended boundary carriers are opaque too.
        self.assertTrue(issubclass(McpConnector, ConnectorBase))
        self.assertTrue(issubclass(McpConnector, PirnOpaqueValue))
        self.assertTrue(issubclass(McpTool, Tool))
        self.assertTrue(issubclass(McpTool, PirnOpaqueValue))


class _InertTransport(McpTransport):
    """A do-nothing transport: the client is never driven in these checks."""

    @property
    def is_open(self) -> bool:
        return False

    async def open(self) -> None:
        return None

    async def send(self, message: Mapping[str, Any]) -> None:
        return None

    async def receive(self) -> Mapping[str, Any]:
        raise AssertionError("_InertTransport.receive must not be called")

    async def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
