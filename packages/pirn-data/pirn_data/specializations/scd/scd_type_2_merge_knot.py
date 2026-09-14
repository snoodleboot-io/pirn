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

Algorithm:
    1. Receive resolved ``rows``, ``target_pool``, ``target_table``,
       ``primary_keys``, ``column_names``, and date/flag column names in
       ``process()``.
    2. Validate pool type, identifiers, pk ⊆ column_names, and no SCD
       columns in column_names.
    3. Fetch all current rows (``is_current = 1``) from the target.
    4. Index existing rows by their primary key tuple.
    5. Classify each source row: INSERT (new key) or EXPIRE+INSERT
       (changed non-key values). Skip unchanged rows.
    6. Bulk-execute expires, then bulk-execute inserts.
    7. Return a dict with ``inserted`` and ``expired`` counts.

References:
    [1] Kimball Group — SCD Type 2 (add row):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_2_queries import ScdType2Queries


class ScdType2MergeKnot(PoolMergeKnot):
    """Merge a source row stream into a Type 2 effective-dated target."""

    def __init__(
        self,
        *,
        rows: Knot,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        effective_date_column: Knot | str,
        expiry_date_column: Knot | str,
        current_flag_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            effective_date_column=effective_date_column,
            expiry_date_column=expiry_date_column,
            current_flag_column=current_flag_column,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        effective_date_column: Any,
        expiry_date_column: Any,
        current_flag_column: Any,
        **_: Any,
    ) -> dict[str, int]:
        self._validate_pools("ScdType2MergeKnot", target_pool=target_pool)
        self._validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        self._validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        self._validate_identifier("column_names", column_tuple)
        self._validate_identifier("effective_date_column", effective_date_column)
        self._validate_identifier("expiry_date_column", expiry_date_column)
        self._validate_identifier("current_flag_column", current_flag_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType2MergeKnot: primary_keys not in column_names: {missing}")
        scd_columns = (effective_date_column, expiry_date_column, current_flag_column)
        overlap = [c for c in scd_columns if c in column_tuple]
        if overlap:
            raise ValueError(
                "ScdType2MergeKnot: effective/expiry/current columns must "
                f"not appear in column_names: {overlap}"
            )
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        materialised: list[tuple[Any, ...]] = [tuple(r) for r in rows]
        if not materialised:
            return {"inserted": 0, "expired": 0}
        select_q = ScdType2Queries.select_query(target_table, column_tuple, current_flag_column)
        insert_q = ScdType2Queries.insert_query(
            target_table,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        )
        expire_q = ScdType2Queries.expire_query(
            target_table, primary_key_tuple, expiry_date_column, current_flag_column
        )
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key = ScdType2MergeKnot._index_rows_by_key(existing_rows, key_indices)
        now = datetime.now(UTC).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        for row in materialised:
            self._validate_row_width("ScdType2MergeKnot", row, column_tuple)
            key = tuple(row[i] for i in key_indices)
            if key not in existing_by_key:
                inserts.append((*tuple(row), now, None, 1))
                continue
            existing = existing_by_key[key]
            if not ScdType2MergeKnot._non_key_values_changed(existing, row, non_key_indices):
                continue
            expires.append((now, *key))
            inserts.append((*tuple(row), now, None, 1))
        if expires:
            await target_pool.execute_many(expire_q, expires)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        return {"inserted": len(inserts), "expired": len(expires)}
