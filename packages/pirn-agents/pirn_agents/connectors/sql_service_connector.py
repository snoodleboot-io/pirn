"""``SqlServiceConnector`` — read-only, row-capped SQL over a core pool (F16-S2).

A thin :class:`~pirn.connectors.connector_base.ConnectorBase` over a core
:class:`~pirn.connectors.database_connection_pool.DatabaseConnectionPool`. The
connection pooling, credential scrubbing, and inline-interpolation guard come from
core's ``SqlitePool`` / ``PostgresPool`` (via the column-aware subclasses); this
connector adds only the three things core's pool abstraction does not provide:

* **read-only mode** (default) rejects any non-``SELECT``/``WITH`` statement via
  :meth:`~pirn_agents.tools.sql.read_only_sql_guard.ReadOnlySqlGuard.assert_read_only`;
* **column-aware results** — ``(columns, rows)``, which the ``sql_query`` tool
  returns to the LLM (core's ``fetch_all`` is column-blind);
* **row cap** — the result set is truncated to ``max_rows``.

The pool is built lazily via :class:`ConnectorBase`'s construct-once lifecycle, so
importing this module — and constructing the connector — stays backend-free.

It also declares
:class:`~pirn_agents.tools.sql.sql_connector.SqlConnector`, the tool-side SQL
interface, so the connector is accepted by
:class:`~pirn_agents.tools.sql.sql_query_tool.SqlQueryTool` (which type-checks its
injected connector) and therefore by ``Bundles.data_toolset`` (PIR-786). Both bases derive
from ``PirnOpaqueValue``, so the two lineages linearise cleanly and ``ConnectorBase``
keeps precedence for the lifecycle and audit behaviour.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.connector_base import ConnectorBase
from pirn.connectors.databases.postgres_config import PostgresConfig
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.core.optional_dependency import OptionalDependency
from pirn.security.credential_ref import CredentialRef

from pirn_agents.connectors.column_aware_pool import ColumnAwarePool
from pirn_agents.connectors.column_aware_postgres_pool import ColumnAwarePostgresPool
from pirn_agents.connectors.column_aware_sqlite_pool import ColumnAwareSqlitePool
from pirn_agents.tools.sql.read_only_sql_guard import ReadOnlySqlGuard
from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqlServiceConnector(ConnectorBase, SqlConnector):
    """Read-only, row-capped, column-aware SQL over a core connection pool.

    Implements the :class:`SqlConnector` interface so ``sql_query`` accepts it.
    """

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
                are allowed. When ``False``, writes are permitted and committed
                before :meth:`execute` returns.
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
        """Build the core-backed column-aware pool for the configured driver.

        The driver is required here, through
        :meth:`~pirn.core.optional_dependency.OptionalDependency.require`, so a
        missing backend fails at the seam with the workspace's standard
        ``pip install "pirn-agents[sql]"`` / ``[postgres]`` message. ``execute`` used to
        re-wrap an ``ImportError`` escaping the pool in a hand-written hint of
        its own, which both duplicated that machinery and could relabel an
        ``ImportError`` raised from *inside* an installed driver as a missing
        extra (PIR-873).

        Raises:
            ImportError: If the configured driver is not installed, naming the
                ``pirn-agents`` extra that installs it.
        """
        if self._driver == "aiosqlite":
            OptionalDependency.require("aiosqlite", extra="sql", package="pirn-agents")
            return ColumnAwareSqlitePool(SqliteConfig(database=self._database or ":memory:"))
        OptionalDependency.require("asyncpg", extra="postgres", package="pirn-agents")
        dsn = self._dsn or (self._credential.reveal() if self._credential is not None else None)
        return ColumnAwarePostgresPool(PostgresConfig(dsn=dsn))

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Run ``query`` with bound ``parameters`` and return ``(columns, rows)``.

        Under ``read_only=False`` a write is durable once this returns, and a
        statement that raises leaves nothing behind — the pool honours
        ``ColumnAwarePool``'s durability contract.

        Each statement stands alone; this connector exposes no multi-statement
        transaction seam. A caller who needs one may open it on the pool directly
        and keep it open across calls made through here: the pool ends only the
        transactions its own statements opened, so a read issued through this
        method will neither commit nor roll back the caller's work.

        Raises:
            ValueError: In read-only mode, if ``query`` is not a single read.
            ImportError: If the driver's backend package is not installed, named
                with the agents extra to install; raised by
                :meth:`_create_client` through ``OptionalDependency.require``,
                not re-wrapped here.
        """
        if self._read_only:
            self._guard.assert_read_only(query)
        pool: ColumnAwarePool = await self._get_client()
        columns, rows = await pool.fetch_columns(query, parameters)
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
