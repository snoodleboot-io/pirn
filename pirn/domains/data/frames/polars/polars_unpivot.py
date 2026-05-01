"""``PolarsUnpivot`` — long reshape via :meth:`polars.DataFrame.unpivot`.

Inverse of :class:`PolarsPivot`. Selected ``on`` columns collapse into
two: a name column (default ``"variable"``) and a value column (default
``"value"``). ``index`` columns are repeated for each row produced.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsUnpivot(Knot):
    """Long reshape: selected columns collapse into name/value pairs."""

    def __init__(
        self,
        *,
        batch: Knot,
        on: Sequence[str],
        index: Sequence[str] | None = None,
        variable_name: str = "variable",
        value_name: str = "value",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not variable_name:
            raise ValueError("PolarsUnpivot: variable_name must be non-empty")
        if not value_name:
            raise ValueError("PolarsUnpivot: value_name must be non-empty")
        self._on = self._coerce_columns("on", on, allow_empty=False)
        self._index = (
            self._coerce_columns("index", index, allow_empty=True)
            if index is not None
            else ()
        )
        self._variable_name = variable_name
        self._value_name = value_name
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def on(self) -> tuple[str, ...]:
        return self._on

    @property
    def index(self) -> tuple[str, ...]:
        return self._index

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        return batch.with_frame(
            batch.frame.unpivot(
                on=list(self._on),
                index=list(self._index) if self._index else None,
                variable_name=self._variable_name,
                value_name=self._value_name,
            )
        )

    @staticmethod
    def _coerce_columns(
        name: str, value: Any, *, allow_empty: bool
    ) -> tuple[str, ...]:
        if isinstance(value, str):
            if not value:
                raise ValueError(f"PolarsUnpivot: {name} must be a non-empty string")
            return (value,)
        if not isinstance(value, Sequence):
            raise TypeError(
                f"PolarsUnpivot: {name} must be a sequence of strings, "
                f"got {type(value).__name__}"
            )
        coerced = tuple(value)
        if not coerced and not allow_empty:
            raise ValueError(f"PolarsUnpivot: {name} must be non-empty")
        for column in coerced:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    f"PolarsUnpivot: every entry in {name} must be a non-empty string"
                )
        return coerced
