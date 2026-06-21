"""``DataVaultSatelliteLoader`` — attribute-change loader for Data Vault Satellites.

A Satellite stores **descriptor attributes** for a Hub or Link.  Each
version of those attributes is a separate row, giving a complete audit
trail.  The current version has a NULL ``load_end_date``; closed versions
carry the ISO-8601 timestamp of the batch that superseded them.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``hub_hash_key_column``, ``attribute_columns``,
       ``hash_diff_column``, ``load_date_column``, ``load_end_date_column``,
       ``record_source_column``, and ``record_source`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and column disjointness against the envelope columns.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, look up the open row (``load_end_date IS NULL``) for that
       hub hash key.
    5. If no open row exists, INSERT a new satellite row with ``load_date = now``
       and ``load_end_date = NULL``.
    6. If an open row exists with a different ``hash_diff``, close the old row
       (``load_end_date = now``) then INSERT a new row.
    7. If the open row's ``hash_diff`` matches, skip (no change).
    8. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_inserted``, and ``rows_closed``.

References:
    [1] Linstedt & Olschimke — *Building a Scalable Data Warehouse with Data Vault 2.0*
        (2015), Chapter 5: Satellite tables.
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class DataVaultSatelliteLoader(Knot):
    """Insert-only (with close-out) loader for Data Vault Satellite tables."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        hub_hash_key_column: Knot | str,
        attribute_columns: Knot | tuple[str, ...],
        hash_diff_column: Knot | str,
        load_date_column: Knot | str,
        load_end_date_column: Knot | str,
        record_source_column: Knot | str,
        record_source: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            hub_hash_key_column=hub_hash_key_column,
            attribute_columns=attribute_columns,
            hash_diff_column=hash_diff_column,
            load_date_column=load_date_column,
            load_end_date_column=load_end_date_column,
            record_source_column=record_source_column,
            record_source=record_source,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_open_query(
        target_table: str,
        hub_hash_key_column: str,
        hash_diff_column: str,
        load_end_date_column: str,
    ) -> str:
        return (
            f"SELECT {hash_diff_column} FROM {target_table} "
            f"WHERE {hub_hash_key_column} = ? "
            f"AND {load_end_date_column} IS NULL"
        )

    @staticmethod
    def _close_query(
        target_table: str,
        hub_hash_key_column: str,
        load_end_date_column: str,
    ) -> str:
        return (
            f"UPDATE {target_table} "
            f"SET {load_end_date_column} = ? "
            f"WHERE {hub_hash_key_column} = ? "
            f"AND {load_end_date_column} IS NULL"
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        load_date_column: str,
        load_end_date_column: str,
        record_source_column: str,
    ) -> str:
        all_cols = [*source_columns, load_date_column, load_end_date_column, record_source_column]
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
        hub_hash_key_column: Any,
        attribute_columns: Any,
        hash_diff_column: Any,
        load_date_column: Any,
        load_end_date_column: Any,
        record_source_column: Any,
        record_source: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultSatelliteLoader: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultSatelliteLoader: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
            ("record_source", record_source),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"DataVaultSatelliteLoader: {label} must be a non-empty string")
        for label, value in (
            ("hub_hash_key_column", hub_hash_key_column),
            ("hash_diff_column", hash_diff_column),
            ("load_date_column", load_date_column),
            ("load_end_date_column", load_end_date_column),
            ("record_source_column", record_source_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"DataVaultSatelliteLoader: {label} must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("hub_hash_key_column", hub_hash_key_column)
        IdentifierValidator.validate_column("hash_diff_column", hash_diff_column)
        IdentifierValidator.validate_column("load_date_column", load_date_column)
        IdentifierValidator.validate_column("load_end_date_column", load_end_date_column)
        IdentifierValidator.validate_column("record_source_column", record_source_column)
        attr_tuple = tuple(attribute_columns)
        IdentifierValidator.validate_columns("attribute_columns", attr_tuple)
        envelope = {
            hub_hash_key_column,
            hash_diff_column,
            load_date_column,
            load_end_date_column,
            record_source_column,
        }
        clash = set(attr_tuple) & envelope
        if clash:
            raise ValueError(
                f"DataVaultSatelliteLoader: attribute_columns clash with envelope "
                f"columns: {sorted(clash)!r}"
            )
        source_columns = cast(tuple[str, ...], (hub_hash_key_column, hash_diff_column, *attr_tuple))
        source_rows = await source_pool.fetch_all(source_query)
        load_date = datetime.now(UTC).isoformat()
        rows_inserted = 0
        rows_closed = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            hub_hk = row_dict[hub_hash_key_column]
            incoming_diff = row_dict[hash_diff_column]
            open_rows = await target_pool.fetch_all(
                DataVaultSatelliteLoader._select_open_query(
                    target_table,
                    hub_hash_key_column,
                    hash_diff_column,
                    load_end_date_column,
                ),
                (hub_hk,),
            )
            if open_rows:
                existing_diff = open_rows[0][0]
                if existing_diff == incoming_diff:
                    continue
                await target_pool.execute(
                    DataVaultSatelliteLoader._close_query(
                        target_table, hub_hash_key_column, load_end_date_column
                    ),
                    (load_date, hub_hk),
                )
                rows_closed += 1
            values = tuple(row_dict[c] for c in source_columns)
            await target_pool.execute(
                DataVaultSatelliteLoader._insert_query(
                    target_table,
                    source_columns,
                    load_date_column,
                    load_end_date_column,
                    record_source_column,
                ),
                (*values, load_date, None, record_source),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
