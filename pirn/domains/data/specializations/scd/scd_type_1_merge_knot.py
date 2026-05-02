"""``ScdType1MergeKnot`` — overwrite-on-change merge for SCD Type 1.

Reads source rows and existing target rows in one knot, classifies each
source row as INSERT (key absent in target) or UPDATE (key present in
target with at least one changed value), and issues the corresponding
parameterised statements through the target pool.

Type 1 SCD (Kimball-style "overwrite") preserves no history: an updated
attribute simply replaces the previous value. For history-preserving
behaviour use :class:`ScdType2Merge` (Type 2) or
:class:`ScdType7Merge` (Type 7).
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType1MergeKnot(Knot):
    """Merge a source row stream into a target table by overwriting on change."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_keys: Sequence[str],
        column_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType1MergeKnot: target_pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(
                f"ScdType1MergeKnot: primary_keys not in column_names: {missing}"
            )
        self._target_pool = target_pool
        self._target_table = target_table
        self._primary_keys = primary_key_tuple
        self._column_names = column_tuple
        self._non_key_columns = tuple(
            c for c in column_tuple if c not in primary_key_tuple
        )
        super().__init__(rows=rows, _config=_config, **kwargs)

    @property
    def select_query(self) -> str:
        column_list = ", ".join(self._column_names)
        return f"SELECT {column_list} FROM {self._target_table}"

    @property
    def insert_query(self) -> str:
        column_list = ", ".join(self._column_names)
        placeholders = ", ".join(["?"] * len(self._column_names))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    @property
    def update_query(self) -> str:
        # Type 1 always rewrites every non-key column on a match —
        # callers who want partial updates should pre-project rows.
        set_clause = ", ".join(f"{c} = ?" for c in self._non_key_columns)
        where_clause = " AND ".join(f"{k} = ?" for k in self._primary_keys)
        return (
            f"UPDATE {self._target_table} SET {set_clause} "
            f"WHERE {where_clause}"
        )

    async def process(
        self, rows: Iterable[Iterable[Any]], **_: Any
    ) -> dict[str, int]:
        materialised = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "updated": 0}
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
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        for row in materialised:
            if len(row) != len(self._column_names):
                raise ValueError(
                    f"ScdType1MergeKnot: row width {len(row)} does not match "
                    f"column_names width {len(self._column_names)}"
                )
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append(row)
                continue
            existing = existing_by_key[key]
            existing_non_keys = tuple(existing[i] for i in non_key_indices)
            new_non_keys = tuple(row[i] for i in non_key_indices)
            if existing_non_keys == new_non_keys:
                continue
            updates.append(new_non_keys + key)
        if inserts:
            await self._target_pool.execute_many(self.insert_query, inserts)
        if updates and self._non_key_columns:
            await self._target_pool.execute_many(self.update_query, updates)
        return {"inserted": len(inserts), "updated": len(updates)}
