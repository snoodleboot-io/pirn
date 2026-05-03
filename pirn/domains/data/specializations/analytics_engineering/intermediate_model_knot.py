"""``IntermediateModelKnot`` — joins staging tables into an intermediate layer.

Joins two staging tables using a configurable join type and ON condition,
writing the joined result into an intermediate target table.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class IntermediateModelKnot(SubTapestry):
    """Join two staging tables into an intermediate layer table."""

    _allowed_join_types: frozenset[str] = frozenset({"INNER", "LEFT", "RIGHT", "FULL"})

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        left_table: str,
        right_table: str,
        join_type: str,
        join_condition: str,
        select_expression: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "IntermediateModelKnot: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "IntermediateModelKnot: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("left_table", left_table),
            ("right_table", right_table),
            ("join_condition", join_condition),
            ("select_expression", select_expression),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"IntermediateModelKnot: {label} must be a non-empty string"
                )
        join_upper = join_type.upper()
        if join_upper not in type(self)._allowed_join_types:
            raise ValueError(
                f"IntermediateModelKnot: join_type must be one of "
                f"{sorted(type(self)._allowed_join_types)!r}, got {join_type!r}"
            )
        IdentifierValidator.validate_column("left_table", left_table)
        IdentifierValidator.validate_column("right_table", right_table)
        IdentifierValidator.validate_column("target_table", target_table)
        self._source_pool = source_pool
        self._left_table = left_table
        self._right_table = right_table
        self._join_type = join_upper
        self._join_condition = join_condition
        self._select_expression = select_expression
        self._target_pool = target_pool
        self._target_table = target_table
        super().__init__(_config=_config, **kwargs)

    @property
    def join_query(self) -> str:
        return (
            f"SELECT {self._select_expression} "
            f"FROM {self._left_table} "
            f"{self._join_type} JOIN {self._right_table} "
            f"ON {self._join_condition}"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Execute the configured join and write results to the intermediate table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and
            ``rows_written`` summarising the join run.
        """
        rows = await self._source_pool.fetch_all(self.join_query)
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
