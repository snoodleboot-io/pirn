"""``ScdType7MergeKnot`` — surrogate-keyed Type 2 history merge for SCD Type 7.

Type 7 SCD (Kimball-style "hybrid surrogate-keyed history") keeps the
business key as a natural identifier and adds a surrogate key
(``scd_id``) that uniquely identifies each historical version. Each
inserted row receives a fresh surrogate id; queries that need the
current attribute values join through the surrogate, while history
queries filter on the effective-date range exactly as in Type 2.

This knot:

* Reads the existing current rows from the target
  (``current_flag_column = 1``).
* Closes (expires) any current row whose primary-key match has changed
  attributes.
* Inserts a new row for every changed-or-new primary key, allocating a
  fresh surrogate id (``MAX(scd_id) + 1`` for the batch).

Surrogate id allocation is per-merge, not per-row, so the column does
not need a database-managed sequence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType7MergeKnot(Knot):
    """Merge a source row stream into a Type 7 surrogate-keyed target."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_keys: Sequence[str],
        column_names: Sequence[str],
        surrogate_key_column: str,
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType7MergeKnot: target_pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns(
            "primary_keys", primary_key_tuple
        )
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        IdentifierValidator.validate_column(
            "surrogate_key_column", surrogate_key_column
        )
        IdentifierValidator.validate_column(
            "effective_date_column", effective_date_column
        )
        IdentifierValidator.validate_column(
            "expiry_date_column", expiry_date_column
        )
        IdentifierValidator.validate_column(
            "current_flag_column", current_flag_column
        )
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(
                f"ScdType7MergeKnot: primary_keys not in column_names: {missing}"
            )
        bookkeeping = (
            surrogate_key_column,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                "ScdType7MergeKnot: surrogate / effective / expiry / "
                f"current columns must not appear in column_names: {overlap}"
            )
        self._target_pool = target_pool
        self._target_table = target_table
        self._primary_keys = primary_key_tuple
        self._column_names = column_tuple
        self._surrogate_key_column = surrogate_key_column
        self._effective_date_column = effective_date_column
        self._expiry_date_column = expiry_date_column
        self._current_flag_column = current_flag_column
        self._non_key_columns = tuple(
            c for c in column_tuple if c not in primary_key_tuple
        )
        super().__init__(rows=rows, _config=_config, **kwargs)

    @property
    def select_query(self) -> str:
        column_list = ", ".join(self._column_names)
        return (
            f"SELECT {column_list} FROM {self._target_table} "
            f"WHERE {self._current_flag_column} = 1"
        )

    @property
    def max_surrogate_query(self) -> str:
        return (
            f"SELECT COALESCE(MAX({self._surrogate_key_column}), 0) "
            f"FROM {self._target_table}"
        )

    @property
    def insert_query(self) -> str:
        all_cols = (
            [self._surrogate_key_column]
            + list(self._column_names)
            + [
                self._effective_date_column,
                self._expiry_date_column,
                self._current_flag_column,
            ]
        )
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    @property
    def expire_query(self) -> str:
        where_clause = " AND ".join(
            f"{k} = ?" for k in self._primary_keys
        )
        return (
            f"UPDATE {self._target_table} SET "
            f"{self._expiry_date_column} = ?, "
            f"{self._current_flag_column} = 0 "
            f"WHERE {where_clause} AND {self._current_flag_column} = 1"
        )

    async def process(
        self, rows: Iterable[Iterable[Any]], **_: Any
    ) -> dict[str, int]:
        materialised = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "expired": 0}
        existing_rows = await self._target_pool.fetch_all(self.select_query)
        max_surrogate_rows = await self._target_pool.fetch_all(
            self.max_surrogate_query
        )
        next_surrogate = (
            int(max_surrogate_rows[0][0]) + 1
            if max_surrogate_rows
            else 1
        )
        key_indices = tuple(
            self._column_names.index(k) for k in self._primary_keys
        )
        non_key_indices = tuple(
            self._column_names.index(c) for c in self._non_key_columns
        )
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in existing_rows:
            key = tuple(row[i] for i in key_indices)
            existing_by_key[key] = tuple(row)
        now = datetime.now(timezone.utc).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        for row in materialised:
            if len(row) != len(self._column_names):
                raise ValueError(
                    f"ScdType7MergeKnot: row width {len(row)} does not match "
                    f"column_names width {len(self._column_names)}"
                )
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(
                    (next_surrogate,) + tuple(row) + (now, None, 1)
                )
                next_surrogate += 1
                continue
            existing = existing_by_key[key]
            existing_non_keys = tuple(existing[i] for i in non_key_indices)
            new_non_keys = tuple(row[i] for i in non_key_indices)
            if existing_non_keys == new_non_keys:
                continue
            expires.append((now,) + key)
            inserts.append(
                (next_surrogate,) + tuple(row) + (now, None, 1)
            )
            next_surrogate += 1
        if expires:
            await self._target_pool.execute_many(
                self.expire_query, expires
            )
        if inserts:
            await self._target_pool.execute_many(
                self.insert_query, inserts
            )
        return {"inserted": len(inserts), "expired": len(expires)}
