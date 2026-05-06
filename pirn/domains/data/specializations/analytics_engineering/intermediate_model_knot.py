"""``IntermediateModelKnot`` — joins staging tables into an intermediate layer.

Joins two staging tables using a configurable join type and ON condition,
writing the joined result into an intermediate target table.

Algorithm:
    1. Receive resolved ``source_pool``, ``left_table``, ``right_table``,
       ``join_type``, ``join_condition``, ``select_expression``,
       ``target_pool``, and ``target_table`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, allowed join types,
       and identifier safety.
    3. Build and execute the JOIN query against ``source_pool``.
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

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class IntermediateModelKnot(Knot):
    """Join two staging tables into an intermediate layer table."""

    _allowed_join_types: ClassVar[frozenset[str]] = frozenset({"INNER", "LEFT", "RIGHT", "FULL"})

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        left_table: Knot | str,
        right_table: Knot | str,
        join_type: Knot | str,
        join_condition: Knot | str,
        select_expression: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            left_table=left_table,
            right_table=right_table,
            join_type=join_type,
            join_condition=join_condition,
            select_expression=select_expression,
            target_pool=target_pool,
            target_table=target_table,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _join_query(
        left_table: str,
        right_table: str,
        join_type: str,
        join_condition: str,
        select_expression: str,
    ) -> str:
        return (
            f"SELECT {select_expression} "
            f"FROM {left_table} "
            f"{join_type} JOIN {right_table} "
            f"ON {join_condition}"
        )

    async def process(
        self,
        *,
        source_pool: Any,
        left_table: Any,
        right_table: Any,
        join_type: Any,
        join_condition: Any,
        select_expression: Any,
        target_pool: Any,
        target_table: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("IntermediateModelKnot: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("IntermediateModelKnot: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("left_table", left_table),
            ("right_table", right_table),
            ("join_condition", join_condition),
            ("select_expression", select_expression),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"IntermediateModelKnot: {label} must be a non-empty string")
        if not isinstance(join_type, str):
            raise ValueError("IntermediateModelKnot: join_type must be a non-empty string")
        join_upper = join_type.upper()
        if join_upper not in self._allowed_join_types:
            raise ValueError(
                f"IntermediateModelKnot: join_type must be one of "
                f"{sorted(self._allowed_join_types)!r}, got {join_type!r}"
            )
        IdentifierValidator.validate_column("left_table", left_table)
        IdentifierValidator.validate_column("right_table", right_table)
        IdentifierValidator.validate_column("target_table", target_table)
        rows = await source_pool.fetch_all(
            IntermediateModelKnot._join_query(
                left_table, right_table, join_upper, join_condition, select_expression
            )
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
