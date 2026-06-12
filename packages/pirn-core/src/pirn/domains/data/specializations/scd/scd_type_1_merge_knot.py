"""``ScdType1MergeKnot`` — overwrite-on-change merge for SCD Type 1.

Reads source rows and existing target rows in one knot, classifies each
source row as INSERT (key absent in target) or UPDATE (key present in
target with at least one changed value), and issues the corresponding
parameterised statements through the target pool.

Type 1 SCD (Kimball-style "overwrite") preserves no history: an updated
attribute simply replaces the previous value. For history-preserving
behaviour use :class:`ScdType2MergeKnot` (Type 2) or
:class:`ScdType7MergeKnot` (Type 7).

Algorithm:
    1. Receive resolved ``rows``, ``target_pool``, ``target_table``,
       ``primary_keys``, and ``column_names`` in ``process()``.
    2. Validate pool type, identifier safety, and pk ⊆ column_names.
    3. Fetch all current rows from the target table.
    4. Index existing rows by their primary key tuple.
    5. Classify each source row as INSERT (key absent) or UPDATE (key
       present with any non-key column changed). Skip unchanged rows.
    6. Bulk-execute inserts via ``execute_many``, then bulk-execute
       updates via ``execute_many``.
    7. Return a dict with ``inserted`` and ``updated`` counts.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType1MergeKnot(Knot):
    """Merge a source row stream into a target table by overwriting on change."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_query(target_table: str, column_names: tuple[str, ...]) -> str:
        column_list = ", ".join(column_names)
        return f"SELECT {column_list} FROM {target_table}"

    @staticmethod
    def _insert_query(target_table: str, column_names: tuple[str, ...]) -> str:
        column_list = ", ".join(column_names)
        placeholders = ", ".join(["?"] * len(column_names))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _update_query(
        target_table: str,
        primary_keys: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where_clause}"

    async def process(
        self,
        *,
        rows: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        **_: Any,
    ) -> dict[str, int]:
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType1MergeKnot: target_pool must be a DatabaseConnectionPool")
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType1MergeKnot: primary_keys not in column_names: {missing}")
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        materialised: list[tuple[Any, ...]] = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "updated": 0}
        select_q = ScdType1MergeKnot._select_query(target_table, column_tuple)
        insert_q = ScdType1MergeKnot._insert_query(target_table, column_tuple)
        update_q = ScdType1MergeKnot._update_query(target_table, primary_key_tuple, non_key_columns)
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        for row in existing_rows:
            key = tuple(row[i] for i in key_indices)
            existing_by_key[key] = tuple(row)
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        for row in materialised:
            if len(row) != len(column_tuple):
                raise ValueError(
                    f"ScdType1MergeKnot: row width {len(row)} does not match "
                    f"column_names width {len(column_tuple)}"
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
            await target_pool.execute_many(insert_q, inserts)
        if updates and non_key_columns:
            await target_pool.execute_many(update_q, updates)
        return {"inserted": len(inserts), "updated": len(updates)}
