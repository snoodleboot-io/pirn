"""``PolarsPivot`` — wide reshape via :meth:`polars.DataFrame.pivot`.

Each unique value in ``on`` becomes a new column whose values come from
``values`` (one or more), grouped by ``index``. Wraps Polars's native
pivot so callers benefit from its vectorised execution and choice of
aggregator (``first``, ``last``, ``sum``, ``mean``, ``min``, ``max``,
``count``, ``len``).
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsPivot(Knot):
    """Wide reshape: each value in ``on`` becomes a new column."""

    def __init__(
        self,
        *,
        batch: Knot,
        on: str | Sequence[str],
        index: str | Sequence[str],
        values: str | Sequence[str],
        aggregate_function: str | None = "first",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed_aggs = (
            "first", "last", "sum", "mean", "min", "max", "count", "len", None,
        )
        if aggregate_function not in allowed_aggs:
            raise ValueError(
                f"PolarsPivot: aggregate_function must be one of {list(allowed_aggs)}, "
                f"got {aggregate_function!r}"
            )
        self._on = self._coerce_columns("on", on)
        self._index = self._coerce_columns("index", index)
        self._values = self._coerce_columns("values", values)
        self._aggregate_function = aggregate_function
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def on(self) -> tuple[str, ...]:
        return self._on

    @property
    def index(self) -> tuple[str, ...]:
        return self._index

    @property
    def values(self) -> tuple[str, ...]:
        return self._values

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        """Pivot the batch to wide format using Polars's native pivot and return the result.

        Args:
            batch: The upstream PolarsDataBatch to reshape.

        Returns:
            A new PolarsDataBatch in wide format with one column per unique value in ``on``.
        """
        return batch.with_frame(
            batch.frame.pivot(
                on=list(self._on),
                index=list(self._index),
                values=list(self._values),
                aggregate_function=self._aggregate_function,
            )
        )

    @staticmethod
    def _coerce_columns(name: str, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            if not value:
                raise ValueError(f"PolarsPivot: {name} must be a non-empty string")
            return (value,)
        if not isinstance(value, Sequence):
            raise TypeError(
                f"PolarsPivot: {name} must be a string or sequence of strings, "
                f"got {type(value).__name__}"
            )
        coerced = tuple(value)
        if not coerced:
            raise ValueError(f"PolarsPivot: {name} must be non-empty")
        for column in coerced:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    f"PolarsPivot: every entry in {name} must be a non-empty string"
                )
        return coerced
