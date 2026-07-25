"""``ColumnAwarePostgresPool`` — core :class:`PostgresPool` with column-aware reads.

Reuses core's Postgres pooling lifecycle (asyncpg pool creation, acquire/release,
``close``, the ``DsnScrubber`` credential-safe error path, and the
``_reject_inline_interpolation`` guard) and adds only column-aware reads for the
agents ``sql_query`` tool. asyncpg ``Record``s already carry their keys, so the
column names come from the first record here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.databases.postgres_config import PostgresConfig
from pirn.connectors.databases.postgres_pool import PostgresPool

from pirn_agents.connectors.column_aware_pool import ColumnAwarePool


class ColumnAwarePostgresPool(PostgresPool, ColumnAwarePool):
    """A core ``PostgresPool`` whose reads also carry column names."""

    def __init__(self, config: PostgresConfig | None = None, *, pool: Any = None) -> None:
        """Build the pool from a config or an injected asyncpg pool.

        Args:
            config: Core :class:`PostgresConfig` (dsn or discrete fields).
            pool: Optional pre-built asyncpg-shaped pool, pooled as-is — the seam
                mirrored tests use to run offline without the ``[postgres]`` extra.
        """
        super().__init__(config, pool=pool)

    async def fetch_columns(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[list[str], list[list[Any]]]:
        """Run a read and return ``(column names, rows)``.

        Core's ``_reject_inline_interpolation`` guard is deliberately not applied:
        its ``%[sd]`` / ``{...}`` pattern false-positives on legitimate literals a
        read query commonly contains (``LIKE '%term%'``, JSON ``{...}``), and this
        connector's defences are read-only mode plus bound parameters — Postgres
        uses ``$1`` markers, never ``%s``, so a literal ``%`` is always data.
        """
        connection = await self.acquire()
        try:
            records = await connection.fetch(query, *tuple(parameters or ()))
        finally:
            await self.release(connection)
        columns = list(records[0].keys()) if records else []
        return columns, [list(record.values()) for record in records]
