"""Interface for async database connection pools.

Concrete implementations (asyncpg, aiosqlite, DuckDB, ...) inherit from
:class:`DatabaseConnectionPool` and override every method. Following the
existing pirn interface convention (see ``pirn/streaming/base.py``,
``pirn/triggers/base.py``, ``pirn/backends/base/run_history.py``) — base
methods raise :class:`NotImplementedError` naming the concrete subclass
that failed to implement them.
"""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class DatabaseConnectionPool:
    """Interface every connector pool implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.databases.sqlite_pool.SqlitePool`
      - :class:`pirn.domains.connectors.databases.duckdb_pool.DuckdbPool`
      - :class:`pirn.domains.connectors.databases.postgres_pool.PostgresPool`
    """

    async def acquire(self) -> Any:
        """Return a connection (or async-context manager wrapping one)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement acquire()"
        )

    async def release(self, connection: Any) -> None:
        """Return a previously-acquired connection to the pool."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement release()"
        )

    async def close(self) -> None:
        """Close the pool and release any underlying resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat pools as opaque.

        Concrete pool implementations wrap engine-specific clients
        (asyncpg, aiosqlite, DuckDB, …) that are not pydantic-compatible.
        Pirn IO validation just needs ``isinstance(value, DatabaseConnectionPool)``;
        this short-circuit avoids pydantic descending into engine internals.
        """
        return core_schema.is_instance_schema(cls)
