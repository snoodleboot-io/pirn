"""``MartModelKnot`` — aggregates an intermediate layer into a business mart.

Reads from a source table, applies a configurable GROUP BY with metric
columns, and writes the aggregated result to the target mart table.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class MartModelKnot(SubTapestry):
    """Aggregate an intermediate source into a business-ready mart table."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_table: str,
        group_by_columns: Sequence[str],
        metric_expressions: Sequence[str],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "MartModelKnot: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "MartModelKnot: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"MartModelKnot: {label} must be a non-empty string"
                )
        if not metric_expressions:
            raise ValueError(
                "MartModelKnot: metric_expressions must be non-empty"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        group_by_tuple = tuple(group_by_columns)
        if group_by_tuple:
            IdentifierValidator.validate_columns(
                "group_by_columns", group_by_tuple
            )
        self._source_pool = source_pool
        self._source_table = source_table
        self._group_by_columns = group_by_tuple
        self._metric_expressions = list(metric_expressions)
        self._target_pool = target_pool
        self._target_table = target_table
        super().__init__(_config=_config, **kwargs)

    @property
    def aggregation_query(self) -> str:
        select_parts = list(self._group_by_columns) + self._metric_expressions
        select_clause = ", ".join(select_parts)
        query = f"SELECT {select_clause} FROM {self._source_table}"
        if self._group_by_columns:
            group_clause = ", ".join(self._group_by_columns)
            query = f"{query} GROUP BY {group_clause}"
        return query

    async def process(self, **_: Any) -> dict[str, Any]:
        """Run the configured aggregation and write results to the mart table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and
            ``rows_written`` summarising the mart run.
        """
        rows = await self._source_pool.fetch_all(self.aggregation_query)
        if not rows:
            return {
                "succeeded": True,
                "target_table": self._target_table,
                "rows_written": 0,
            }
        col_count = len(rows[0])
        placeholders = ", ".join(["?"] * col_count)
        insert_sql = (
            f"INSERT INTO {self._target_table} VALUES ({placeholders})"
        )
        rows_written = 0
        for row in rows:
            await self._target_pool.execute(insert_sql, tuple(row))
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_written": rows_written,
        }
