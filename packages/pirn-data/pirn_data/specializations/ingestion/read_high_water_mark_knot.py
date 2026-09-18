"""``ReadHighWaterMarkKnot`` — return ``MAX(watermark_column)`` from a
target table, or ``None`` when the table is empty (initial load).

Pool, table, and watermark_column arrive as resolved values in
``process()``.  Identifier guards (alphanumeric + underscores) are
applied there for defence-in-depth.

Algorithm:
    1. Receive ``pool``, ``table``, and ``watermark_column`` in ``process()``.
    2. Validate pool type, non-empty strings, and alphanumeric guards.
    3. Issue ``SELECT MAX(watermark_column) FROM table``.
    4. Return the scalar result, or ``None`` if the table is empty.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
    [2] pirn — WatermarkIncrementalExtract:
        pirn_data/specializations/ingestion/watermark_incremental_extract.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.pool_validator import PoolValidator


class ReadHighWaterMarkKnot(Knot):
    """Read ``MAX(watermark_column)`` from a target table."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        table: Knot | str,
        watermark_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            table=table,
            watermark_column=watermark_column,
            _config=_config,
            **kwargs,
        )

    async def process(self, *, pool: Any, table: Any, watermark_column: Any, **_: Any) -> Any:
        """Validate inputs, query the MAX watermark, and return the value or None.

        Args:
            pool: The database connection pool.
            table: The target table name (alphanumeric + underscores).
            watermark_column: The watermark column name (alphanumeric + underscores).

        Returns:
            The maximum watermark value, or ``None`` when the table is empty.

        Raises:
            TypeError: If ``pool`` is not a ``DatabaseConnectionPool``.
            ValueError: If identifiers are empty or contain invalid characters.
        """
        PoolValidator.validate_pools("ReadHighWaterMarkKnot", pool=pool)
        for label, value in (
            ("table", table),
            ("watermark_column", watermark_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ReadHighWaterMarkKnot: {label} must be a non-empty string")
            if not value.replace("_", "").isalnum():
                raise ValueError(
                    f"ReadHighWaterMarkKnot: {label} {value!r} must be "
                    "alphanumeric (plus underscores)"
                )
        rows = await pool.fetch_all(f"SELECT MAX({watermark_column}) FROM {table}")
        if not rows:
            return None
        return rows[0][0]
