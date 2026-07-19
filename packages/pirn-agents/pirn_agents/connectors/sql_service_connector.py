"""``SqlServiceConnector`` — a pooled async SQL connector (F16-S2 / PIR-355).

A :class:`~pirn_agents.connector_base.ConnectorBase` subclass that holds a single
pooled backend connection/pool for the whole run (the pooling lever, AD-3) and
runs parameterized queries against it. Two drivers are supported, both lazily
imported so importing this module stays backend-free:

* ``"aiosqlite"`` (default, ``[sql]`` extra) — a persistent async connection,
* ``"asyncpg"`` (``[postgres]`` extra) — a real connection pool.

Safety levers mirror the F6 ``sql_query`` tool:

* **read-only mode** (default) rejects any non-``SELECT``/``WITH`` statement via
  :meth:`~pirn_agents.tools.sql._read_only_sql_guard.ReadOnlySqlGuard.assert_read_only`;
* **parameterized queries** — bound parameters are passed to the driver, never
  interpolated into the SQL text;
* **row cap** — the materialised result set is truncated to ``max_rows``.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import Any

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.tools.sql._read_only_sql_guard import ReadOnlySqlGuard


class SqlServiceConnector(ConnectorBase):
    """Pooled async SQL connector with read-only mode and a row cap."""

    def __init__(
        self,
        *,
        driver: str = "aiosqlite",
        database: str | None = None,
        dsn: str | None = None,
        read_only: bool = True,
        max_rows: int = 1000,
        credential: CredentialRef | None = None,
        connection: Any | None = None,
    ) -> None:
        """Configure the driver, connection target, and safety caps.

        Args:
            driver: ``"aiosqlite"`` or ``"asyncpg"``.
            database: SQLite database path/URI (``aiosqlite`` driver).
            dsn: Postgres DSN (``asyncpg`` driver); falls back to the credential
                secret when omitted.
            read_only: When ``True`` (default), only ``SELECT``/``WITH`` queries
                are allowed.
            max_rows: Maximum number of rows returned; extra rows are dropped.
            credential: Optional :class:`CredentialRef` (a DSN for ``asyncpg``).
            connection: Optional pre-built connection/pool pooled as-is (tests).

        Raises:
            TypeError: If ``credential`` is not a ``CredentialRef`` or ``None``.
            ValueError: If ``driver`` is unknown or ``max_rows`` is not positive.
        """
        super().__init__(credential=credential)
        if driver not in ("aiosqlite", "asyncpg"):
            raise ValueError(
                f"SqlServiceConnector: driver must be 'aiosqlite'|'asyncpg', got {driver!r}"
            )
        if max_rows <= 0:
            raise ValueError(f"SqlServiceConnector: max_rows must be positive, got {max_rows}")
        self._driver = driver
        self._database = database
        self._dsn = dsn
        self._read_only = read_only
        self._max_rows = max_rows
        self._guard = ReadOnlySqlGuard()
        if connection is not None:
            self._client = connection

    async def _create_client(self) -> Any:
        """Build the pooled connection/pool lazily for the configured driver."""
        if self._driver == "aiosqlite":
            aiosqlite = self._require("sql", "aiosqlite")
            return await aiosqlite.connect(self._database)
        asyncpg = self._require("postgres", "asyncpg")
        dsn = self._dsn or (self._credential.reveal() if self._credential is not None else None)
        return await asyncpg.create_pool(dsn=dsn)

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Run ``query`` with bound ``parameters`` and return ``(columns, rows)``.

        Raises:
            ValueError: In read-only mode, if ``query`` is not a single read.
        """
        if self._read_only:
            self._guard.assert_read_only(query)
        client = await self._get_client()
        if self._driver == "aiosqlite":
            return await self._execute_aiosqlite(client, query, parameters)
        return await self._execute_asyncpg(client, query, parameters)

    async def _execute_aiosqlite(
        self, client: Any, query: str, parameters: Sequence[Any] | None
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Execute against an ``aiosqlite`` connection and cap the rows."""
        cursor = await client.execute(query, tuple(parameters or ()))
        try:
            fetched = await cursor.fetchall()
            columns = [description[0] for description in cursor.description or ()]
        finally:
            await cursor.close()
        rows = [list(row) for row in fetched][: self._max_rows]
        return columns, rows

    async def _execute_asyncpg(
        self, client: Any, query: str, parameters: Sequence[Any] | None
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Execute against an ``asyncpg`` pool and cap the rows."""
        async with client.acquire() as connection:
            records = await connection.fetch(query, *tuple(parameters or ()))
        capped = list(records)[: self._max_rows]
        columns = list(capped[0].keys()) if capped else []
        rows = [list(record.values()) for record in capped]
        return columns, rows

    async def close(self) -> None:
        """Close the pooled connection/pool deterministically and idempotently.

        Both ``aiosqlite`` connections and ``asyncpg`` pools expose an *async*
        ``close``; the base class only awaits ``aclose``, so this override awaits
        whichever closer the driver provides.
        """
        client: Any = self._client
        if client is not None:
            closer = getattr(client, "aclose", None) or getattr(client, "close", None)
            if callable(closer):
                result = closer()
                if inspect.isawaitable(result):
                    await result
            self._client = None
        self._clear_credentials()
