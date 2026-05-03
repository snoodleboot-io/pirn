"""``PandasCast`` — Tier-2 type coercion via :meth:`pandas.DataFrame.astype`.

The ``casts`` mapping accepts either a numpy/pandas dtype, a dtype
string (``"int64"``, ``"float64"``, ``"string"``, ``"bool"``), or a
Python primitive type (``int``, ``float``, ``str``, ``bool``); the
latter is translated to the corresponding pandas dtype.
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasCast(Knot):
    """Coerce values per column to caller-specified Pandas dtypes."""

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
                "PandasCast: casts must be a non-empty Mapping[column, dtype]"
            )
        for column in casts:
            if not isinstance(column, str) or not column:
                raise TypeError("PandasCast: casts keys must be non-empty strings")
        self._casts: dict[str, Any] = {
            column: self._normalise_dtype(column, dtype)
            for column, dtype in casts.items()
        }
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def casts(self) -> Mapping[str, Any]:
        return dict(self._casts)

    async def process(self, batch: PandasDataBatch, **_: Any) -> PandasDataBatch:
        """Cast the configured columns to their target dtypes and return the updated batch.

        Args:
            batch: The PandasDataBatch whose columns are to be cast.

        Returns:
            A new PandasDataBatch with the configured columns cast to their target dtypes.
        """
        applicable = {
            column: dtype for column, dtype in self._casts.items()
            if column in batch.frame.columns
        }
        if not applicable:
            return batch
        return batch.with_frame(batch.frame.astype(applicable))

    def _normalise_dtype(self, column: str, dtype: Any) -> Any:
        # Python primitive → pandas/numpy dtype string.
        primitives: dict[type, str] = {
            int: "int64",
            float: "float64",
            str: "string",
            bool: "bool",
        }
        if isinstance(dtype, type) and dtype in primitives:
            return primitives[dtype]
        # Strings and dtype-like objects (numpy dtype, pandas extension dtype)
        # are passed straight through to ``astype`` which validates them.
        if isinstance(dtype, str) and dtype:
            return dtype
        if hasattr(dtype, "kind") or hasattr(dtype, "name"):
            return dtype
        raise TypeError(
            f"PandasCast: casts[{column!r}] must be a Pandas dtype or a "
            f"Python primitive (int/float/str/bool), got {dtype!r}"
        )
