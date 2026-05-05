"""``DimTableLoad`` — full dimension table load with configurable SCD logic.

Orchestrates a full dimension load:

1. Fetch source rows.
2. Generate a surrogate key for each new row (auto-increment via
   ``MAX(surrogate_key_column) + 1`` on the target table).
3. Apply either Type 1 (overwrite) or Type 2 (history) SCD logic.

``scd_type`` accepts ``1`` or ``2`` (default ``1``).  For Type 2 the
target table must carry ``valid_from``, ``valid_to``, and ``is_current``
columns whose names are configurable via the corresponding parameters.

Algorithm:
    1. Receive resolved inputs in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and scd_type membership.
    3. Fetch all source rows and determine the next surrogate key from
       ``MAX(surrogate_key_column)`` on the target table.
    4. For each source row look up whether the natural key already exists.
       - Type 1: INSERT new rows; UPDATE changed rows.
       - Type 2: INSERT new rows with history columns; close out existing
         rows before inserting the new version.
    5. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``rows_updated`` (Type 1) or ``rows_closed``
       (Type 2).

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class DimTableLoad(Knot):
    """Full dimension load with surrogate key generation and configurable SCD logic."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        natural_key_columns: Knot | tuple[str, ...],
        non_key_columns: Knot | tuple[str, ...],
        surrogate_key_column: Knot | str,
        scd_type: Knot | int,
        valid_from_column: Knot | str,
        valid_to_column: Knot | str,
        current_flag_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            natural_key_columns=natural_key_columns,
            non_key_columns=non_key_columns,
            surrogate_key_column=surrogate_key_column,
            scd_type=scd_type,
            valid_from_column=valid_from_column,
            valid_to_column=valid_to_column,
            current_flag_column=current_flag_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_current_query(
        target_table: str,
        natural_key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
        scd_type: int,
        current_flag_column: str,
    ) -> str:
        cols = ", ".join(non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in natural_key_columns)
        if scd_type == 2:
            return (
                f"SELECT {cols} FROM {target_table} "
                f"WHERE {where} AND {current_flag_column} = 1"
            )
        return f"SELECT {cols} FROM {target_table} WHERE {where}"

    @staticmethod
    def _max_sk_query(target_table: str, surrogate_key_column: str) -> str:
        return f"SELECT COALESCE(MAX({surrogate_key_column}), 0) FROM {target_table}"

    @staticmethod
    def _insert_type1_query(
        target_table: str,
        surrogate_key_column: str,
        natural_key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        all_cols = [surrogate_key_column, *natural_key_columns, *non_key_columns]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({col_list}) VALUES ({placeholders})"

    @staticmethod
    def _update_type1_query(
        target_table: str,
        natural_key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in natural_key_columns)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where}"

    @staticmethod
    def _close_out_query(
        target_table: str,
        natural_key_columns: tuple[str, ...],
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in natural_key_columns)
        return (
            f"UPDATE {target_table} "
            f"SET {valid_to_column} = ?, {current_flag_column} = 0 "
            f"WHERE {where} AND {current_flag_column} = 1"
        )

    @staticmethod
    def _insert_type2_query(
        target_table: str,
        surrogate_key_column: str,
        natural_key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
        valid_from_column: str,
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [
            surrogate_key_column,
            *natural_key_columns,
            *non_key_columns,
            valid_from_column,
            valid_to_column,
            current_flag_column,
        ]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({col_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        natural_key_columns: Any,
        non_key_columns: Any,
        surrogate_key_column: Any,
        scd_type: Any,
        valid_from_column: Any,
        valid_to_column: Any,
        current_flag_column: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("DimTableLoad: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("DimTableLoad: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("DimTableLoad: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("DimTableLoad: target_table must be a non-empty string")
        if scd_type not in (1, 2):
            raise ValueError("DimTableLoad: scd_type must be 1 or 2")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("surrogate_key_column", surrogate_key_column)
        nk_tuple = tuple(natural_key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("natural_key_columns", nk_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        if scd_type == 2:
            for col_name, col_val in (
                ("valid_from_column", valid_from_column),
                ("valid_to_column", valid_to_column),
                ("current_flag_column", current_flag_column),
            ):
                IdentifierValidator.validate_column(col_name, col_val)
        source_columns = (*nk_tuple, *non_key_tuple)
        source_rows = await source_pool.fetch_all(source_query)
        sk_rows = await target_pool.fetch_all(
            self._max_sk_query(target_table, surrogate_key_column)
        )
        next_sk = sk_rows[0][0] + 1
        rows_inserted = 0
        rows_updated = 0
        rows_closed = 0
        select_q = self._select_current_query(
            target_table, nk_tuple, non_key_tuple, scd_type, current_flag_column
        )
        if scd_type == 1:
            insert_q = self._insert_type1_query(
                target_table, surrogate_key_column, nk_tuple, non_key_tuple
            )
            update_q = self._update_type1_query(target_table, nk_tuple, non_key_tuple)
            for row in source_rows:
                row_dict = dict(zip(source_columns, row, strict=False))
                nk_values = tuple(row_dict[k] for k in nk_tuple)
                non_key_values = tuple(row_dict[k] for k in non_key_tuple)
                existing = await target_pool.fetch_all(select_q, nk_values)
                if not existing:
                    await target_pool.execute(
                        insert_q,
                        (next_sk, *nk_values, *non_key_values),
                    )
                    next_sk += 1
                    rows_inserted += 1
                else:
                    await target_pool.execute(update_q, (*non_key_values, *nk_values))
                    rows_updated += 1
        else:
            insert_q = self._insert_type2_query(
                target_table,
                surrogate_key_column,
                nk_tuple,
                non_key_tuple,
                valid_from_column,
                valid_to_column,
                current_flag_column,
            )
            close_q = self._close_out_query(
                target_table, nk_tuple, valid_to_column, current_flag_column
            )
            for row in source_rows:
                row_dict = dict(zip(source_columns, row, strict=False))
                nk_values = tuple(row_dict[k] for k in nk_tuple)
                non_key_values = tuple(row_dict[k] for k in non_key_tuple)
                existing = await target_pool.fetch_all(select_q, nk_values)
                now_iso = datetime.now(UTC).isoformat()
                if not existing:
                    await target_pool.execute(
                        insert_q,
                        (next_sk, *nk_values, *non_key_values, now_iso, None, 1),
                    )
                    next_sk += 1
                    rows_inserted += 1
                    continue
                current_values = tuple(existing[0])
                if current_values == non_key_values:
                    continue
                await target_pool.execute(close_q, (now_iso, *nk_values))
                rows_closed += 1
                await target_pool.execute(
                    insert_q,
                    (next_sk, *nk_values, *non_key_values, now_iso, None, 1),
                )
                next_sk += 1
                rows_inserted += 1
        result: dict[str, Any] = {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
        }
        if scd_type == 1:
            result["rows_updated"] = rows_updated
        else:
            result["rows_closed"] = rows_closed
        return result
