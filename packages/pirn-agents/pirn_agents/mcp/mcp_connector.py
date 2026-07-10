"""``McpConnector`` — a pooled, self-healing MCP session for the pirn graph.

Wrapping an :class:`~pirn_agents.mcp.mcp_client.McpClient` in
:class:`~pirn_agents.connector_base.ConnectorBase` gives the F2 lifecycle for
free: the session is built once on first use and reused for the whole run (the
pooling lever), and :meth:`close` tears it down deterministically. On top of that
this connector adds *self-healing*: :meth:`session` returns the live client, and
if the transport has dropped it reconnects with exponential, jittered backoff via
a freshly-built transport — so callers get one long-lived session with no
per-call reconnect, and a blip is absorbed transparently.

A ``transport_factory`` (not a live transport) is injected so each reconnect
attempt starts from a clean transport; ``sleep`` and ``jitter`` are injectable so
backoff timing is deterministic under test. The ``mcp`` backend stays lazy — it
is only touched when a concrete transport actually opens.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_transport import McpTransport


class McpConnector(ConnectorBase):
    """Pooled MCP session with reconnect-on-failure backoff."""

    def __init__(
        self,
        *,
        transport_factory: Callable[[], McpTransport],
        client_name: str = "pirn-agents",
        client_version: str = "0.9.0",
        protocol_version: str = "2025-06-18",
        max_reconnect_attempts: int = 5,
        backoff_base: float = 0.05,
        backoff_cap: float = 2.0,
        jitter: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        credential: CredentialRef | None = None,
    ) -> None:
        """Configure how sessions are built and how reconnect backs off.

        Args:
            transport_factory: Zero-arg callable returning a fresh
                :class:`McpTransport` for each (re)connect.
            client_name/client_version/protocol_version: Forwarded to the
                :class:`McpClient` handshake.
            max_reconnect_attempts: Total connect attempts before giving up
                (must be >= 1).
            backoff_base: Base delay (seconds) for the exponential schedule.
            backoff_cap: Upper bound (seconds) on the exponential term.
            jitter: Zero-arg callable returning extra seconds added to each
                delay; defaults to ``U[0, backoff_base)``.
            sleep: Awaitable sleep used between attempts; defaults to
                :func:`asyncio.sleep` (injectable for deterministic tests).
            credential: Optional credential reference (F2 scrubbing).

        Raises:
            TypeError: If ``transport_factory`` is not callable.
            ValueError: If ``max_reconnect_attempts`` is less than 1.
        """
        super().__init__(credential=credential)
        if not callable(transport_factory):
            raise TypeError(
                "McpConnector: transport_factory must be callable, "
                f"got {type(transport_factory).__name__}"
            )
        if max_reconnect_attempts < 1:
            raise ValueError(
                f"McpConnector: max_reconnect_attempts must be >= 1, got {max_reconnect_attempts}"
            )
        self._transport_factory: Callable[[], McpTransport] = transport_factory
        self._client_name: str = client_name
        self._client_version: str = client_version
        self._protocol_version: str = protocol_version
        self._max_reconnect_attempts: int = max_reconnect_attempts
        self._backoff_base: float = backoff_base
        self._backoff_cap: float = backoff_cap
        self._jitter: Callable[[], float] = jitter if jitter is not None else self._default_jitter
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )

    async def _create_client(self) -> McpClient:
        """Build a fresh transport, wrap it in a client, and open the session.

        On a handshake/transport failure the partially-opened client is closed
        before the error propagates so no subprocess or socket leaks.
        """
        transport = self._transport_factory()
        client = McpClient(
            transport,
            client_name=self._client_name,
            client_version=self._client_version,
            protocol_version=self._protocol_version,
        )
        try:
            await client.open()
        except BaseException:
            await client.aclose()
            raise
        return client

    async def session(self) -> McpClient:
        """Return the live session, reconnecting with backoff if it dropped.

        Fast path: when a client is already built and open it is returned with no
        awaiting of backoff. Otherwise the connector (re)connects under the
        exponential+jitter schedule.
        """
        client = self._client
        if isinstance(client, McpClient) and client.is_open:
            return client
        return await self._connect_with_backoff()

    async def _connect_with_backoff(self) -> McpClient:
        """Attempt to (re)build the session, sleeping between failed attempts.

        Raises:
            McpError: If every attempt fails; chains the last underlying error.
        """
        last_exc: BaseException | None = None
        for attempt in range(self._max_reconnect_attempts):
            self._client = None
            try:
                return await self._get_client()
            except Exception as exc:
                last_exc = exc
                self._client = None
                if attempt + 1 >= self._max_reconnect_attempts:
                    break
                await self._sleep(self._delay_for(attempt))
        raise McpError(
            f"McpConnector: reconnect exhausted after {self._max_reconnect_attempts} attempt(s)"
        ) from last_exc

    def _delay_for(self, attempt: int) -> float:
        """Return the backoff delay for a zero-based ``attempt`` index."""
        capped = min(self._backoff_cap, self._backoff_base * (2**attempt))
        return capped + self._jitter()

    def _default_jitter(self) -> float:
        """Return default jitter drawn from ``U[0, backoff_base)`` seconds."""
        return random.random() * self._backoff_base
