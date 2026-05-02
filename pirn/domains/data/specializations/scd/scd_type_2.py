"""``ScdType2`` — Kimball Type 2 Slowly Changing Dimension.

Type 2 ("add row on change") preserves a complete history of attribute
values by closing the current row (``valid_to = now()``,
``is_current = false``) and inserting a new effective-dated row with
the new attribute values. Queries can reconstruct any historical
attribute view by filtering on the effective date range or
``is_current``.

Composition:

1. :class:`DatabaseQuerySource` reads the source rows.
2. :class:`ScdType2MergeKnot` reads the *current* target rows
   (``is_current = 1``), computes the per-key diff, expires changed
   rows, and inserts the new versions plus any brand-new keys.

Target schema requirements
--------------------------
The target table must declare the three SCD bookkeeping columns whose
names are configurable:

* ``effective_date_column`` (default ``valid_from``) — TEXT/TIMESTAMP.
* ``expiry_date_column`` (default ``valid_to``) — TEXT/TIMESTAMP, nullable.
* ``current_flag_column`` (default ``is_current``) — INTEGER/BOOLEAN.

For surrogate-keyed Type 2 use :class:`ScdType7`.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.connectors.knots.database_query_source import (
    DatabaseQuerySource,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.domains.data.specializations.scd.scd_type_2_merge_knot import (
    ScdType2MergeKnot,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ScdType2(SubTapestry):
    """SubTapestry that performs a Type 2 effective-dated SCD merge."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_keys: Sequence[str],
        column_names: Sequence[str],
        effective_date_column: str = "valid_from",
        expiry_date_column: str = "valid_to",
        current_flag_column: str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType2: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType2: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "ScdType2: source_query must be a non-empty string"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns(
            "primary_keys", primary_key_tuple
        )
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        IdentifierValidator.validate_column(
            "effective_date_column", effective_date_column
        )
        IdentifierValidator.validate_column(
            "expiry_date_column", expiry_date_column
        )
        IdentifierValidator.validate_column(
            "current_flag_column", current_flag_column
        )
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(
                f"ScdType2: primary_keys not in column_names: {missing}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._primary_keys = primary_key_tuple
        self._column_names = column_tuple
        self._effective_date_column = effective_date_column
        self._expiry_date_column = expiry_date_column
        self._current_flag_column = current_flag_column
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            ScdType2MergeKnot(
                rows=extracted,
                target_pool=self._target_pool,
                target_table=self._target_table,
                primary_keys=self._primary_keys,
                column_names=self._column_names,
                effective_date_column=self._effective_date_column,
                expiry_date_column=self._expiry_date_column,
                current_flag_column=self._current_flag_column,
                _config=KnotConfig(id="merge"),
            )
        inner_result = await self._run_inner(inner)
        return {
            "succeeded": inner_result.succeeded,
            "target_table": self._target_table,
        }
