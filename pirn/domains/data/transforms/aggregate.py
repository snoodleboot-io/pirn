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
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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
        by: Sequence[str],
        aggs: Mapping[str, AggregateSpec],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError(
                "Aggregate: by must be a sequence of column names "
                "(e.g. tuple or list)"
            )
        if not by:
            raise ValueError("Aggregate: by must be non-empty")
        for b in by:
            if not isinstance(b, str) or not b:
                raise TypeError("Aggregate: every entry in by must be a non-empty string")
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "Aggregate: aggs must be a non-empty Mapping[output_column, "
                "AggregateSpec]"
            )
        for output_name, spec in aggs.items():
            if not isinstance(output_name, str) or not output_name:
                raise TypeError("Aggregate: aggs keys must be non-empty strings")
            if not isinstance(spec, AggregateSpec):
                raise TypeError(
                    f"Aggregate: aggs[{output_name!r}] must be an AggregateSpec, "
                    f"got {type(spec).__name__}"
                )
        self._by: tuple[str, ...] = tuple(by)
        self._aggs: dict[str, AggregateSpec] = dict(aggs)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    @property
    def aggs(self) -> Mapping[str, AggregateSpec]:
        return dict(self._aggs)

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        """Group the batch by the configured columns, apply per-group aggregations, and return the result.

        Args:
            batch: The DataBatch to group and aggregate.

        Returns:
            A new DataBatch with one row per group and columns for each aggregation output.
        """
        groups = self._group_rows(batch)
        out_rows: list[Mapping[str, Any]] = []
        for key_tuple, rows_in_group in groups.items():
            out_row: dict[str, Any] = dict(zip(self._by, key_tuple))
            for output_name, spec in self._aggs.items():
                values = [
                    row[spec.source]
                    for row in rows_in_group
                    if spec.source in row
                ]
                out_row[output_name] = self._apply(spec.function, values)
            out_rows.append(out_row)
        new_schema = self._rebuild_schema(batch.schema)
        return batch.with_rows(tuple(out_rows)).with_schema(new_schema)

    def _group_rows(
        self, batch: DataBatch
    ) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
        groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
        for row in batch.rows:
            key = tuple(self._hashable(row.get(b)) for b in self._by)
            groups.setdefault(key, []).append(row)
        return groups

    def _apply(self, function: str, values: list[Any]) -> Any:
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
            return len({self._hashable(v) for v in non_null})
        if function == "first":
            return values[0] if values else None
        if function == "last":
            return values[-1] if values else None
        # AggregateSpec validation should have prevented this; defence in depth.
        raise ValueError(f"Aggregate: unknown aggregation function {function!r}")

    def _rebuild_schema(self, schema: DataSchema) -> DataSchema:
        new_columns: dict[str, type] = {}
        for column in self._by:
            new_columns[column] = schema.columns.get(column, object)
        for output_name in self._aggs:
            new_columns[output_name] = object
        primary_keys = self._by
        return DataSchema(columns=new_columns, primary_keys=primary_keys)

    @staticmethod
    def _hashable(value: Any) -> Any:
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
