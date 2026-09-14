"""``PolarsPivot`` — wide reshape via :meth:`polars.DataFrame.pivot`.

Each unique value in ``on`` becomes a new column whose values come from
``values`` (one or more), grouped by ``index``. Wraps Polars's native
pivot so callers benefit from its vectorised execution and choice of
aggregator (``first``, ``last``, ``sum``, ``mean``, ``min``, ``max``,
``count``, ``len``).

Algorithm:
    1. Validate ``aggregate_function`` against the allowed set (or None).
    2. Coerce ``on``, ``index``, and ``values`` from string scalars or
       sequences to ``tuple[str, ...]`` via :meth:`_coerce_columns`,
       which also validates non-empty column names.
    3. Call ``frame.pivot(on=..., index=..., values=...,
       aggregate_function=...)`` to produce the wide-format frame.
    4. Return the result wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.pivot:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.pivot.html
    [2] Polars — reshaping guide:
        https://docs.pola.rs/user-guide/transformations/unpivot/
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

from pirn.core.annotation_import import AnnotationImport
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn_data.value_shape import ValueShape


class PolarsPivot(Knot):
    """Wide reshape: each value in ``on`` becomes a new column."""

    _annotation_imports: ClassVar[Mapping[str, AnnotationImport]] = {
        "pl": AnnotationImport("polars", extra="polars", package="pirn-data"),
    }

    def __init__(
        self,
        *,
        batch: Knot,
        on: Knot | str | Sequence[str],
        index: Knot | str | Sequence[str],
        values: Knot | str | Sequence[str],
        aggregate_function: Knot | str | None = "first",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            on=on,
            index=index,
            values=values,
            aggregate_function=aggregate_function,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: PolarsDataBatch,
        on: Any,
        index: Any,
        values: Any,
        aggregate_function: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Pivot the batch to wide format using Polars's native pivot and return the result.

        Args:
            batch: The upstream PolarsDataBatch to reshape.
            on: Column(s) whose unique values become new column names.
            index: Column(s) used as row identifiers.
            values: Column(s) whose values fill the pivoted cells.
            aggregate_function: Aggregation to apply when multiple values map to
                the same cell (first/last/sum/mean/min/max/count/len/None).

        Returns:
            A new PolarsDataBatch in wide format with one column per unique value in ``on``.
        """
        polars_aggregate = self._polars_aggregate_function(aggregate_function)
        on_coerced = self._coerce_columns("on", on)
        index_coerced = self._coerce_columns("index", index)
        values_coerced = self._coerce_columns("values", values)
        return batch.with_frame(
            batch.frame.pivot(
                on=list(on_coerced),
                index=list(index_coerced),
                values=list(values_coerced),
                aggregate_function=polars_aggregate,
            )
        )

    @staticmethod
    def _polars_aggregate_function(
        aggregate_function: object,
    ) -> Literal["first", "last", "sum", "mean", "min", "max", "len"] | None:
        """Map the accepted ``aggregate_function`` names onto Polars's pivot aggregations.

        ``"count"`` is kept as a spelling of ``"len"``, the name Polars uses for it
        since 0.20.5 (the old name still works there but warns).
        """
        if aggregate_function is None:
            return None
        if isinstance(aggregate_function, str):
            match aggregate_function:
                case "first" | "last" | "sum" | "mean" | "min" | "max" | "len":
                    return aggregate_function
                case "count":
                    return "len"
                case _:
                    pass
        raise ValueError(
            "PolarsPivot: aggregate_function must be one of "
            "['first', 'last', 'sum', 'mean', 'min', 'max', 'count', 'len', None], "
            f"got {aggregate_function!r}"
        )

    @staticmethod
    def _coerce_columns(name: str, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            if not value:
                raise ValueError(f"PolarsPivot: {name} must be a non-empty string")
            return (value,)
        if not ValueShape.is_sequence(value):
            raise TypeError(
                f"PolarsPivot: {name} must be a string or sequence of strings, "
                f"got {type(value).__name__}"
            )
        coerced = tuple(value)
        if not coerced:
            raise ValueError(f"PolarsPivot: {name} must be non-empty")
        for column in coerced:
            if not isinstance(column, str) or not column:
                raise TypeError(f"PolarsPivot: every entry in {name} must be a non-empty string")
        return coerced
