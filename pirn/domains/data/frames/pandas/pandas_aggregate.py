"""``PandasAggregate`` — Tier-2 group-by + aggregation via Pandas's native
``groupby`` / ``agg`` API.

Unlike :class:`pirn.domains.data.frames.polars.polars_aggregate.PolarsAggregate`
(which takes ``polars.Expr`` directly), this knot takes a
``Mapping[output_column, AggregateSpec]`` matching the Tier-1
:class:`pirn.domains.data.transforms.aggregate.Aggregate` vocabulary
(sum/mean/min/max/count/count_distinct/first/last). Each spec maps to
the equivalent pandas aggregation inside :meth:`_apply`.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec


class PandasAggregate(Knot):
    """Group rows by ``by`` and apply :class:`AggregateSpec` aggregations."""

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
                "PandasAggregate: by must be a sequence of column names"
            )
        if not by:
            raise ValueError("PandasAggregate: by must be non-empty")
        for column in by:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    "PandasAggregate: every entry in by must be a non-empty string"
                )
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "PandasAggregate: aggs must be a non-empty Mapping[output_column, "
                "AggregateSpec]"
            )
        for output_name, spec in aggs.items():
            if not isinstance(output_name, str) or not output_name:
                raise TypeError(
                    "PandasAggregate: aggs keys must be non-empty strings"
                )
            if not isinstance(spec, AggregateSpec):
                raise TypeError(
                    f"PandasAggregate: aggs[{output_name!r}] must be an AggregateSpec, "
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

    async def process(self, batch: PandasDataBatch, **_: Any) -> PandasDataBatch:
        """Group the batch by the configured columns, apply AggregateSpec functions, and return the result.

        Args:
            batch: The PandasDataBatch to group and aggregate.

        Returns:
            A new PandasDataBatch containing the aggregated result.
        """
        grouped = batch.frame.groupby(list(self._by), sort=False, dropna=False)
        out_rows: list[dict[str, Any]] = []
        for key, group in grouped:
            key_tuple = key if isinstance(key, tuple) else (key,)
            row: dict[str, Any] = dict(zip(self._by, key_tuple))
            for output_name, spec in self._aggs.items():
                series = group[spec.source] if spec.source in group.columns else pd.Series(dtype=object)
                row[output_name] = self._apply(spec.function, series)
            out_rows.append(row)
        column_order = list(self._by) + list(self._aggs.keys())
        result = pd.DataFrame(out_rows, columns=column_order)
        return batch.with_frame(result)

    def _apply(self, function: str, series: pd.Series) -> Any:
        non_null = series.dropna()
        if function == "sum":
            return non_null.sum() if len(non_null) > 0 else 0
        if function == "mean":
            return float(non_null.mean()) if len(non_null) > 0 else None
        if function == "min":
            return non_null.min() if len(non_null) > 0 else None
        if function == "max":
            return non_null.max() if len(non_null) > 0 else None
        if function == "count":
            return int(len(non_null))
        if function == "count_distinct":
            return int(non_null.nunique())
        if function == "first":
            return series.iloc[0] if len(series) > 0 else None
        if function == "last":
            return series.iloc[-1] if len(series) > 0 else None
        # AggregateSpec validation should have prevented this; defence in depth.
        raise ValueError(
            f"PandasAggregate: unknown aggregation function {function!r}"
        )
