"""``ScdType1Overwrite`` — deprecated; construct :class:`MergeUpsert` directly.

SCD Type 1 keeps **only the current value** for every dimension row: when
a tracked attribute changes, the existing target row is updated in place
and history is lost. It is the right choice when the warehouse only
needs the latest snapshot (e.g. correcting a typo in a name) and storage
of historical states is not a regulatory or analytic requirement.

**Deprecated (PIR-870).** This class's per-row select/update/insert logic
is byte-for-byte the same as
:class:`~pirn_data.specializations.incremental.merge_upsert.MergeUpsert`
(same queries, same validation); the two grew independently under
different names for the same SCD-1 / upsert pattern. Construct
``MergeUpsert`` directly in new pipelines — its ``rows_inserted`` /
``rows_updated`` split is a superset of this class's single
``rows_upserted`` count. This name is kept importable for one deprecation
cycle and raises a ``DeprecationWarning`` on construction
(``Knot._deprecated_since``); see `docs/domains/data.md` (SCD / CDC
patterns) for the migration note.

Behaviour
---------
For each row produced by ``source_query``:

* If a row with the same ``key_columns`` already exists in
  ``target_table``, ``UPDATE`` the ``non_key_columns`` to the new values.
* Otherwise ``INSERT`` a new row carrying both key and non-key columns.

The knot returns a primitive summary so pirn's content-addressing hash
does not have to walk a :class:`RunResult` whose outputs may contain a
:class:`DataBatch` with a type-bearing schema.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``key_columns``, and ``non_key_columns`` in
       ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and column disjointness.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, issue a SELECT to check whether the key exists in the
       target table.
    5. If present, UPDATE the non-key columns; otherwise INSERT all columns.
    6. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_upserted``.

References:
    [1] Kimball Group — SCD Type 1 (overwrite):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations._pool_merge_knot import _PoolMergeKnot


class ScdType1Overwrite(_PoolMergeKnot):
    """Deprecated: construct :class:`~pirn_data.specializations.incremental.merge_upsert.MergeUpsert`.

    Upserts dimension rows in place, preserving no history (SCD Type 1) --
    see the module docstring for why this duplicates ``MergeUpsert``.
    """

    _deprecated_since: ClassVar[str | None] = "PIR-870"

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        non_key_columns: Knot | tuple[str, ...],
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
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_existing_query(target_table: str, key_columns: tuple[str, ...]) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"SELECT 1 FROM {target_table} WHERE {where}"

    @staticmethod
    def _update_query(
        target_table: str,
        key_columns: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where}"

    @staticmethod
    def _insert_query(target_table: str, all_columns: tuple[str, ...]) -> str:
        columns = ", ".join(all_columns)
        placeholders = ", ".join(["?"] * len(all_columns))
        return f"INSERT INTO {target_table} ({columns}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        non_key_columns: Any,
        **_: Any,
    ) -> dict[str, Any]:
        self._validate_pools("ScdType1Overwrite", source_pool=source_pool, target_pool=target_pool)
        self._validate_non_empty_string("ScdType1Overwrite", "source_query", source_query)
        self._validate_non_empty_string("ScdType1Overwrite", "target_table", target_table)
        self._validate_identifier("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        self._validate_identifier("key_columns", key_tuple)
        self._validate_identifier("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"ScdType1Overwrite: key_columns and non_key_columns overlap on {sorted(overlap)!r}"
            )
        source_rows = await source_pool.fetch_all(source_query)
        matched = await self._execute_per_row_upsert(
            source_rows,
            target_pool,
            key_tuple,
            non_key_tuple,
            ScdType1Overwrite._select_existing_query(target_table, key_tuple),
            ScdType1Overwrite._update_query(target_table, key_tuple, non_key_tuple),
            ScdType1Overwrite._insert_query(target_table, key_tuple + non_key_tuple),
        )
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_upserted": len(matched),
        }
