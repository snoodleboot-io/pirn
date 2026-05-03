"""``ScdType2MergeKnot`` — effective-dated row-versioning merge for SCD Type 2.

For every source row whose primary key matches a target row with
``valid_to IS NULL`` and any non-key column changed, this knot:

* Stamps the existing current row with ``valid_to = now()`` and
  ``is_current = false``.
* Inserts a new row carrying the new attribute values plus
  ``valid_from = now()``, ``valid_to = NULL``, ``is_current = true``.

Brand-new primary keys produce a single insert with the same effective-
date defaults.

Type 2 SCD (Kimball-style row-versioning) preserves the full history of
attribute values; queries against the table can reconstruct what an
attribute looked like at any point in time. The trade-off vs Type 1 is
storage and a denormalised lookup.
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


class ScdType2MergeKnot(Knot):
    """Merge a source row stream into a Type 2 effective-dated target."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_keys: Sequence[str],
        column_names: Sequence[str],
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType2MergeKnot: target_pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns(
            "primary_keys", primary_key_tuple
        )
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
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
                f"ScdType2MergeKnot: primary_keys not in column_names: {missing}"
            )
        scd_columns = (
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        overlap = [c for c in scd_columns if c in column_tuple]
        if overlap:
            raise ValueError(
                "ScdType2MergeKnot: effective/expiry/current columns must "
                f"not appear in column_names: {overlap}"
            )
        self._target_pool = target_pool
        self._target_table = target_table
        self._primary_keys = primary_key_tuple
        self._column_names = column_tuple
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
    def insert_query(self) -> str:
        all_cols = list(self._column_names) + [
            self._effective_date_column,
            self._expiry_date_column,
            self._current_flag_column,
        ]
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
        """Merge source rows into the effective-dated Type 2 target by expiring changed rows and inserting new versions.

        Args:
            rows: The upstream source rows; each row is an iterable of positional values.

        Returns:
            A dict with keys ``inserted`` and ``expired`` containing the operation counts.

        Raises:
            ValueError: If any source row's width does not match the configured column_names.
        """
        materialised = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "expired": 0}
        existing_rows = await self._target_pool.fetch_all(self.select_query)
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
                    f"ScdType2MergeKnot: row width {len(row)} does not match "
                    f"column_names width {len(self._column_names)}"
                )
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(tuple(row) + (now, None, 1))
                continue
            existing = existing_by_key[key]
            existing_non_keys = tuple(existing[i] for i in non_key_indices)
            new_non_keys = tuple(row[i] for i in non_key_indices)
            if existing_non_keys == new_non_keys:
                continue
            expires.append((now,) + key)
            inserts.append(tuple(row) + (now, None, 1))
        if expires:
            await self._target_pool.execute_many(
                self.expire_query, expires
            )
        if inserts:
            await self._target_pool.execute_many(
                self.insert_query, inserts
            )
        return {"inserted": len(inserts), "expired": len(expires)}
