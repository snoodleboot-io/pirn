"""``PandasAggregate`` — Tier-2 group-by + aggregation via Pandas's native
``groupby`` / ``agg`` API.

Unlike :class:`pirn.domains.data.frames.polars.polars_aggregate.PolarsAggregate`
(which takes ``polars.Expr`` directly), this knot takes a
``Mapping[output_column, AggregateSpec]`` matching the Tier-1
:class:`pirn.domains.data.transforms.aggregate.Aggregate` vocabulary
(sum/mean/min/max/count/count_distinct/first/last). Each spec maps to
the equivalent pandas aggregation inside :meth:`_apply`.

Algorithm:
    1. Validate ``by`` as a non-empty sequence of non-empty strings.
    2. Validate ``aggs`` as a non-empty Mapping whose values are all
       :class:`AggregateSpec` instances.
    3. Call ``frame.groupby(by, sort=False, dropna=False)`` to obtain
       groups without sorting and preserving NaN-keyed groups.
    4. For each group key, build an output row from the by-columns, then
       for each ``AggregateSpec`` call :meth:`_apply` on the relevant
       series to compute the scalar result.
    5. Assemble all output rows into a new ``DataFrame`` with column
       order ``[*by, *aggs.keys()]``.
    6. Return the result wrapped in a new :class:`PandasDataBatch`.

    ```text
    grouped = frame.groupby(by, sort=False, dropna=False)
    for key, group in grouped:
        row = {col: key_val for col, key_val in zip(by, key)}
        for output_name, spec in aggs.items():
            row[output_name] = apply(spec.function, group[spec.source])
        out_rows.append(row)
    return DataFrame(out_rows, columns=[*by, *aggs.keys()])
    ```

References:
    [1] pandas — DataFrame.groupby:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html
    [2] pandas — GroupBy.agg:
        https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.DataFrameGroupBy.agg.html
    [3] Alternative: pandas GroupBy.agg with string function names (chosen
        manual dispatch here to map Tier-1 AggregateSpec vocabulary):
        https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.DataFrameGroupBy.agg.html
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

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
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, AggregateSpec],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: PandasDataBatch,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Group by configured columns, apply AggregateSpec functions, and return the result.

        Args:
            batch: The PandasDataBatch to group and aggregate.
            by: Sequence of column names to group by.
            aggs: Mapping of output column name to AggregateSpec.

        Returns:
            A new PandasDataBatch containing the aggregated result.
        """
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError("PandasAggregate: by must be a sequence of column names")
        if not by:
            raise ValueError("PandasAggregate: by must be non-empty")
        for column in by:
            if not isinstance(column, str) or not column:
                raise TypeError("PandasAggregate: every entry in by must be a non-empty string")
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "PandasAggregate: aggs must be a non-empty Mapping[output_column, AggregateSpec]"
            )
        for output_name, spec in aggs.items():
            if not isinstance(output_name, str) or not output_name:
                raise TypeError("PandasAggregate: aggs keys must be non-empty strings")
            if not isinstance(spec, AggregateSpec):
                raise TypeError(
                    f"PandasAggregate: aggs[{output_name!r}] must be an AggregateSpec, "
                    f"got {type(spec).__name__}"
                )
        by_tuple: tuple[str, ...] = tuple(by)
        aggs_dict: dict[str, AggregateSpec] = dict(aggs)
        grouped = batch.frame.groupby(list(by_tuple), sort=False, dropna=False)
        out_rows: list[dict[str, Any]] = []
        for key, group in grouped:
            key_tuple = key if isinstance(key, tuple) else (key,)
            row: dict[str, Any] = dict(zip(by_tuple, key_tuple, strict=False))
            for output_name, spec in aggs_dict.items():
                if spec.source in group.columns:
                    series = group[spec.source]
                else:
                    series = pd.Series(dtype=object)
                row[output_name] = self._apply(spec.function, series)
            out_rows.append(row)
        column_order = list(by_tuple) + list(aggs_dict.keys())
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
            return len(non_null)
        if function == "count_distinct":
            return int(non_null.nunique())
        if function == "first":
            return series.iloc[0] if len(series) > 0 else None
        if function == "last":
            return series.iloc[-1] if len(series) > 0 else None
        # AggregateSpec validation should have prevented this; defence in depth.
        raise ValueError(f"PandasAggregate: unknown aggregation function {function!r}")
