"""``PolarsUnpivot`` — long reshape via :meth:`polars.DataFrame.unpivot`.

Inverse of :class:`PolarsPivot`. Selected ``on`` columns collapse into
two: a name column (default ``"variable"``) and a value column (default
``"value"``). ``index`` columns are repeated for each row produced.

Algorithm:
    1. Validate ``variable_name`` and ``value_name`` as non-empty strings.
    2. Coerce and validate ``on`` as a non-empty sequence of non-empty
       strings via :meth:`_coerce_columns`.
    3. Coerce and validate ``index`` as an optional sequence of non-empty
       strings (may be empty or None).
    4. Call ``frame.unpivot(on=..., index=..., variable_name=...,
       value_name=...)`` to reshape the frame.
    5. Return the result wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.unpivot:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.unpivot.html
    [2] Polars — reshaping guide:
        https://docs.pola.rs/user-guide/transformations/unpivot/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsUnpivot(Knot):
    """Long reshape: selected columns collapse into name/value pairs."""

    def __init__(
        self,
        *,
        batch: Knot,
        on: Knot | Sequence[str],
        index: Knot | Sequence[str] | None = None,
        variable_name: Knot | str = "variable",
        value_name: Knot | str = "value",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            on=on,
            index=index,
            variable_name=variable_name,
            value_name=value_name,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: PolarsDataBatch,
        on: Any,
        index: Any,
        variable_name: Any,
        value_name: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Unpivot the configured columns from wide to long format and return the result.

        Args:
            batch: The upstream PolarsDataBatch to reshape.
            on: Columns to collapse into name/value pairs.
            index: Columns to keep as identifiers (repeated per row produced).
            variable_name: Name for the new column holding original column names.
            value_name: Name for the new column holding original values.

        Returns:
            A new PolarsDataBatch in long format with variable and value columns.
        """
        if not variable_name:
            raise ValueError("PolarsUnpivot: variable_name must be non-empty")
        if not value_name:
            raise ValueError("PolarsUnpivot: value_name must be non-empty")
        on_coerced = self._coerce_columns("on", on, allow_empty=False)
        index_coerced = (
            self._coerce_columns("index", index, allow_empty=True) if index is not None else ()
        )
        return batch.with_frame(
            batch.frame.unpivot(
                on=list(on_coerced),
                index=list(index_coerced) if index_coerced else None,
                variable_name=variable_name,
                value_name=value_name,
            )
        )

    @staticmethod
    def _coerce_columns(name: str, value: Any, *, allow_empty: bool) -> tuple[str, ...]:
        if isinstance(value, str):
            if not value:
                raise ValueError(f"PolarsUnpivot: {name} must be a non-empty string")
            return (value,)
        if not isinstance(value, Sequence):
            raise TypeError(
                f"PolarsUnpivot: {name} must be a sequence of strings, got {type(value).__name__}"
            )
        coerced = tuple(value)
        if not coerced and not allow_empty:
            raise ValueError(f"PolarsUnpivot: {name} must be non-empty")
        for column in coerced:
            if not isinstance(column, str) or not column:
                raise TypeError(f"PolarsUnpivot: every entry in {name} must be a non-empty string")
        return coerced
