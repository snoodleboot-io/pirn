"""``BronzeRawIngest`` — preserve-as-received ingestion to a "bronze"
landing zone.

The medallion architecture (bronze → silver → gold) starts with bronze:
the unmodified record from the source plus minimal envelope metadata
(``ingested_at``, ``source_uri``).  No type coercion, no normalisation,
no dedup — anything that mutates the raw row defeats bronze's job as the
last line of audit / replay defence.

Algorithm:
    1. Receive all inputs in ``process()`` and validate.
    2. Fetch source rows via ``source_pool.fetch_all``.
    3. Stamp each row with the current UTC timestamp and ``source_uri``.
    4. Build the INSERT query from ``source_columns`` + metadata columns.
    5. Write stamped rows to the target via ``target_pool.execute_many``.
    6. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — StampBronzeMetadataKnot:
        pirn/domains/data/specializations/medallion/stamp_bronze_metadata_knot.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class BronzeRawIngest(Knot):
    """Ingest source rows into a bronze table with envelope metadata."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        source_columns: Knot | Sequence[str],
        source_uri: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            source_columns=source_columns,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_insert_query(
        target_table: str, source_columns: tuple[str, ...]
    ) -> str:
        all_cols = [*source_columns, "_ingested_at", "_source_uri"]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        source_columns: Any,
        source_uri: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, fetch rows, stamp metadata, insert into bronze table, return summary.

        Args:
            source_pool: Pool to read source rows from.
            source_query: SELECT query to run against the source.
            target_pool: Pool to write bronze rows to.
            target_table: Name of the bronze target table.
            source_columns: Ordered source column names.
            source_uri: URI string to stamp on every row.

        Returns:
            A dict with ``succeeded``, ``target_table``, and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If any string argument is empty, or ``source_columns`` is empty.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "BronzeRawIngest: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "BronzeRawIngest: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "BronzeRawIngest: source_query must be a non-empty string"
            )
        if not isinstance(target_table, str) or not target_table:
            raise ValueError(
                "BronzeRawIngest: target_table must be a non-empty string"
            )
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError(
                "BronzeRawIngest: source_uri must be a non-empty string"
            )
        column_tuple = tuple(source_columns)
        if not column_tuple:
            raise ValueError("BronzeRawIngest: source_columns must be non-empty")
        rows = await source_pool.fetch_all(source_query)
        ingested_at = datetime.now(UTC).isoformat()
        stamped = [(*tuple(r), ingested_at, source_uri) for r in rows]
        insert_query = BronzeRawIngest._build_insert_query(target_table, column_tuple)
        await target_pool.execute_many(insert_query, stamped)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": len(stamped),
        }
