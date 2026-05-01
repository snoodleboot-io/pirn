"""``ReadHighWaterMarkKnot`` — internal helper for
:class:`WatermarkIncrementalExtract`.

Returns ``MAX(watermark_column)`` from the target table, or ``None``
when the target is empty (initial load). Pool is held as instance state.
Identifier guards reject anything non-alphanumeric.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class ReadHighWaterMarkKnot(Knot):
    """Read ``MAX(watermark_column)`` from a target table."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        table: str,
        watermark_column: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ReadHighWaterMarkKnot: pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("table", table),
            ("watermark_column", watermark_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ReadHighWaterMarkKnot: {label} must be a non-empty string"
                )
            if not value.replace("_", "").isalnum():
                raise ValueError(
                    f"ReadHighWaterMarkKnot: {label} {value!r} must be "
                    "alphanumeric (plus underscores)"
                )
        self._pool = pool
        self._table = table
        self._watermark_column = watermark_column
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Any:
        fetch_all = getattr(self._pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                "ReadHighWaterMarkKnot: pool does not support fetch_all()"
            )
        rows = await fetch_all(
            f"SELECT MAX({self._watermark_column}) FROM {self._table}"
        )
        if not rows:
            return None
        return rows[0][0]
