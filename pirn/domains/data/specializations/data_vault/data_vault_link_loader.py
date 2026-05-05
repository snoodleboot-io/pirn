"""``DataVaultLinkLoader`` — insert-only loader for Data Vault Link entities.

A Link records **relationships** between two or more Hub entities.  Each
row carries:

* a composite hash key (hash of all participating hub hash keys concatenated
  in a canonical order),
* one hash key column per participating Hub,
* ``load_date`` — the UTC ISO-8601 timestamp of the batch that first saw
  this combination,
* ``record_source`` — the system-of-record label for that batch.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``link_hash_key_column``, ``hub_hash_key_columns``,
       ``load_date_column``, ``record_source_column``, and ``record_source``
       in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and column disjointness against the envelope columns.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, check whether the link hash key already exists in the target.
    5. If present, skip (insert-only; no updates ever).
    6. Otherwise, INSERT the new link row with current UTC ``load_date`` and
       the supplied ``record_source``.
    7. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_inserted``.

References:
    [1] Linstedt & Olschimke — *Building a Scalable Data Warehouse with Data Vault 2.0*
        (2015), Chapter 6: Link tables.
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class DataVaultLinkLoader(Knot):
    """Insert-only loader that adds new relationship rows to a Data Vault Link."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        link_hash_key_column: Knot | str,
        hub_hash_key_columns: Knot | tuple[str, ...],
        load_date_column: Knot | str,
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
            link_hash_key_column=link_hash_key_column,
            hub_hash_key_columns=hub_hash_key_columns,
            load_date_column=load_date_column,
            record_source_column=record_source_column,
            record_source=record_source,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _exists_query(target_table: str, link_hash_key_column: str) -> str:
        return f"SELECT 1 FROM {target_table} WHERE {link_hash_key_column} = ?"

    @staticmethod
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        load_date_column: str,
        record_source_column: str,
    ) -> str:
        all_cols = [*source_columns, load_date_column, record_source_column]
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
        link_hash_key_column: Any,
        hub_hash_key_columns: Any,
        load_date_column: Any,
        record_source_column: Any,
        record_source: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultLinkLoader: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultLinkLoader: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
            ("record_source", record_source),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DataVaultLinkLoader: {label} must be a non-empty string"
                )
        for label, value in (
            ("link_hash_key_column", link_hash_key_column),
            ("load_date_column", load_date_column),
            ("record_source_column", record_source_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DataVaultLinkLoader: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("link_hash_key_column", link_hash_key_column)
        IdentifierValidator.validate_column("load_date_column", load_date_column)
        IdentifierValidator.validate_column("record_source_column", record_source_column)
        hub_hk_tuple = tuple(hub_hash_key_columns)
        IdentifierValidator.validate_columns("hub_hash_key_columns", hub_hk_tuple)
        envelope = {load_date_column, record_source_column, link_hash_key_column}
        clash = set(hub_hk_tuple) & envelope
        if clash:
            raise ValueError(
                f"DataVaultLinkLoader: hub_hash_key_columns clash with envelope "
                f"columns: {sorted(clash)!r}"
            )
        source_columns = (link_hash_key_column, *hub_hk_tuple)
        source_rows = await source_pool.fetch_all(source_query)
        load_date = datetime.now(UTC).isoformat()
        rows_inserted = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            link_hk = row_dict[link_hash_key_column]
            existing = await target_pool.fetch_all(
                DataVaultLinkLoader._exists_query(target_table, link_hash_key_column),
                (link_hk,),
            )
            if existing:
                continue
            values = tuple(row_dict[c] for c in source_columns)
            await target_pool.execute(
                DataVaultLinkLoader._insert_query(
                    target_table, source_columns, load_date_column, record_source_column
                ),
                (*values, load_date, record_source),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
        }
