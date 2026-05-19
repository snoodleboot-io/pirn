"""``Aggregate`` — group rows by one or more columns and compute per-group
aggregations.

Output rows contain one entry per group. Each output row carries the
group-by column values plus one column per :class:`AggregateSpec`
declared in ``aggs``. The schema is rewritten to reflect the new shape:
columns are ``by + tuple(aggs.keys())``.

Null handling: aggregations skip ``None`` values (``count`` counts only
non-null entries — use a separate :class:`pirn.domains.data.transforms.filter.Filter`
or a downstream null-rate check for null counting). Empty groups (after
filtering nulls) yield ``None`` for ``mean`` / ``min`` / ``max`` /
``first`` / ``last`` and ``0`` for ``count`` / ``count_distinct``.

Algorithm:
    1. Validate ``by`` (non-empty sequence of non-empty strings) and ``aggs``
       (non-empty mapping of output name → :class:`AggregateSpec`).
    2. Partition all rows into groups keyed by the ``by``-column tuple.
       Unhashable values (e.g. lists) are coerced to their ``repr`` for
       grouping purposes.
    3. For each group, extract the source column values from every row in
       the group, filter out ``None``, then apply the specified aggregation
       function.
    4. Assemble output rows as ``{by_cols..., output_col: agg_value, ...}``.
    5. Rebuild the :class:`DataSchema` with ``by`` as primary keys and
       ``object`` as the type for each aggregation output column.

    ```text
    groups = partition(rows, key=lambda row: tuple(row[b] for b in by))
    for key, rows_in_group in groups:
        out_row = dict(zip(by, key))
        for output_name, spec in aggs:
            values = [row[spec.source] for row in rows_in_group if spec.source in row]
            out_row[output_name] = aggregate(spec.function, non_null(values))
        emit out_row
    ```

Math:
    For a group of :math:`N` rows with non-null source values
    :math:`v_1, \\ldots, v_k` (where :math:`k \\leq N`):

    $$
    \\text{sum}     = \\sum_{i=1}^{k} v_i
    $$

    $$
    \\text{mean}    = \\begin{cases}
        \\displaystyle\\frac{\\sum v_i}{k} & k > 0 \\\\
        \\text{None}                        & k = 0
    \\end{cases}
    $$

    $$
    \\text{count}          = k, \\quad
    \\text{count\\_distinct} = \\bigl|\\{v_1,\\ldots,v_k\\}\\bigr|
    $$

References:
    [1] Kimball, R. & Ross, M. — *The Data Warehouse Toolkit* (3rd ed.),
        Chapter 3 — Fact Table Techniques (group-by aggregation patterns):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/
    [2] Python ``itertools.groupby`` — alternative approach (not used here;
        requires pre-sorted input, which pirn does not guarantee):
        https://docs.python.org/3/library/itertools.html#itertools.groupby
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec


class Aggregate(Knot):
    """Group-by + aggregation knot."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, AggregateSpec],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> DataBatch:
        """Group the batch by the configured columns and apply per-group aggregations.

        Args:
            batch: The DataBatch to group and aggregate.
            by: Sequence of column names to group by.
            aggs: Mapping of output column name to AggregateSpec.

        Returns:
            A new DataBatch with one row per group and columns for each aggregation output.
        """
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError("Aggregate: by must be a sequence of column names (e.g. tuple or list)")
        if not by:
            raise ValueError("Aggregate: by must be non-empty")
        for b in by:
            if not isinstance(b, str) or not b:
                raise TypeError("Aggregate: every entry in by must be a non-empty string")
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "Aggregate: aggs must be a non-empty Mapping[output_column, AggregateSpec]"
            )
        for output_name, spec in aggs.items():
            if not isinstance(output_name, str) or not output_name:
                raise TypeError("Aggregate: aggs keys must be non-empty strings")
            if not isinstance(spec, AggregateSpec):
                raise TypeError(
                    f"Aggregate: aggs[{output_name!r}] must be an AggregateSpec, "
                    f"got {type(spec).__name__}"
                )
        by_tuple: tuple[str, ...] = tuple(by)
        aggs_dict: dict[str, AggregateSpec] = dict(aggs)
        groups = self._group_rows(batch, by_tuple)
        out_rows: list[Mapping[str, Any]] = []
        for key_tuple, rows_in_group in groups.items():
            out_row: dict[str, Any] = dict(zip(by_tuple, key_tuple, strict=False))
            for output_name, spec in aggs_dict.items():
                values = [row[spec.source] for row in rows_in_group if spec.source in row]
                out_row[output_name] = self._apply(spec.function, values)
            out_rows.append(out_row)
        new_schema = self._rebuild_schema(batch.schema, by_tuple, aggs_dict)
        return batch.with_rows(tuple(out_rows)).with_schema(new_schema)

    @staticmethod
    def _group_rows(
        batch: DataBatch, by: tuple[str, ...]
    ) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
        groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
        for row in batch.rows:
            for b in by:
                if b not in row:
                    raise ValueError(f"Aggregate: group-by column {b!r} missing from row")
            key = tuple(Aggregate._hashable(row[b]) for b in by)
            groups.setdefault(key, []).append(row)
        return groups

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
            return len({Aggregate._hashable(v) for v in non_null})
        if function == "first":
            return values[0] if values else None
        if function == "last":
            return values[-1] if values else None
        # AggregateSpec validation should have prevented this; defence in depth.
        raise ValueError(f"Aggregate: unknown aggregation function {function!r}")

    @staticmethod
    def _rebuild_schema(
        schema: DataSchema,
        by: tuple[str, ...],
        aggs: dict[str, AggregateSpec],
    ) -> DataSchema:
        new_columns: dict[str, type] = {}
        for column in by:
            new_columns[column] = schema.columns.get(column, object)
        for output_name in aggs:
            new_columns[output_name] = object
        return DataSchema(columns=new_columns, primary_keys=by)

    @staticmethod
    def _hashable(value: Any) -> Any:
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
