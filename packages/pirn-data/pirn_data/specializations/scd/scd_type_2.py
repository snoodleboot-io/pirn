"""``ScdType2`` — Kimball Type 2 Slowly Changing Dimension (effective-dated history).

Type 2 preserves the full history of every tracked attribute by keeping one row
per distinct version of each natural key. On a change the current row is stamped
``valid_to = now`` / ``is_current = 0`` and a new row is inserted with
``valid_from = now``, ``valid_to = NULL``, ``is_current = 1``. A query can then
reconstruct what an attribute looked like at any instant. The trade-off against
:class:`~pirn_data.specializations.scd.scd_type_1.ScdType1` is storage and a
denormalised lookup; for a surrogate key over the same history see
:class:`~pirn_data.specializations.scd.scd_type_7.ScdType7`.

This is the *only* Type 2 implementation in the package. It previously had three
near-identical siblings: ``ScdType2MergeKnot`` (same statements, rows from an
upstream knot), ``ScdType2History`` (same statements issued one row at a time)
and ``DbtStyleSnapshot`` (same statements, change detected by comparing a stored
row hash rather than the stored values). All three are deleted: ``rows`` is now
an input here, the set-based statements are strictly fewer round trips, and
``row_hash_column`` selects hash-based detection.

Source rows arrive one of two ways, and exactly one must be given:

* ``rows`` — positional rows from an upstream knot, one value per
  ``column_names`` entry;
* ``source_pool`` + ``source_query`` — a query this knot runs itself.

Change detection has two modes:

* **value comparison** (default) — the stored non-key values are compared
  against the candidate row's;
* **row hash** — set ``row_hash_column`` to the name of a column holding a
  content hash of the non-key values (dbt's ``dbt_scd_id`` idiom). The hash is
  written on every insert and compared on every subsequent run. The hash is
  :class:`~pirn.core.content_hasher.ContentHasher`'s SHA-256 over the canonical
  form of the value tuple, not a delimiter-joined ``str()`` of it: joining on a
  separator collides whenever a value contains the separator, so ``("a|b", "c")``
  and ``("a", "b|c")`` hashed identically and a real change went undetected.

Algorithm:
    1. Validate the pools, identifiers, ``primary_keys ⊆ column_names``, and
       that no bookkeeping column appears in ``column_names``.
    2. Materialise the source rows from ``rows`` or ``source_query``.
    3. Fetch every current target row (``is_current = 1``) and index it by
       primary key.
    4. Classify each source row: INSERT when its key is absent, EXPIRE + INSERT
       when it changed, skip when it did not.
    5. Issue one ``execute_many`` for the expiries, then one for the inserts.
    6. Return ``succeeded``, ``target_table``, ``rows_inserted`` and
       ``rows_expired``.

References:
    [1] Kimball Group — SCD Type 2 (add row):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/
    [2] dbt — snapshot strategies (the ``row_hash_column`` mode):
        https://docs.getdbt.com/docs/build/snapshots
    [3] pirn — ContentHasher (collision-free canonical hashing):
        pirn/core/content_hasher.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.pool_validator import PoolValidator
from pirn_data.specializations.pool_merge_knot import PoolMergeKnot
from pirn_data.specializations.scd.scd_type_2_queries import ScdType2Queries


class ScdType2(PoolMergeKnot):
    """Perform a Type 2 SCD merge: expire changed rows, insert new versions."""

    def __init__(
        self,
        *,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        primary_keys: Knot | tuple[str, ...],
        column_names: Knot | tuple[str, ...],
        rows: Knot | Sequence[Sequence[Any]] | None = None,
        source_pool: Knot | DatabaseConnectionPool | None = None,
        source_query: Knot | str | None = None,
        effective_date_column: Knot | str = "valid_from",
        expiry_date_column: Knot | str = "valid_to",
        current_flag_column: Knot | str = "is_current",
        row_hash_column: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            target_pool=target_pool,
            target_table=target_table,
            primary_keys=primary_keys,
            column_names=column_names,
            rows=rows,
            source_pool=source_pool,
            source_query=source_query,
            effective_date_column=effective_date_column,
            expiry_date_column=expiry_date_column,
            current_flag_column=current_flag_column,
            row_hash_column=row_hash_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _row_hash(non_key_values: tuple[Any, ...]) -> str:
        """Content hash of a row's non-key values, for hash-based change detection.

        Delegates to :class:`~pirn.core.content_hasher.ContentHasher`, whose
        canonical serialisation is injective over the value tuple. A
        ``"|".join(str(v) for v in values)`` digest is not: any value containing
        the separator aliases onto a different tuple, so a changed row could
        hash to its predecessor and never be versioned.
        """
        return ContentHasher.hash(non_key_values)

    @staticmethod
    async def _merge(
        source_rows: Sequence[tuple[Any, ...]],
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_key_tuple: tuple[str, ...],
        column_tuple: tuple[str, ...],
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
        row_hash_column: str | None,
    ) -> dict[str, int]:
        """Classify ``source_rows`` against the current target rows and apply them."""
        if not source_rows:
            return {"rows_inserted": 0, "rows_expired": 0}
        select_q = ScdType2Queries.select_query(
            target_table, column_tuple, current_flag_column, row_hash_column
        )
        insert_q = ScdType2Queries.insert_query(
            target_table,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
            row_hash_column,
        )
        expire_q = ScdType2Queries.expire_query(
            target_table, primary_key_tuple, expiry_date_column, current_flag_column
        )
        existing_rows = await target_pool.fetch_all(select_q)
        key_indices = tuple(column_tuple.index(k) for k in primary_key_tuple)
        non_key_columns = tuple(c for c in column_tuple if c not in primary_key_tuple)
        non_key_indices = tuple(column_tuple.index(c) for c in non_key_columns)
        existing_by_key = ScdType2._index_rows_by_key(existing_rows, key_indices)
        now = datetime.now(UTC).isoformat()
        inserts: list[tuple[Any, ...]] = []
        expires: list[tuple[Any, ...]] = []
        for row in source_rows:
            key = tuple(row[i] for i in key_indices)
            row_hash = (
                ScdType2._row_hash(tuple(row[i] for i in non_key_indices))
                if row_hash_column is not None
                else None
            )
            new_row = (
                (*row, now, None, 1) if row_hash_column is None else (*row, now, None, 1, row_hash)
            )
            if key not in existing_by_key:
                inserts.append(new_row)
                continue
            existing = existing_by_key[key]
            if row_hash_column is None:
                changed = ScdType2._non_key_values_changed(existing, row, non_key_indices)
            else:
                # The stored hash is selected as the extra trailing column.
                changed = existing[len(column_tuple)] != row_hash
            if not changed:
                continue
            expires.append((now, *key))
            inserts.append(new_row)
        if expires:
            await target_pool.execute_many(expire_q, expires)
        if inserts:
            await target_pool.execute_many(insert_q, inserts)
        return {"rows_inserted": len(inserts), "rows_expired": len(expires)}

    async def process(
        self,
        *,
        target_pool: Any,
        target_table: Any,
        primary_keys: Any,
        column_names: Any,
        rows: Any = None,
        source_pool: Any = None,
        source_query: Any = None,
        effective_date_column: Any = "valid_from",
        expiry_date_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        row_hash_column: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        PoolValidator.validate_pools("ScdType2", target_pool=target_pool)
        PoolValidator.validate_identifier("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        PoolValidator.validate_identifier("primary_keys", primary_key_tuple)
        column_tuple = tuple(column_names)
        PoolValidator.validate_identifier("column_names", column_tuple)
        PoolValidator.validate_identifier("effective_date_column", effective_date_column)
        PoolValidator.validate_identifier("expiry_date_column", expiry_date_column)
        PoolValidator.validate_identifier("current_flag_column", current_flag_column)
        if row_hash_column is not None:
            PoolValidator.validate_identifier("row_hash_column", row_hash_column)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(f"ScdType2: primary_keys not in column_names: {missing}")
        bookkeeping = [effective_date_column, expiry_date_column, current_flag_column]
        if row_hash_column is not None:
            bookkeeping.append(row_hash_column)
        overlap = [c for c in bookkeeping if c in column_tuple]
        if overlap:
            raise ValueError(
                f"ScdType2: SCD bookkeeping columns must not appear in column_names: {overlap}"
            )
        source_rows = await self._resolve_source_rows(
            "ScdType2", rows, source_pool, source_query, column_tuple
        )
        counts = await ScdType2._merge(
            source_rows,
            target_pool,
            target_table,
            primary_key_tuple,
            column_tuple,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
            row_hash_column,
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            **counts,
        }
