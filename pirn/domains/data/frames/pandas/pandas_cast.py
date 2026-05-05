"""``PandasCast`` — Tier-2 type coercion via :meth:`pandas.DataFrame.astype`.

The ``casts`` mapping accepts either a numpy/pandas dtype, a dtype
string (``"int64"``, ``"float64"``, ``"string"``, ``"bool"``), or a
Python primitive type (``int``, ``float``, ``str``, ``bool``); the
latter is translated to the corresponding pandas dtype.

Algorithm:
    1. Validate ``casts`` as a non-empty Mapping with non-empty string keys.
    2. Normalise each value via :meth:`_normalise_dtype`:
       - Python primitive types (``int``, ``float``, ``str``, ``bool``) map
         to their pandas dtype equivalents (``"int64"``, ``"float64"``,
         ``"string"``, ``"bool"``).
       - String dtype names and objects with a ``.kind`` or ``.name``
         attribute are passed through to ``astype`` unchanged.
       - Anything else raises :class:`TypeError`.
    3. Restrict the normalised mapping to columns that actually exist in the
       frame (unknown columns are silently skipped).
    4. If no applicable columns remain, return the batch unchanged.
    5. Call ``frame.astype(applicable)`` and return the result wrapped in a
       new :class:`PandasDataBatch`.

References:
    [1] pandas — DataFrame.astype:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.astype.html
    [2] pandas — dtype reference:
        https://pandas.pydata.org/docs/user_guide/basics.html#dtypes
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasCast(Knot):
    """Coerce values per column to caller-specified Pandas dtypes."""

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
        batch: PandasDataBatch,
        casts: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Cast the configured columns to their target dtypes and return the updated batch.

        Args:
            batch: The PandasDataBatch whose columns are to be cast.
            casts: Mapping of column name to dtype.

        Returns:
            A new PandasDataBatch with the configured columns cast to their target dtypes.
        """
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError(
                "PandasCast: casts must be a non-empty Mapping[column, dtype]"
            )
        for column in casts:
            if not isinstance(column, str) or not column:
                raise TypeError("PandasCast: casts keys must be non-empty strings")
        normalised: dict[str, Any] = {
            column: self._normalise_dtype(column, dtype)
            for column, dtype in casts.items()
        }
        applicable = {
            column: dtype for column, dtype in normalised.items()
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
