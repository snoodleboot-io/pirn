"""``McpConnector`` — a pooled, self-healing MCP session for the pirn graph.

Wrapping an :class:`~pirn_agents.mcp.mcp_client.McpClient` in
:class:`~pirn.connectors.connector_base.ConnectorBase` gives the F2 lifecycle for
free: the session is built once on first use and reused for the whole run (the
pooling lever), and :meth:`close` tears it down deterministically. On top of that
this connector adds *self-healing*: :meth:`session` returns the live client, and
if the transport has dropped it reconnects under a core
:class:`~pirn.core.knot_retry_policy.KnotRetryPolicy` (exponential, capped, full
jitter) via a freshly-built transport — so callers get one long-lived session with no
per-call reconnect, and a blip is absorbed transparently.

A ``transport_factory`` (not a live transport) is injected so each reconnect
attempt starts from a clean transport; ``sleep`` and ``rng`` are injectable so
backoff timing is deterministic under test. The ``mcp`` backend stays lazy — it
is only touched when a concrete transport actually opens.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from pirn.connectors.connector_base import ConnectorBase
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.security.credential_ref import CredentialRef

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
        reconnect: KnotRetryPolicy | None = None,
        rng: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        credential: CredentialRef | None = None,
    ) -> None:
        """Configure how sessions are built and how reconnect backs off.

        Args:
            transport_factory: Zero-arg callable returning a fresh
                :class:`McpTransport` for each (re)connect.
            client_name/client_version/protocol_version: Forwarded to the
                :class:`McpClient` handshake.
            reconnect: The reconnect schedule — ``max_attempts`` connect
                attempts in total, backing off exponentially between them.
                Defaults to ``KnotRetryPolicy(max_attempts=5, base_delay=0.05,
                max_delay=2.0)``.
            rng: Zero-arg jitter draw in ``[0, 1)`` forwarded to the policy;
                defaults to :func:`random.random`.
            sleep: Awaitable sleep used between attempts; defaults to
                :func:`asyncio.sleep` (injectable for deterministic tests).
            credential: Optional credential reference (F2 scrubbing).

        Raises:
            TypeError: If ``transport_factory`` is not callable, or
                ``reconnect`` is not a :class:`KnotRetryPolicy`.
        """
        super().__init__(credential=credential)
        if not callable(transport_factory):
            raise TypeError(
                "McpConnector: transport_factory must be callable, "
                f"got {type(transport_factory).__name__}"
            )
        policy = (
            reconnect
            if reconnect is not None
            else KnotRetryPolicy(max_attempts=5, base_delay=0.05, max_delay=2.0)
        )
        if not isinstance(policy, KnotRetryPolicy):
            raise TypeError(
                f"McpConnector: reconnect must be a KnotRetryPolicy, got {type(reconnect).__name__}"
            )
        self._transport_factory: Callable[[], McpTransport] = transport_factory
        self._client_name: str = client_name
        self._client_version: str = client_version
        self._protocol_version: str = protocol_version
        self._reconnect: KnotRetryPolicy = policy
        self._rng: Callable[[], float] | None = rng
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

        The retry loop is core's
        :meth:`~pirn.core.knot_retry_policy.KnotRetryPolicy.run` over
        :meth:`_attempt_connect`, on the ``reconnect`` schedule.

        Raises:
            McpError: If every attempt fails; chains the last underlying error.
        """
        try:
            return await self._reconnect.run(
                self._attempt_connect, call_id="mcp_connect", sleep=self._sleep, rng=self._rng
            )
        except Exception as exc:
            raise McpError(
                f"McpConnector: reconnect exhausted after {self._reconnect.max_attempts} attempt(s)"
            ) from exc

    async def _attempt_connect(self) -> McpClient:
        """One connect attempt from a clean slate; a failure leaves no client behind."""
        self._client = None
        try:
            return await self._get_client()
        except Exception:
            self._client = None
            raise
