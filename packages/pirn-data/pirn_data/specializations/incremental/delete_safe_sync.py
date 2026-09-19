"""``DeleteSafeSync`` — full sync with soft-delete; never hard-deletes.

Synchronises a target table to match a source table's keyset. Rows present in the
source are upserted; rows in the target absent from the source are soft-deleted by
setting ``deleted_flag_column = 1`` and stamping ``deleted_at_column``. Hard
deletes are never issued, so a row removed from the source becomes logically
invisible rather than lost.

**A key that comes back is revived.** Every insert and every update clears the
delete markers (``deleted_flag_column = 0``, ``deleted_at_column = NULL``).
Without that, a key that was soft-deleted on one run and reappeared in the source
on the next had its non-key values updated while ``is_deleted`` stayed ``1`` — the
row was silently still invisible to every consumer filtering on the flag, and no
amount of re-syncing brought it back.

**A key already soft-deleted is not re-stamped.** The soft-delete pass touches only
rows whose flag is still clear, so ``deleted_at`` keeps the instant the row
actually disappeared instead of being pushed forward to the latest run.

**The whole sync is one transaction.** Upserts and soft-deletes run inside
``target_pool.transaction()``, so a failure part-way cannot leave the target with
some keys synced and others still carrying the previous run's state. The
statements are set-based: three ``execute_many`` calls rather than a SELECT plus
an UPDATE or INSERT per source row.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows; index them by key tuple.
    3. Fetch every target key with its current delete flag, in one query.
    4. Classify: a source key absent from the target is an INSERT, a source key
       present is an UPDATE (which also clears the delete markers), a target key
       absent from the source whose flag is clear is a SOFT DELETE.
    5. Inside one transaction on ``target_pool``, issue one ``execute_many`` per
       class of change.
    6. Return a summary dict with ``rows_inserted``, ``rows_updated`` and
       ``rows_soft_deleted``.

References:
    [1] pirn — DatabaseConnectionPool.transaction (atomic unit of work):
        pirn/connectors/database_connection_pool.py
    [2] pirn_data/pool_validator.py — the shared argument checks.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.pool_validator import PoolValidator


class DeleteSafeSync(Knot):
    """Full table sync: upsert new/changed rows, soft-delete removed rows, revive returns."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        non_key_columns: Knot | tuple[str, ...],
        deleted_flag_column: Knot | str = "is_deleted",
        deleted_at_column: Knot | str = "deleted_at",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            key_columns=key_columns,
            non_key_columns=non_key_columns,
            deleted_flag_column=deleted_flag_column,
            deleted_at_column=deleted_at_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _update_query(
        target_table: str,
        key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
        deleted_flag_column: str,
        deleted_at_column: str,
    ) -> str:
        """Update a present key's values and clear its delete markers."""
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"UPDATE {target_table} SET {set_clause}, "
            f"{deleted_flag_column} = 0, {deleted_at_column} = NULL "
            f"WHERE {where}"
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        all_columns: tuple[str, ...],
        deleted_flag_column: str,
        deleted_at_column: str,
    ) -> str:
        """Insert a new key with its delete markers explicitly clear."""
        columns = ", ".join([*all_columns, deleted_flag_column, deleted_at_column])
        placeholders = ", ".join(["?"] * len(all_columns))
        return f"INSERT INTO {target_table} ({columns}) VALUES ({placeholders}, 0, NULL)"

    @staticmethod
    def _fetch_target_keys_query(
        target_table: str, key_columns: tuple[str, ...], deleted_flag_column: str
    ) -> str:
        """Read every target key with its current delete flag as the trailing column."""
        key_cols = ", ".join([*key_columns, deleted_flag_column])
        return f"SELECT {key_cols} FROM {target_table}"

    @staticmethod
    def _soft_delete_query(
        target_table: str,
        key_columns: tuple[str, ...],
        deleted_flag_column: str,
        deleted_at_column: str,
    ) -> str:
        """Soft-delete a key, stamping the instant it disappeared."""
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"UPDATE {target_table} "
            f"SET {deleted_flag_column} = 1, {deleted_at_column} = ? "
            f"WHERE {where}"
        )

    @staticmethod
    def _classify(
        source_rows: Sequence[Sequence[Any]],
        target_key_rows: Sequence[Sequence[Any]],
        key_tuple: tuple[str, ...],
        non_key_tuple: tuple[str, ...],
        now_iso: str,
    ) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        """Split the sync into insert, update and soft-delete bind tuples.

        ``target_key_rows`` carries each target key followed by its current delete
        flag, so a key already soft-deleted can be left alone rather than
        re-stamped.

        Returns:
            ``(inserts, updates, soft_deletes)``, each a list of bind tuples in the
            order its statement expects.
        """
        all_columns = key_tuple + non_key_tuple
        key_width = len(key_tuple)
        target_flags: dict[tuple[Any, ...], Any] = {
            tuple(row)[:key_width]: tuple(row)[key_width] for row in target_key_rows
        }
        inserts: list[tuple[Any, ...]] = []
        updates: list[tuple[Any, ...]] = []
        source_keys: set[tuple[Any, ...]] = set()
        for row in source_rows:
            row_dict = dict(zip(all_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            non_key_values = tuple(row_dict[k] for k in non_key_tuple)
            source_keys.add(key_values)
            if key_values in target_flags:
                updates.append(non_key_values + key_values)
            else:
                inserts.append(key_values + non_key_values)
        soft_deletes = [
            (now_iso, *key_values)
            for key_values, flag in target_flags.items()
            if key_values not in source_keys and not flag
        ]
        return inserts, updates, soft_deletes

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        non_key_columns: Any,
        deleted_flag_column: Any = "is_deleted",
        deleted_at_column: Any = "deleted_at",
        **_: Any,
    ) -> dict[str, Any]:
        PoolValidator.validate_pools(
            "DeleteSafeSync",
            source_pool=source_pool,
            target_pool=target_pool,
        )
        PoolValidator.validate_non_empty_string("DeleteSafeSync", "source_query", source_query)
        PoolValidator.validate_non_empty_string("DeleteSafeSync", "target_table", target_table)
        PoolValidator.validate_identifier("target_table", target_table)
        PoolValidator.validate_identifier("deleted_flag_column", deleted_flag_column)
        PoolValidator.validate_identifier("deleted_at_column", deleted_at_column)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        PoolValidator.validate_identifier("key_columns", key_tuple)
        PoolValidator.validate_identifier("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"DeleteSafeSync: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        marker_overlap = {deleted_flag_column, deleted_at_column} & set(key_tuple + non_key_tuple)
        if marker_overlap:
            raise ValueError(
                "DeleteSafeSync: the delete markers must not appear in key_columns or "
                f"non_key_columns: {sorted(marker_overlap)!r}"
            )
        all_columns = key_tuple + non_key_tuple
        now_iso = datetime.now(UTC).isoformat()
        source_rows = await source_pool.fetch_all(source_query)
        target_key_rows = await target_pool.fetch_all(
            DeleteSafeSync._fetch_target_keys_query(target_table, key_tuple, deleted_flag_column)
        )
        inserts, updates, soft_deletes = DeleteSafeSync._classify(
            source_rows, target_key_rows, key_tuple, non_key_tuple, now_iso
        )
        insert_q = DeleteSafeSync._insert_query(
            target_table, all_columns, deleted_flag_column, deleted_at_column
        )
        update_q = DeleteSafeSync._update_query(
            target_table, key_tuple, non_key_tuple, deleted_flag_column, deleted_at_column
        )
        soft_delete_q = DeleteSafeSync._soft_delete_query(
            target_table, key_tuple, deleted_flag_column, deleted_at_column
        )
        async with target_pool.transaction() as transaction:
            if inserts:
                await transaction.execute_many(insert_q, inserts)
            if updates:
                await transaction.execute_many(update_q, updates)
            if soft_deletes:
                await transaction.execute_many(soft_delete_q, soft_deletes)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": len(inserts),
            "rows_updated": len(updates),
            "rows_soft_deleted": len(soft_deletes),
        }
