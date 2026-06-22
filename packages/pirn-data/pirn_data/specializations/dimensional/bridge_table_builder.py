"""``BridgeTableBuilder`` — build a many-to-many bridge table with weighting.

A bridge table resolves many-to-many relationships between two dimension
tables. Each row represents an association and carries an optional
``weight_column`` (e.g. allocation percentage, contribution fraction).
Weights default to ``1.0 / group_size`` if ``auto_weight`` is ``True``;
otherwise the caller must supply a weight column in the source.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``bridge_table``, ``left_key_columns``, ``right_key_columns``,
       ``weight_column``, ``auto_weight``, ``group_key_columns``, and
       ``source_columns`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and auto_weight/group_key_columns consistency.
    3. Truncate the existing bridge table (bridge tables are rebuilt in full
       on each run — partial updates yield inconsistent weights).
    4. Fetch the source rows and map them to dicts by ``source_columns``.
    5. If ``auto_weight`` is ``True``, group source rows by
       ``group_key_columns`` and compute ``1.0 / count`` per group.
    6. Insert all rows into the bridge table.
    7. Return a summary dict with ``succeeded``, ``bridge_table``, and
       ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class BridgeTableBuilder(Knot):
    """Build a many-to-many bridge table, optionally computing proportional weights per group."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        bridge_table: Knot | str,
        left_key_columns: Knot | tuple[str, ...],
        right_key_columns: Knot | tuple[str, ...],
        weight_column: Knot | str,
        auto_weight: Knot | bool,
        group_key_columns: Knot | tuple[str, ...],
        source_columns: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            bridge_table=bridge_table,
            left_key_columns=left_key_columns,
            right_key_columns=right_key_columns,
            weight_column=weight_column,
            auto_weight=auto_weight,
            group_key_columns=group_key_columns,
            source_columns=source_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _truncate_query(bridge_table: str) -> str:
        return f"DELETE FROM {bridge_table}"

    @staticmethod
    def _insert_query(
        bridge_table: str,
        left_key_columns: tuple[str, ...],
        right_key_columns: tuple[str, ...],
        weight_column: str,
    ) -> str:
        all_cols = [*left_key_columns, *right_key_columns, weight_column]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {bridge_table} ({col_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        bridge_table: Any,
        left_key_columns: Any,
        right_key_columns: Any,
        weight_column: Any,
        auto_weight: Any,
        group_key_columns: Any,
        source_columns: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("BridgeTableBuilder: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("BridgeTableBuilder: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("BridgeTableBuilder: source_query must be a non-empty string")
        if not isinstance(bridge_table, str) or not bridge_table:
            raise ValueError("BridgeTableBuilder: bridge_table must be a non-empty string")
        IdentifierValidator.validate_column("bridge_table", bridge_table)
        if not isinstance(weight_column, str) or not weight_column:
            raise ValueError("BridgeTableBuilder: weight_column must be a non-empty string")
        IdentifierValidator.validate_column("weight_column", weight_column)
        lk_tuple = tuple(left_key_columns)
        rk_tuple = tuple(right_key_columns)
        IdentifierValidator.validate_columns("left_key_columns", lk_tuple)
        IdentifierValidator.validate_columns("right_key_columns", rk_tuple)
        if auto_weight:
            if not group_key_columns:
                raise ValueError(
                    "BridgeTableBuilder: group_key_columns is required when auto_weight=True"
                )
            gk_tuple = tuple(group_key_columns)
            IdentifierValidator.validate_columns("group_key_columns", gk_tuple)
        else:
            gk_tuple = tuple(group_key_columns) if group_key_columns else ()
        src_col_tuple = tuple(source_columns)
        if src_col_tuple:
            IdentifierValidator.validate_columns("source_columns", src_col_tuple)
        else:
            seen: list[str] = []
            for c in [*lk_tuple, *rk_tuple, *gk_tuple]:
                if c not in seen:
                    seen.append(c)
            if not auto_weight and weight_column not in seen:
                seen.append(weight_column)
            src_col_tuple = tuple(seen)

        source_rows = await source_pool.fetch_all(source_query)
        await target_pool.execute(self._truncate_query(bridge_table))
        rows_as_dicts = [dict(zip(src_col_tuple, row, strict=False)) for row in source_rows]
        if auto_weight:
            group_counts: dict[tuple[Any, ...], int] = defaultdict(int)
            for row_dict in rows_as_dicts:
                group_key = tuple(row_dict[k] for k in gk_tuple)
                group_counts[group_key] += 1
        insert_q = self._insert_query(bridge_table, lk_tuple, rk_tuple, weight_column)
        rows_inserted = 0
        for row_dict in rows_as_dicts:
            lk_values = tuple(row_dict[k] for k in lk_tuple)
            rk_values = tuple(row_dict[k] for k in rk_tuple)
            if auto_weight:
                group_key = tuple(row_dict[k] for k in gk_tuple)
                weight = 1.0 / group_counts[group_key]  # type: ignore[possibly-undefined]
            else:
                weight = row_dict[weight_column]
            await target_pool.execute(insert_q, (*lk_values, *rk_values, weight))
            rows_inserted += 1
        return {
            "succeeded": True,
            "bridge_table": bridge_table,
            "rows_inserted": rows_inserted,
        }
