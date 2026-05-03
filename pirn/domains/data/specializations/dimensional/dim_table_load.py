"""``DimTableLoad`` — Full dimension table load with configurable SCD logic.

Orchestrates a full dimension load:

1. Fetch source rows.
2. Generate a surrogate key for each new row (auto-increment via
   ``MAX(surrogate_key_column) + 1`` on the target table).
3. Apply either Type 1 (overwrite) or Type 2 (history) SCD logic.

``scd_type`` accepts ``1`` or ``2`` (default ``1``).  For Type 2 the
target table must carry ``valid_from``, ``valid_to``, and ``is_current``
columns whose names are configurable via the corresponding parameters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DimTableLoad(SubTapestry):
    """Full dimension load with surrogate key generation and configurable SCD logic."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        natural_key_columns: Sequence[str],
        non_key_columns: Sequence[str],
        surrogate_key_column: str = "dim_sk",
        scd_type: Literal[1, 2] = 1,
        valid_from_column: str = "valid_from",
        valid_to_column: str = "valid_to",
        current_flag_column: str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DimTableLoad: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DimTableLoad: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "DimTableLoad: source_query must be a non-empty string"
            )
        if not isinstance(target_table, str) or not target_table:
            raise ValueError(
                "DimTableLoad: target_table must be a non-empty string"
            )
        if scd_type not in (1, 2):
            raise ValueError("DimTableLoad: scd_type must be 1 or 2")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column(
            "surrogate_key_column", surrogate_key_column
        )
        nk_tuple = tuple(natural_key_columns)
        nk_non_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("natural_key_columns", nk_tuple)
        IdentifierValidator.validate_columns("non_key_columns", nk_non_tuple)
        if scd_type == 2:
            for col_name, col_val in (
                ("valid_from_column", valid_from_column),
                ("valid_to_column", valid_to_column),
                ("current_flag_column", current_flag_column),
            ):
                IdentifierValidator.validate_column(col_name, col_val)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._natural_key_columns = nk_tuple
        self._non_key_columns = nk_non_tuple
        self._surrogate_key_column = surrogate_key_column
        self._scd_type = scd_type
        self._valid_from_column = valid_from_column
        self._valid_to_column = valid_to_column
        self._current_flag_column = current_flag_column
        self._source_columns = nk_tuple + nk_non_tuple
        super().__init__(_config=_config, **kwargs)

    def _select_current_query(self) -> str:
        cols = ", ".join(self._non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in self._natural_key_columns)
        if self._scd_type == 2:
            return (
                f"SELECT {cols} FROM {self._target_table} "
                f"WHERE {where} AND {self._current_flag_column} = 1"
            )
        return f"SELECT {cols} FROM {self._target_table} WHERE {where}"

    def _max_sk_query(self) -> str:
        return (
            f"SELECT COALESCE(MAX({self._surrogate_key_column}), 0) "
            f"FROM {self._target_table}"
        )

    def _insert_type1_query(self) -> str:
        all_cols = (
            [self._surrogate_key_column]
            + list(self._natural_key_columns)
            + list(self._non_key_columns)
        )
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    def _update_type1_query(self) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in self._non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in self._natural_key_columns)
        return f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"

    def _close_out_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._natural_key_columns)
        return (
            f"UPDATE {self._target_table} "
            f"SET {self._valid_to_column} = ?, {self._current_flag_column} = 0 "
            f"WHERE {where} AND {self._current_flag_column} = 1"
        )

    def _insert_type2_query(self) -> str:
        all_cols = (
            [self._surrogate_key_column]
            + list(self._natural_key_columns)
            + list(self._non_key_columns)
            + [
                self._valid_from_column,
                self._valid_to_column,
                self._current_flag_column,
            ]
        )
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Load source rows into the dimension table applying surrogate key generation and configured SCD logic.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``,
            ``rows_updated`` (Type 1) or ``rows_closed`` (Type 2) summarising the outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        sk_rows = await self._target_pool.fetch_all(self._max_sk_query())
        next_sk = sk_rows[0][0] + 1
        rows_inserted = 0
        rows_updated = 0
        rows_closed = 0
        select_q = self._select_current_query()
        if self._scd_type == 1:
            insert_q = self._insert_type1_query()
            update_q = self._update_type1_query()
            for row in source_rows:
                row_dict = dict(zip(self._source_columns, row))
                nk_values = tuple(row_dict[k] for k in self._natural_key_columns)
                non_key_values = tuple(
                    row_dict[k] for k in self._non_key_columns
                )
                existing = await self._target_pool.fetch_all(
                    select_q, nk_values
                )
                if not existing:
                    await self._target_pool.execute(
                        insert_q,
                        (next_sk,) + nk_values + non_key_values,
                    )
                    next_sk += 1
                    rows_inserted += 1
                else:
                    await self._target_pool.execute(
                        update_q, non_key_values + nk_values
                    )
                    rows_updated += 1
        else:
            insert_q = self._insert_type2_query()
            close_q = self._close_out_query()
            for row in source_rows:
                row_dict = dict(zip(self._source_columns, row))
                nk_values = tuple(row_dict[k] for k in self._natural_key_columns)
                non_key_values = tuple(
                    row_dict[k] for k in self._non_key_columns
                )
                existing = await self._target_pool.fetch_all(
                    select_q, nk_values
                )
                now_iso = datetime.now(timezone.utc).isoformat()
                if not existing:
                    await self._target_pool.execute(
                        insert_q,
                        (next_sk,) + nk_values + non_key_values + (now_iso, None, 1),
                    )
                    next_sk += 1
                    rows_inserted += 1
                    continue
                current_values = tuple(existing[0])
                if current_values == non_key_values:
                    continue
                await self._target_pool.execute(
                    close_q, (now_iso,) + nk_values
                )
                rows_closed += 1
                await self._target_pool.execute(
                    insert_q,
                    (next_sk,) + nk_values + non_key_values + (now_iso, None, 1),
                )
                next_sk += 1
                rows_inserted += 1
        result: dict[str, Any] = {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
        }
        if self._scd_type == 1:
            result["rows_updated"] = rows_updated
        else:
            result["rows_closed"] = rows_closed
        return result
