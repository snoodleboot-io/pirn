"""``MartModelKnot`` — aggregates an intermediate layer into a business mart.

Reads from a source table, applies a configurable GROUP BY with metric
columns, and writes the aggregated result to the target mart table.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_table``, ``group_by_columns``,
       ``metric_expressions``, ``target_pool``, and ``target_table`` in
       ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and non-empty metric expressions.
    3. Build and execute the aggregation query against ``source_pool``.
    4. For each result row, INSERT into ``target_table`` via ``target_pool``.
    5. Return a summary dict with ``succeeded``, ``target_table``, and
       ``rows_written``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class MartModelKnot(Knot):
    """Aggregate an intermediate source into a business-ready mart table."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        group_by_columns: Knot | tuple[str, ...],
        metric_expressions: Knot | tuple[str, ...],
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_table=source_table,
            group_by_columns=group_by_columns,
            metric_expressions=metric_expressions,
            target_pool=target_pool,
            target_table=target_table,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _aggregation_query(
        source_table: str,
        group_by_columns: tuple[str, ...],
        metric_expressions: tuple[str, ...],
    ) -> str:
        select_parts = [*group_by_columns, *metric_expressions]
        select_clause = ", ".join(select_parts)
        query = f"SELECT {select_clause} FROM {source_table}"
        if group_by_columns:
            group_clause = ", ".join(group_by_columns)
            query = f"{query} GROUP BY {group_clause}"
        return query

    async def process(
        self,
        *,
        source_pool: Any,
        source_table: Any,
        group_by_columns: Any,
        metric_expressions: Any,
        target_pool: Any,
        target_table: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("MartModelKnot: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("MartModelKnot: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"MartModelKnot: {label} must be a non-empty string")
        group_by_tuple = tuple(group_by_columns)
        metric_tuple = tuple(metric_expressions)
        if not metric_tuple:
            raise ValueError("MartModelKnot: metric_expressions must be non-empty")
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        if group_by_tuple:
            IdentifierValidator.validate_columns("group_by_columns", group_by_tuple)
        rows = await source_pool.fetch_all(
            MartModelKnot._aggregation_query(source_table, group_by_tuple, metric_tuple)
        )
        if not rows:
            return {
                "succeeded": True,
                "target_table": target_table,
                "rows_written": 0,
            }
        col_count = len(rows[0])
        placeholders = ", ".join(["?"] * col_count)
        insert_sql = f"INSERT INTO {target_table} VALUES ({placeholders})"
        rows_written = 0
        for row in rows:
            await target_pool.execute(insert_sql, tuple(row))
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_written": rows_written,
        }
