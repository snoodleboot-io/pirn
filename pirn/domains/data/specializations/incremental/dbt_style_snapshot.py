"""``DbtStyleSnapshot`` — dbt-compatible timestamp/check snapshot strategy.

Implements the core of dbt's snapshot materialisation:

1. Compute a hash of the tracked columns for every source row.
2. Look up the currently-active snapshot row for each natural key.
3. Detect which rows have changed by comparing hashes.
4. Close old rows (set ``valid_to`` and ``is_current = 0``).
5. Insert new rows for changed or new natural keys.

The approach is equivalent to dbt's ``strategy: check`` / ``strategy:
timestamp`` modes collapsed into a single hash-based implementation.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. For each source row, compute an MD5 hash of the pipe-joined tracked
       column values.
    3. Query the target for the currently-active row by natural key.
    4. If no active row exists, insert a new row with ``is_current = 1``.
    5. If the hash differs from the stored hash, close the current row
       (set ``valid_to = now``, ``is_current = 0``) then insert a new one.
    6. If the hash matches, skip the row (no change).
    7. Return a summary dict with ``rows_inserted`` and ``rows_closed``.

Math:
    Let :math:`V` be the sequence of tracked column values for a row.
    $
    \\text{hash}(V) = \\text{MD5}\\!\\left(\\bigcup_{v \\in V} \\text{str}(v) + \\text{"|"}\\right)
    $

References:
    [1] dbt — snapshot strategy documentation:
        https://docs.getdbt.com/docs/build/snapshots
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
    [4] Python — hashlib.md5 with usedforsecurity=False:
        https://docs.python.org/3/library/hashlib.html
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class DbtStyleSnapshot(Knot):
    """dbt-compatible snapshot: hash-based change detection with SCD Type 2 rows."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        tracked_columns: Knot | tuple[str, ...],
        valid_from_column: Knot | str = "dbt_valid_from",
        valid_to_column: Knot | str = "dbt_valid_to",
        current_flag_column: Knot | str = "dbt_is_current",
        row_hash_column: Knot | str = "dbt_scd_id",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            key_columns=key_columns,
            tracked_columns=tracked_columns,
            valid_from_column=valid_from_column,
            valid_to_column=valid_to_column,
            current_flag_column=current_flag_column,
            row_hash_column=row_hash_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _compute_row_hash(tracked_values: tuple[Any, ...]) -> str:
        raw = "|".join(str(v) for v in tracked_values)
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def _select_current_query(
        target_table: str,
        key_columns: tuple[str, ...],
        row_hash_column: str,
        current_flag_column: str,
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"SELECT {row_hash_column} FROM {target_table} "
            f"WHERE {where} AND {current_flag_column} = 1"
        )

    @staticmethod
    def _close_out_query(
        target_table: str,
        key_columns: tuple[str, ...],
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"UPDATE {target_table} "
            f"SET {valid_to_column} = ?, {current_flag_column} = 0 "
            f"WHERE {where} AND {current_flag_column} = 1"
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        valid_from_column: str,
        valid_to_column: str,
        current_flag_column: str,
        row_hash_column: str,
    ) -> str:
        all_cols = [
            *source_columns,
            valid_from_column,
            valid_to_column,
            current_flag_column,
            row_hash_column,
        ]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        tracked_columns: Any,
        valid_from_column: Any = "dbt_valid_from",
        valid_to_column: Any = "dbt_valid_to",
        current_flag_column: Any = "dbt_is_current",
        row_hash_column: Any = "dbt_scd_id",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("DbtStyleSnapshot: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("DbtStyleSnapshot: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("DbtStyleSnapshot: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("DbtStyleSnapshot: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        for col_label, col_name in (
            ("valid_from_column", valid_from_column),
            ("valid_to_column", valid_to_column),
            ("current_flag_column", current_flag_column),
            ("row_hash_column", row_hash_column),
        ):
            IdentifierValidator.validate_column(col_label, col_name)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                f"DbtStyleSnapshot: key_columns and tracked_columns overlap on {sorted(overlap)!r}"
            )
        source_columns = key_tuple + tracked_tuple
        select_q = DbtStyleSnapshot._select_current_query(
            target_table, key_tuple, row_hash_column, current_flag_column
        )
        close_q = DbtStyleSnapshot._close_out_query(
            target_table, key_tuple, valid_to_column, current_flag_column
        )
        insert_q = DbtStyleSnapshot._insert_query(
            target_table,
            source_columns,
            valid_from_column,
            valid_to_column,
            current_flag_column,
            row_hash_column,
        )
        source_rows = await source_pool.fetch_all(source_query)
        rows_inserted = 0
        rows_closed = 0
        now_iso = datetime.now(UTC).isoformat()
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            tracked_values = tuple(row_dict[k] for k in tracked_tuple)
            new_hash = DbtStyleSnapshot._compute_row_hash(tracked_values)
            existing = await target_pool.fetch_all(select_q, key_values)
            if not existing:
                await target_pool.execute(
                    insert_q,
                    key_values + tracked_values + (now_iso, None, 1, new_hash),
                )
                rows_inserted += 1
                continue
            current_hash = existing[0][0]
            if current_hash == new_hash:
                continue
            await target_pool.execute(close_q, (now_iso, *key_values))
            rows_closed += 1
            await target_pool.execute(
                insert_q,
                key_values + tracked_values + (now_iso, None, 1, new_hash),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
