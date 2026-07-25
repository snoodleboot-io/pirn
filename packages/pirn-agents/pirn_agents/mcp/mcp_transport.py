"""``McpTransport`` — provider-neutral async carrier for MCP JSON-RPC frames.

The transport is the sole seam between the thin JSON-RPC core (:class:`~pirn_
agents.mcp.mcp_client.McpClient`) and the outside world. It moves individual
JSON-RPC *messages* (already decoded to plain mappings) in each direction and
knows nothing about MCP semantics — that keeps both concrete transports (stdio,
streamable-HTTP) and the in-memory test double interchangeable behind one
interface.

Concrete transports override :meth:`open`, :meth:`send`, :meth:`receive`, and
:meth:`close`. Because the core owns request/response correlation, the transport
only has to deliver frames in order; it never inspects ``id``/``method``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class McpTransport:
    """Interface every MCP transport must satisfy.

    A transport is stateful (it wraps a live subprocess pipe or HTTP session),
    so it is intentionally *not* a :class:`~pirn.core.pirn_opaque_value.Pirn
    OpaqueValue`: it is internal plumbing held by an
    :class:`~pirn_agents.mcp.mcp_client.McpClient`, never passed through the
    pirn graph directly.
    """

    @property
    def is_open(self) -> bool:
        """Return whether the transport currently holds a live connection."""
        raise NotImplementedError(f"{type(self).__name__} must implement is_open")

    async def open(self) -> None:
        """Establish the underlying connection so frames can flow."""
        raise NotImplementedError(f"{type(self).__name__} must implement open()")

    async def send(self, message: Mapping[str, Any]) -> None:
        """Write one JSON-RPC ``message`` (a plain mapping) to the peer."""
        raise NotImplementedError(f"{type(self).__name__} must implement send()")

    async def receive(self) -> Mapping[str, Any]:
        """Read and return the next JSON-RPC message from the peer."""
        raise NotImplementedError(f"{type(self).__name__} must implement receive()")

    async def close(self) -> None:
        """Tear down the connection idempotently; a second call is a no-op."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")
