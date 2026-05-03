"""``DataVaultLinkLoader`` — insert-only loader for Data Vault Link entities.

A Link records **relationships** between two or more Hub entities.  Each
row carries:

* a composite hash key (hash of all participating hub hash keys concatenated
  in a canonical order),
* one hash key column per participating Hub,
* ``load_date`` — the UTC ISO-8601 timestamp of the batch that first saw
  this combination,
* ``record_source`` — the system-of-record label for that batch.

Behaviour
---------
For each row produced by ``source_query``:

* If a row with the same ``link_hash_key_column`` already exists in
  ``target_table`` → **skip** (insert-only; no updates ever).
* Otherwise → ``INSERT`` the new link row.

Re-running with the same set of relationships is always a no-op.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DataVaultLinkLoader(SubTapestry):
    """Insert-only loader that adds new relationship rows to a Data Vault Link."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        link_hash_key_column: str,
        hub_hash_key_columns: Sequence[str],
        load_date_column: str = "load_date",
        record_source_column: str = "record_source",
        record_source: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._link_hash_key_column = link_hash_key_column
        self._hub_hash_key_columns = hub_hk_tuple
        self._load_date_column = load_date_column
        self._record_source_column = record_source_column
        self._record_source = record_source
        self._source_columns = (link_hash_key_column,) + hub_hk_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def _exists_query(self) -> str:
        return (
            f"SELECT 1 FROM {self._target_table} "
            f"WHERE {self._link_hash_key_column} = ?"
        )

    @property
    def _insert_query(self) -> str:
        all_cols = list(self._source_columns) + [
            self._load_date_column,
            self._record_source_column,
        ]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Insert new relationship rows into the Link, skipping any that already exist.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and ``rows_inserted``
            summarising the load outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        load_date = datetime.now(timezone.utc).isoformat()
        rows_inserted = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            link_hk = row_dict[self._link_hash_key_column]
            existing = await self._target_pool.fetch_all(
                self._exists_query, (link_hk,)
            )
            if existing:
                continue
            values = tuple(row_dict[c] for c in self._source_columns)
            await self._target_pool.execute(
                self._insert_query,
                values + (load_date, self._record_source),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
        }
