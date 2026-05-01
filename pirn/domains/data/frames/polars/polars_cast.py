"""``PolarsCast`` — Tier-2 type coercion via :meth:`polars.DataFrame.cast`.

The ``casts`` mapping accepts either a Polars dtype (``pl.Int64``,
``pl.Float64``, …) or a Python primitive type (``int``, ``float``,
``str``, ``bool``); the latter is translated to the corresponding Polars
dtype.
"""

from __future__ import annotations

from typing import Any, Mapping

import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsCast(Knot):
    """Coerce values per column to caller-specified Polars dtypes."""

    def __init__(
        self,
        *,
        batch: Knot,
        casts: Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError(
                "PolarsCast: casts must be a non-empty Mapping[column, dtype]"
            )
        for column in casts:
            if not isinstance(column, str) or not column:
                raise TypeError("PolarsCast: casts keys must be non-empty strings")
        self._casts: dict[str, pl.DataType] = {
            column: self._normalise_dtype(column, dtype)
            for column, dtype in casts.items()
        }
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def casts(self) -> Mapping[str, pl.DataType]:
        return dict(self._casts)

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        applicable = {
            column: dtype for column, dtype in self._casts.items()
            if column in batch.frame.columns
        }
        if not applicable:
            return batch
        return batch.with_frame(batch.frame.cast(applicable))

    def _normalise_dtype(self, column: str, dtype: Any) -> pl.DataType:
        # Already a Polars dtype? Pass through.
        if isinstance(dtype, pl.DataType) or (
            isinstance(dtype, type) and issubclass(dtype, pl.DataType)
        ):
            return dtype  # type: ignore[return-value]
        # Python primitive → Polars dtype.
        primitives: dict[type, pl.DataType] = {
            int: pl.Int64(),
            float: pl.Float64(),
            str: pl.Utf8(),
            bool: pl.Boolean(),
        }
        if isinstance(dtype, type) and dtype in primitives:
            return primitives[dtype]
        raise TypeError(
            f"PolarsCast: casts[{column!r}] must be a Polars dtype or a "
            f"Python primitive (int/float/str/bool), got {dtype!r}"
        )
