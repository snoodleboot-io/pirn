"""``FullRefreshExtract`` — truncate and reload a target table from a
source query on every run.

Every run is a complete refresh: fetch all source rows, delete all target
rows, then insert the fresh set.  No state, no watermark — the target
converges to exact parity with the source.

Use this when:
- The source dataset is small enough to read in full each run.
- You need *exact* parity with the source after every run (no drift
  from incremental gaps).
- You don't have a reliable watermark column.

Algorithm:
    1. Receive ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, and ``insert_query`` in ``process()``.
    2. Validate pool types, non-empty strings, and the alphanumeric
       guard on ``target_table``.
    3. Fetch all source rows via ``source_pool.fetch_all``.
    4. Truncate the target via ``DELETE FROM <target_table>``.
    5. Insert all fetched rows via ``target_pool.execute_many``.
    6. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class FullRefreshExtract(Knot):
    """Drop + reload a target table from a source query on every run."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        insert_query: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            insert_query=insert_query,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        insert_query: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, fetch rows, truncate target, insert fresh rows, return summary.

        Args:
            source_pool: Pool to read rows from.
            source_query: SELECT query to execute against the source.
            target_pool: Pool to write rows to.
            target_table: Name of the table to truncate and reload.
            insert_query: INSERT query to execute for each row batch.

        Returns:
            A dict with ``succeeded``, ``target_table``, and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If any string argument is empty or ``target_table`` is non-alphanumeric.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("FullRefreshExtract: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("FullRefreshExtract: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("FullRefreshExtract: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("FullRefreshExtract: target_table must be a non-empty string")
        if not target_table.replace("_", "").isalnum():
            raise ValueError(
                f"FullRefreshExtract: target_table {target_table!r} must be "
                "alphanumeric (plus underscores)"
            )
        if not isinstance(insert_query, str) or not insert_query:
            raise ValueError("FullRefreshExtract: insert_query must be a non-empty string")
        rows = await source_pool.fetch_all(source_query)
        await target_pool.execute(f"DELETE FROM {target_table}")
        await target_pool.execute_many(insert_query, [tuple(r) for r in rows])
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": len(rows),
        }
