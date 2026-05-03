"""``ScdType3PreviousValue`` — Slowly Changing Dimension Type 3 (previous value).

SCD Type 3 stores both the current value **and** the one prior value for
each tracked attribute. When a tracked attribute changes, the old current
value shifts into the ``{col}_previous`` column and the new value is
written into the ``{col}`` column. Only one historical value is kept;
older history is lost.

Behaviour
---------
For each row from ``source_query``:

* If no row with the same ``key_columns`` exists in the target →
  insert the row with the tracked columns populated and every
  ``{col}_previous`` column set to ``NULL``.
* If a row exists with **different** values for any ``tracked_columns`` →
  shift current → previous and write the new current values in place
  (``UPDATE``).
* If a row exists with **identical** tracked values → no change.

The target table must declare ``key_columns``, ``tracked_columns``, and a
``{col}_previous`` companion for every tracked column.  Callers may
override the suffix via ``previous_suffix`` if their naming convention
differs (e.g. ``_prior``).
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ScdType3PreviousValue(SubTapestry):
    """Maintain SCD Type 3 (current + one prior value per tracked column)."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        tracked_columns: Sequence[str],
        previous_suffix: str = "_previous",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType3PreviousValue: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType3PreviousValue: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType3PreviousValue: {label} must be a non-empty string"
                )
        if not isinstance(previous_suffix, str) or not previous_suffix:
            raise ValueError(
                "ScdType3PreviousValue: previous_suffix must be a non-empty string"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType3PreviousValue: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        previous_columns = tuple(f"{c}{previous_suffix}" for c in tracked_tuple)
        for col in previous_columns:
            IdentifierValidator.validate_column("previous column", col)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._tracked_columns = tracked_tuple
        self._previous_columns = previous_columns
        self._source_columns = key_tuple + tracked_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def select_current_query(self) -> str:
        cols = ", ".join(self._tracked_columns)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"SELECT {cols} FROM {self._target_table} WHERE {where}"
        )

    @property
    def insert_query(self) -> str:
        all_cols = (
            list(self._key_columns)
            + list(self._tracked_columns)
            + list(self._previous_columns)
        )
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    @property
    def update_query(self) -> str:
        set_parts = []
        for current_col, previous_col in zip(
            self._tracked_columns, self._previous_columns
        ):
            set_parts.append(f"{previous_col} = {current_col}")
            set_parts.append(f"{current_col} = ?")
        set_clause = ", ".join(set_parts)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"

    async def process(self, **_: Any) -> dict[str, Any]:
        """Shift current tracked values to previous columns and write new current values.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``,
            and ``rows_updated`` summarising the merge outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            tracked_values = tuple(
                row_dict[k] for k in self._tracked_columns
            )
            existing = await self._target_pool.fetch_all(
                self.select_current_query, key_values
            )
            if not existing:
                nulls = (None,) * len(self._previous_columns)
                await self._target_pool.execute(
                    self.insert_query,
                    key_values + tracked_values + nulls,
                )
                rows_inserted += 1
                continue
            current_tracked = tuple(existing[0])
            if current_tracked == tracked_values:
                continue
            # new values interleaved with key_values for the WHERE clause
            await self._target_pool.execute(
                self.update_query,
                tracked_values + key_values,
            )
            rows_updated += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
        }
