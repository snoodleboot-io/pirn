"""``PandasJoin`` — Tier-2 binary join via :meth:`pandas.DataFrame.merge`.

Mirrors the parameter shape of
:class:`pirn.domains.data.frames.polars.polars_join.PolarsJoin` but uses
pandas's join vocabulary (``inner``, ``left``, ``right``, ``outer``,
``cross``). Pandas does not natively support ``semi`` or ``anti`` joins,
so those values are rejected at construction time with a clear error
message.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasJoin(Knot):
    """Binary join over two :class:`PandasDataBatch` parents."""

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        how: str = "inner",
        suffix: str = "_right",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed_how = ("inner", "left", "right", "outer", "cross")
        if how in ("semi", "anti"):
            raise ValueError(
                "PandasJoin: pandas does not natively support "
                f"{how!r} joins; use a filter/anti-pattern with isin() instead"
            )
        if how not in allowed_how:
            raise ValueError(
                f"PandasJoin: how must be one of {list(allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError(
                    "PandasJoin: cross join takes no on/left_on/right_on"
                )
        else:
            self._validate_keys(on, left_on, right_on)
        self._on = self._coerce_keys(on)
        self._left_on = self._coerce_keys(left_on)
        self._right_on = self._coerce_keys(right_on)
        self._how = how
        self._suffix = suffix
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: PandasDataBatch, right: PandasDataBatch, **_: Any
    ) -> PandasDataBatch:
        suffixes = ("", self._suffix)
        if self._how == "cross":
            joined = left.frame.merge(
                right.frame, how="cross", suffixes=suffixes
            )
        elif self._on is not None:
            joined = left.frame.merge(
                right.frame,
                on=list(self._on),
                how=self._how,
                suffixes=suffixes,
            )
        else:
            assert self._left_on is not None and self._right_on is not None
            joined = left.frame.merge(
                right.frame,
                left_on=list(self._left_on),
                right_on=list(self._right_on),
                how=self._how,
                suffixes=suffixes,
            )
        return left.with_frame(joined.reset_index(drop=True))

    def _validate_keys(
        self,
        on: str | Sequence[str] | None,
        left_on: str | Sequence[str] | None,
        right_on: str | Sequence[str] | None,
    ) -> None:
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError(
                "PandasJoin: pass either on= or left_on/right_on, not both"
            )
        if on is None and (left_on is None or right_on is None):
            raise TypeError(
                "PandasJoin: provide on= for matching columns, or both "
                "left_on= and right_on= for differently-named keys"
            )

    @staticmethod
    def _coerce_keys(
        value: str | Sequence[str] | None,
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return (value,)
        return tuple(value)
