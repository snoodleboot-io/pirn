"""``McpSessionPool`` — vend one long-lived MCP session per server across a run.

The pool maps a stable server *key* to a single
:class:`~pirn_agents.mcp.mcp_connector.McpConnector`, constructing that connector
exactly once and returning the same instance on every :meth:`acquire_connector`.
Because each connector already reuses one client and self-heals with backoff, the
pool guarantees at most one live session per server for the whole run (no
per-call reconnect) while still letting an application talk to several servers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_connector import McpConnector


class McpSessionPool:
    """Construct-once-per-key vending of :class:`McpConnector` sessions."""

    def __init__(
        self,
        *,
        factories: Mapping[str, Callable[[], McpConnector]] | None = None,
    ) -> None:
        """Seed the pool with optional per-key connector factories.

        Args:
            factories: Mapping of server key to a zero-arg callable that builds
                that server's :class:`McpConnector`. More can be added later via
                :meth:`register`.
        """
        self._factories: dict[str, Callable[[], McpConnector]] = dict(factories or {})
        self._connectors: dict[str, McpConnector] = {}

    def register(self, key: str, factory: Callable[[], McpConnector]) -> None:
        """Register (or replace) the connector ``factory`` for server ``key``.

        Raises:
            TypeError: If ``key`` is not a non-empty string or ``factory`` is not
                callable.
        """
        if not isinstance(key, str) or not key:
            raise TypeError(f"McpSessionPool.register: key must be a non-empty string, got {key!r}")
        if not callable(factory):
            raise TypeError(
                f"McpSessionPool.register: factory must be callable, got {type(factory).__name__}"
            )
        self._factories[key] = factory

    def acquire_connector(self, key: str) -> McpConnector:
        """Return the single connector for ``key``, building it once on demand.

        Raises:
            KeyError: If no factory is registered for ``key``.
            TypeError: If the factory returns a non-:class:`McpConnector`.
        """
        connector = self._connectors.get(key)
        if connector is not None:
            return connector
        factory = self._factories.get(key)
        if factory is None:
            raise KeyError(f"McpSessionPool: no connector factory registered for key {key!r}")
        built = factory()
        if not isinstance(built, McpConnector):
            raise TypeError(
                f"McpSessionPool: factory for {key!r} must return an McpConnector, "
                f"got {type(built).__name__}"
            )
        self._connectors[key] = built
        return built

    async def session(self, key: str) -> McpClient:
        """Return the live client for ``key`` via its pooled connector."""
        return await self.acquire_connector(key).session()

    async def close(self) -> None:
        """Close every pooled connector and forget them, idempotently."""
        for connector in self._connectors.values():
            await connector.close()
        self._connectors.clear()
