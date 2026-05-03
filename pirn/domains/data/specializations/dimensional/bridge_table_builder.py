"""``BridgeTableBuilder`` — Build a many-to-many bridge table with weighting.

A bridge table resolves many-to-many relationships between two dimension
tables. Each row represents an association and carries an optional
``weight_column`` (e.g. allocation percentage, contribution fraction).
Weights default to ``1.0 / group_size`` if ``auto_weight`` is ``True``;
otherwise the caller must supply a weight column in the source.

Behaviour
---------
1. Truncate the existing bridge table (bridge tables are rebuilt in full
   on each run — partial updates yield inconsistent weights).
2. Fetch the source rows.
3. If ``auto_weight`` is ``True``, group source rows by ``group_key_columns``
   and compute ``1.0 / count`` per group.  The computed weight is written to
   ``weight_column``.
4. Insert all rows into the bridge table.

``source_columns`` must include ``left_key_columns``, ``right_key_columns``,
``group_key_columns`` (if ``auto_weight``), and the raw weight column (if
not ``auto_weight``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class BridgeTableBuilder(SubTapestry):
    """Build a many-to-many bridge table, optionally computing proportional weights per group."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        bridge_table: str,
        left_key_columns: Sequence[str],
        right_key_columns: Sequence[str],
        weight_column: str = "weight_factor",
        auto_weight: bool = True,
        group_key_columns: Sequence[str] | None = None,
        source_columns: Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "BridgeTableBuilder: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "BridgeTableBuilder: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "BridgeTableBuilder: source_query must be a non-empty string"
            )
        if not isinstance(bridge_table, str) or not bridge_table:
            raise ValueError(
                "BridgeTableBuilder: bridge_table must be a non-empty string"
            )
        IdentifierValidator.validate_column("bridge_table", bridge_table)
        IdentifierValidator.validate_column("weight_column", weight_column)
        lk_tuple = tuple(left_key_columns)
        rk_tuple = tuple(right_key_columns)
        IdentifierValidator.validate_columns("left_key_columns", lk_tuple)
        IdentifierValidator.validate_columns("right_key_columns", rk_tuple)
        if auto_weight:
            if group_key_columns is None:
                raise ValueError(
                    "BridgeTableBuilder: group_key_columns is required when auto_weight=True"
                )
            gk_tuple = tuple(group_key_columns)
            IdentifierValidator.validate_columns("group_key_columns", gk_tuple)
        else:
            gk_tuple = tuple(group_key_columns) if group_key_columns else ()
        src_col_tuple: tuple[str, ...]
        if source_columns is not None:
            src_col_tuple = tuple(source_columns)
            IdentifierValidator.validate_columns("source_columns", src_col_tuple)
        else:
            seen: list[str] = []
            for c in list(lk_tuple) + list(rk_tuple) + list(gk_tuple):
                if c not in seen:
                    seen.append(c)
            if not auto_weight:
                if weight_column not in seen:
                    seen.append(weight_column)
            src_col_tuple = tuple(seen)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._bridge_table = bridge_table
        self._left_key_columns = lk_tuple
        self._right_key_columns = rk_tuple
        self._weight_column = weight_column
        self._auto_weight = auto_weight
        self._group_key_columns = gk_tuple
        self._source_columns = src_col_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def truncate_query(self) -> str:
        return f"DELETE FROM {self._bridge_table}"

    @property
    def insert_query(self) -> str:
        all_cols = (
            list(self._left_key_columns)
            + list(self._right_key_columns)
            + [self._weight_column]
        )
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._bridge_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Rebuild the bridge table from source rows, computing proportional weights per group if auto_weight is enabled.

        Returns:
            A dict with keys ``succeeded``, ``bridge_table``, and ``rows_inserted``
            summarising the outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        await self._target_pool.execute(self.truncate_query)
        rows_as_dicts = [
            dict(zip(self._source_columns, row)) for row in source_rows
        ]
        if self._auto_weight:
            group_counts: dict[tuple[Any, ...], int] = defaultdict(int)
            for row_dict in rows_as_dicts:
                group_key = tuple(row_dict[k] for k in self._group_key_columns)
                group_counts[group_key] += 1
        rows_inserted = 0
        for row_dict in rows_as_dicts:
            lk_values = tuple(row_dict[k] for k in self._left_key_columns)
            rk_values = tuple(row_dict[k] for k in self._right_key_columns)
            if self._auto_weight:
                group_key = tuple(row_dict[k] for k in self._group_key_columns)
                weight = 1.0 / group_counts[group_key]
            else:
                weight = row_dict[self._weight_column]
            await self._target_pool.execute(
                self.insert_query,
                lk_values + rk_values + (weight,),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "bridge_table": self._bridge_table,
            "rows_inserted": rows_inserted,
        }
