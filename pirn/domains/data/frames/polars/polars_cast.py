"""``PolarsCast`` — Tier-2 type coercion via :meth:`polars.DataFrame.cast`.

The ``casts`` mapping accepts either a Polars dtype (``pl.Int64``,
``pl.Float64``, …) or a Python primitive type (``int``, ``float``,
``str``, ``bool``); the latter is translated to the corresponding Polars
dtype.

Algorithm:
    1. Validate ``casts`` as a non-empty Mapping with non-empty string keys.
    2. Normalise each value via :meth:`_normalise_dtype`:
       - Native Polars ``DataType`` instances or subclasses pass through.
       - Python primitives ``int``, ``float``, ``str``, ``bool`` map to
         ``pl.Int64``, ``pl.Float64``, ``pl.Utf8``, ``pl.Boolean``.
       - Anything else raises :class:`TypeError`.
    3. Restrict the normalised mapping to columns that actually exist in the
       frame (unknown columns are silently skipped).
    4. If no applicable columns remain, return the batch unchanged.
    5. Call ``frame.cast(applicable)`` and return the result wrapped in a
       new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.cast:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.cast.html
    [2] Polars — data types:
        https://docs.pola.rs/user-guide/concepts/data-types/
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
        casts: Knot | Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, casts=casts, _config=_config, **kwargs)

    async def process(
        self,
        batch: PolarsDataBatch,
        casts: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Cast the configured columns to their target Polars dtypes and return the updated batch.

        Args:
            batch: The upstream PolarsDataBatch whose columns will be recast.
            casts: Mapping of column name to Polars dtype.

        Returns:
            A new PolarsDataBatch with the configured columns cast to their target dtypes.
        """
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError("PolarsCast: casts must be a non-empty Mapping[column, dtype]")
        for column in casts:
            if not isinstance(column, str) or not column:
                raise TypeError("PolarsCast: casts keys must be non-empty strings")
        normalised: dict[str, pl.DataType] = {
            column: self._normalise_dtype(column, dtype) for column, dtype in casts.items()
        }
        applicable = {
            column: dtype for column, dtype in normalised.items() if column in batch.frame.columns
        }
        if not applicable:
            return batch
        return batch.with_frame(batch.frame.cast(applicable))  # type: ignore[arg-type]

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
