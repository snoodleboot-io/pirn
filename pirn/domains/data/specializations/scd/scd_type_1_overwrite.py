"""``ScdType1Overwrite`` — Slowly Changing Dimension Type 1 (overwrite).

SCD Type 1 keeps **only the current value** for every dimension row: when
a tracked attribute changes, the existing target row is updated in place
and history is lost. It is the right choice when the warehouse only
needs the latest snapshot (e.g. correcting a typo in a name) and storage
of historical states is not a regulatory or analytic requirement.

Behaviour
---------
For each row produced by ``source_query``:

* If a row with the same ``key_columns`` already exists in
  ``target_table``, ``UPDATE`` the ``non_key_columns`` to the new values.
* Otherwise ``INSERT`` a new row carrying both key and non-key columns.

The knot returns a primitive summary so pirn's content-addressing hash
does not have to walk a :class:`RunResult` whose outputs may contain a
:class:`DataBatch` with a type-bearing schema.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ScdType1Overwrite(SubTapestry):
    """Upsert dimension rows in place, preserving no history (SCD Type 1)."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        non_key_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType1Overwrite: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType1Overwrite: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType1Overwrite: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        non_key_tuple = tuple(non_key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("non_key_columns", non_key_tuple)
        overlap = set(key_tuple) & set(non_key_tuple)
        if overlap:
            raise ValueError(
                f"ScdType1Overwrite: key_columns and non_key_columns overlap "
                f"on {sorted(overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._non_key_columns = non_key_tuple
        self._all_columns = key_tuple + non_key_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def select_existing_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"SELECT 1 FROM {self._target_table} WHERE {where}"

    @property
    def update_query(self) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in self._non_key_columns)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"

    @property
    def insert_query(self) -> str:
        columns = ", ".join(self._all_columns)
        placeholders = ", ".join(["?"] * len(self._all_columns))
        return (
            f"INSERT INTO {self._target_table} ({columns}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Upsert each source row into the target by overwriting changed attributes in place.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and ``rows_upserted``
            summarising the merge outcome.
        """
        # Read all source rows up-front; SCD Type 1 is intended for
        # dimension tables that fit comfortably in memory.
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_upserted = 0
        for row in source_rows:
            row_dict = dict(zip(self._all_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            non_key_values = tuple(row_dict[k] for k in self._non_key_columns)
            existing = await self._target_pool.fetch_all(
                self.select_existing_query, key_values
            )
            if existing:
                await self._target_pool.execute(
                    self.update_query, non_key_values + key_values
                )
            else:
                await self._target_pool.execute(
                    self.insert_query, key_values + non_key_values
                )
            rows_upserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_upserted": rows_upserted,
        }
