"""``SqlServiceConnector`` — read-only, row-capped SQL over a core pool (F16-S2).

A thin :class:`~pirn_agents.connector_base.ConnectorBase` over a core
:class:`~pirn.connectors.database_connection_pool.DatabaseConnectionPool`. The
connection pooling, credential scrubbing, and inline-interpolation guard come from
core's ``SqlitePool`` / ``PostgresPool`` (via the column-aware subclasses); this
connector adds only the three things core's pool abstraction does not provide:

* **read-only mode** (default) rejects any non-``SELECT``/``WITH`` statement via
  :meth:`~pirn_agents.tools.sql._read_only_sql_guard.ReadOnlySqlGuard.assert_read_only`;
* **column-aware results** — ``(columns, rows)``, which the ``sql_query`` tool
  returns to the LLM (core's ``fetch_all`` is column-blind);
* **row cap** — the result set is truncated to ``max_rows``.

The pool is built lazily via :class:`ConnectorBase`'s construct-once lifecycle, so
importing this module — and constructing the connector — stays backend-free.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.databases.postgres_config import PostgresConfig
from pirn.connectors.databases.sqlite_config import SqliteConfig

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.connectors.column_aware_pool import ColumnAwarePool
from pirn_agents.connectors.column_aware_postgres_pool import ColumnAwarePostgresPool
from pirn_agents.connectors.column_aware_sqlite_pool import ColumnAwareSqlitePool
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.tools.sql._read_only_sql_guard import ReadOnlySqlGuard


class SqlServiceConnector(ConnectorBase):
    """Read-only, row-capped, column-aware SQL over a core connection pool."""

    def __init__(
        self,
        *,
        driver: str = "aiosqlite",
        database: str | None = None,
        dsn: str | None = None,
        read_only: bool = True,
        max_rows: int = 1000,
        credential: CredentialRef | None = None,
        pool: ColumnAwarePool | None = None,
    ) -> None:
        """Configure the driver, connection target, and safety caps.

        Args:
            driver: ``"aiosqlite"`` or ``"asyncpg"`` — selects the core pool.
            database: SQLite database path/URI (``aiosqlite`` driver).
            dsn: Postgres DSN (``asyncpg`` driver); falls back to the credential
                secret when omitted.
            read_only: When ``True`` (default), only ``SELECT``/``WITH`` queries
                are allowed.
            max_rows: Maximum number of rows returned; extra rows are dropped.
            credential: Optional :class:`CredentialRef` (a DSN for ``asyncpg``).
            pool: Optional pre-built :class:`ColumnAwarePool`, pooled as-is — the
                seam mirrored tests use to run offline.

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
        if pool is not None:
            self._client = pool

    async def _create_client(self) -> ColumnAwarePool:
        """Build the core-backed column-aware pool for the configured driver."""
        # pyright can't see the config fields as __init__ params: core's
        # @connection_config decorator wraps dataclasses.dataclass but is not
        # annotated @dataclass_transform, so the synthesised __init__ is invisible.
        # The construction is runtime-correct (core's own tests build these the same
        # way). Tracked upstream as PIR-749.
        if self._driver == "aiosqlite":
            return ColumnAwareSqlitePool(
                SqliteConfig(database=self._database or ":memory:")  # pyright: ignore[reportCallIssue]
            )
        dsn = self._dsn or (self._credential.reveal() if self._credential is not None else None)
        return ColumnAwarePostgresPool(PostgresConfig(dsn=dsn))  # pyright: ignore[reportCallIssue]

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Run ``query`` with bound ``parameters`` and return ``(columns, rows)``.

        Raises:
            ValueError: In read-only mode, if ``query`` is not a single read.
            ImportError: If the driver's backend package is not installed, named
                with the agents extra to install (the core pool underneath reports
                the ``pirn[...]`` extra, which an agents user does not have).
        """
        if self._read_only:
            self._guard.assert_read_only(query)
        pool: ColumnAwarePool = await self._get_client()
        try:
            columns, rows = await pool.fetch_columns(query, parameters)
        except ImportError as exc:
            extra = "sql" if self._driver == "aiosqlite" else "postgres"
            raise ImportError(
                f"SqlServiceConnector: the {self._driver!r} backend is required; "
                f'install it with: pip install "pirn-agents[{extra}]"'
            ) from exc
        return columns, rows[: self._max_rows]

    async def close(self) -> None:
        """Close the pooled backend deterministically and scrub credentials.

        Core pools expose an *async* ``close``; the ``ConnectorBase`` default only
        awaits ``aclose``, so this override awaits the pool's ``close`` directly.
        Calling ``close`` again is a safe no-op.
        """
        pool: ColumnAwarePool | None = self._client
        if pool is not None:
            await pool.close()
            self._client = None
        self._clear_credentials()
