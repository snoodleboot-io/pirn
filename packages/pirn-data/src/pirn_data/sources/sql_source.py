"""``SqlSource`` — execute a SQL query via :class:`DatabaseConnectionPool` and
materialise the results as a :class:`DataBatch`.

This is the universal "read from any SQL-compliant backend" knot.  Any pool
implementation (SQLite, DuckDB, Postgres, MySQL, BigQuery, …) works as long as
it satisfies the :class:`DatabaseConnectionPool` interface.

Algorithm:
    1. Validate ``pool`` (DatabaseConnectionPool) and ``query`` (non-empty string).
    2. Call ``await pool.fetch_all(query)`` to execute the query and retrieve rows.
    3. Normalise each row to ``dict[str, Any]``.
    4. Return a :class:`DataBatch` stamped with ``source_uri``, ``fetched_at=now(UTC)``,
       and the optional schema.

References:
    [1] :class:`pirn.connectors.database_connection_pool.DatabaseConnectionPool` —
        pluggable SQL backend abstraction.
    [2] :class:`pirn_data.sources.file_source.FileSource` —
        analogous file-based source.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema


class SqlSource(Source):
    """Execute a SQL query and emit a :class:`DataBatch`.

    Constructor
    -----------
    pool:
        Any :class:`DatabaseConnectionPool` (SQLite, DuckDB, Postgres, …).
    query:
        SQL query string.  Must not contain inline string interpolation —
        use the driver's bind syntax for parameters.
    schema:
        Optional :class:`DataSchema`.  When provided, carried forward on
        the resulting :class:`DataBatch`.
    source_uri:
        Lineage hint.  When ``None``, defaults to
        ``f"sql://{type(pool).__name__}"``.
    """

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        schema: Knot | DataSchema | None = None,
        source_uri: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            schema=schema,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        schema: DataSchema | None = None,
        source_uri: str | None = None,
        **_: Any,
    ) -> DataBatch:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("SqlSource: pool must be a DatabaseConnectionPool instance")
        if not isinstance(query, str) or not query:
            raise ValueError("SqlSource: query must be a non-empty string")
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError("SqlSource: schema must be a DataSchema instance")
        resolved_uri = source_uri or f"sql://{type(pool).__name__}"
        rows_raw = await pool.fetch_all(query)
        rows = tuple(_normalise_row(r) for r in rows_raw)
        return DataBatch(
            rows=rows,
            schema=schema if schema is not None else DataSchema(),
            source_uri=resolved_uri,
            fetched_at=datetime.now(UTC),
        )


def _normalise_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    if hasattr(row, "_fields"):
        return row._asdict()
    return dict(enumerate(row))  # type: ignore[arg-type]
