"""``DataVaultSatelliteLoader`` — attribute-change loader for Data Vault Satellites.

A Satellite stores **descriptor attributes** for a Hub or Link.  Each
version of those attributes is a separate row, giving a complete audit
trail.  The current version has a NULL ``load_end_date``; closed versions
carry the ISO-8601 timestamp of the batch that superseded them.

Behaviour
---------
For each row produced by ``source_query``:

* Compute the incoming ``hash_diff`` (caller-supplied as a column in the
  source; typically MD5 or SHA-1 of all attribute values concatenated).
* Look up the **open** row (``load_end_date IS NULL``) for that
  ``hub_hash_key_column`` value.
* If no open row exists → ``INSERT`` a new satellite row with
  ``load_date = now``, ``load_end_date = NULL``.
* If an open row exists with a **different** ``hash_diff`` → close the
  old row (``load_end_date = now``) then ``INSERT`` a new row.
* If the open row's ``hash_diff`` matches → **skip** (no change).

Re-running with identical attribute payloads is always a no-op.
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


class DataVaultSatelliteLoader(SubTapestry):
    """Insert-only (with close-out) loader for Data Vault Satellite tables."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        hub_hash_key_column: str,
        attribute_columns: Sequence[str],
        hash_diff_column: str = "hash_diff",
        load_date_column: str = "load_date",
        load_end_date_column: str = "load_end_date",
        record_source_column: str = "record_source",
        record_source: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
                raise ValueError(
                    f"DataVaultSatelliteLoader: {label} must be a non-empty string"
                )
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
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._hub_hash_key_column = hub_hash_key_column
        self._attribute_columns = attr_tuple
        self._hash_diff_column = hash_diff_column
        self._load_date_column = load_date_column
        self._load_end_date_column = load_end_date_column
        self._record_source_column = record_source_column
        self._record_source = record_source
        self._source_columns = (hub_hash_key_column, hash_diff_column) + attr_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def _select_open_query(self) -> str:
        return (
            f"SELECT {self._hash_diff_column} FROM {self._target_table} "
            f"WHERE {self._hub_hash_key_column} = ? "
            f"AND {self._load_end_date_column} IS NULL"
        )

    @property
    def _close_query(self) -> str:
        return (
            f"UPDATE {self._target_table} "
            f"SET {self._load_end_date_column} = ? "
            f"WHERE {self._hub_hash_key_column} = ? "
            f"AND {self._load_end_date_column} IS NULL"
        )

    @property
    def _insert_query(self) -> str:
        all_cols = list(self._source_columns) + [
            self._load_date_column,
            self._load_end_date_column,
            self._record_source_column,
        ]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({col_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Load changed satellite attributes, closing old rows and inserting new ones.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``,
            and ``rows_closed`` summarising the load outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        load_date = datetime.now(timezone.utc).isoformat()
        rows_inserted = 0
        rows_closed = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            hub_hk = row_dict[self._hub_hash_key_column]
            incoming_diff = row_dict[self._hash_diff_column]
            open_rows = await self._target_pool.fetch_all(
                self._select_open_query, (hub_hk,)
            )
            if open_rows:
                existing_diff = open_rows[0][0]
                if existing_diff == incoming_diff:
                    continue
                await self._target_pool.execute(
                    self._close_query, (load_date, hub_hk)
                )
                rows_closed += 1
            values = tuple(row_dict[c] for c in self._source_columns)
            await self._target_pool.execute(
                self._insert_query,
                values + (load_date, None, self._record_source),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
