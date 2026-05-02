"""``ScdType1`` — Kimball Type 1 Slowly Changing Dimension.

Type 1 ("overwrite-on-change") replaces the existing target row's
non-key columns whenever the source row's values differ. No history is
preserved — the previous attribute values are lost. Use this for
attributes where only the current value matters (e.g. customer name
typo fix, normalisation update).

Composition:

1. :class:`DatabaseQuerySource` reads the source rows.
2. :class:`ScdType1MergeKnot` reads the existing target rows, computes
   the diff, and issues parameterised INSERT / UPDATE statements
   against the target pool.

For history-preserving SCD use :class:`ScdType2` (effective dating) or
:class:`ScdType7` (surrogate key + Type 2 history).
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
from pirn.domains.data.specializations.scd.scd_type_1_merge_knot import (
    ScdType1MergeKnot,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ScdType1(SubTapestry):
    """SubTapestry that performs a Type 1 SCD merge."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        primary_keys: Sequence[str],
        column_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType1: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType1: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "ScdType1: source_query must be a non-empty string"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        primary_key_tuple = tuple(primary_keys)
        IdentifierValidator.validate_columns(
            "primary_keys", primary_key_tuple
        )
        column_tuple = tuple(column_names)
        IdentifierValidator.validate_columns("column_names", column_tuple)
        missing = [k for k in primary_key_tuple if k not in column_tuple]
        if missing:
            raise ValueError(
                f"ScdType1: primary_keys not in column_names: {missing}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._primary_keys = primary_key_tuple
        self._column_names = column_tuple
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        with Tapestry() as inner:
            extracted = DatabaseQuerySource(
                pool=self._source_pool,
                query=self._source_query,
                _config=KnotConfig(id="extract"),
            )
            ScdType1MergeKnot(
                rows=extracted,
                target_pool=self._target_pool,
                target_table=self._target_table,
                primary_keys=self._primary_keys,
                column_names=self._column_names,
                _config=KnotConfig(id="merge"),
            )
        inner_result = await self._run_inner(inner)
        return {
            "succeeded": inner_result.succeeded,
            "target_table": self._target_table,
        }
