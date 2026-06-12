"""``GoldAggregation`` — aggregate a silver table into a gold business mart.

Tier-1 dict-based pipeline (small batches):

1. Fetch silver rows from the source pool.
2. Key them into a :class:`DataBatch` by column name.
3. Group by ``by`` and compute ``aggs`` (inline aggregation).
4. Project output rows to positional tuples.
5. Write to the gold target via ``execute_many``.

Algorithm:
    1. Receive all inputs in ``process()`` and validate.
    2. Fetch silver rows via ``source_pool.fetch_all``.
    3. Convert tuples to row dicts keyed by ``source_columns``.
    4. Group rows by the ``by`` key tuple.
    5. For each group, compute each ``AggregateSpec`` aggregate.
    6. Derive ``target_columns`` as ``by + tuple(aggs.keys())``.
    7. Build the INSERT query and write via ``target_pool.execute_many``.
    8. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_inserted``.

References:
    [1] pirn — AggregateSpec: pirn/domains/data/transforms/aggregate_spec.py
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec


class GoldAggregation(Knot):
    """Silver → Gold: group by + aggregations into a business mart."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        source_columns: Knot | Sequence[str],
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, AggregateSpec],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            source_columns=source_columns,
            target_pool=target_pool,
            target_table=target_table,
            by=by,
            aggs=aggs,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_insert_query(target_table: str, target_columns: tuple[str, ...]) -> str:
        column_list = ", ".join(target_columns)
        placeholders = ", ".join(["?"] * len(target_columns))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _apply(function: str, values: list[Any]) -> Any:
        non_null = [v for v in values if v is not None]
        if function == "sum":
            return sum(non_null) if non_null else 0
        if function == "mean":
            return sum(non_null) / len(non_null) if non_null else None
        if function == "min":
            return min(non_null) if non_null else None
        if function == "max":
            return max(non_null) if non_null else None
        if function == "count":
            return len(non_null)
        if function == "count_distinct":
            primitives = (int, float, str, bool, type(None))
            hashable = {repr(v) if not isinstance(v, primitives) else v for v in non_null}
            return len(hashable)
        if function == "first":
            return values[0] if values else None
        if function == "last":
            return values[-1] if values else None
        raise ValueError(f"GoldAggregation: unknown aggregation function {function!r}")

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        source_columns: Any,
        target_pool: Any,
        target_table: Any,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, fetch silver rows, aggregate, write to gold table, return summary.

        Args:
            source_pool: Pool to read silver rows from.
            source_query: SELECT query to run against the silver source.
            source_columns: Ordered source column names.
            target_pool: Pool to write gold rows to.
            target_table: Name of the gold target table.
            by: Column names to group by.
            aggs: Mapping of output column name to :class:`AggregateSpec`.

        Returns:
            A dict with ``succeeded``, ``target_table``, and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If any string argument is empty, or sequence arguments are empty.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("GoldAggregation: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("GoldAggregation: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("GoldAggregation: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("GoldAggregation: target_table must be a non-empty string")
        source_column_tuple = tuple(source_columns)
        if not source_column_tuple:
            raise ValueError("GoldAggregation: source_columns must be non-empty")
        by_tuple = tuple(by)
        if not by_tuple:
            raise ValueError("GoldAggregation: by must be non-empty")
        aggs_dict: dict[str, AggregateSpec] = dict(aggs)
        target_columns = by_tuple + tuple(aggs_dict.keys())
        # Fetch silver rows and convert to row dicts.
        raw_rows = await source_pool.fetch_all(source_query)
        row_dicts = [dict(zip(source_column_tuple, tuple(r), strict=False)) for r in raw_rows]
        # Group rows by the by-tuple key.
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in row_dicts:
            key = tuple(row.get(col) for col in by_tuple)
            groups[key].append(row)
        # Compute aggregations per group.
        output_rows: list[tuple[Any, ...]] = []
        for key_tuple, group_rows in groups.items():
            out: dict[str, Any] = dict(zip(by_tuple, key_tuple, strict=False))
            for output_name, spec in aggs_dict.items():
                values = [r[spec.source] for r in group_rows if spec.source in r]
                out[output_name] = GoldAggregation._apply(spec.function, values)
            output_rows.append(tuple(out.get(col) for col in target_columns))
        insert_query = GoldAggregation._build_insert_query(target_table, target_columns)
        await target_pool.execute_many(insert_query, output_rows)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": len(output_rows),
        }
