"""``PolarsJoin`` — Tier-2 binary join via :meth:`polars.DataFrame.join`.

This is the first transform that exists *only* at Tier 2 — joining
``tuple[dict, ...]`` row lists at Tier 1 would be O(n²) without
indexing, so we deliberately do not provide a Tier-1 implementation per
the ARD efficiency mandate.

Supports the standard Polars join strategies (``inner``, ``left``,
``right``, ``full``, ``semi``, ``anti``, ``cross``). When ``on`` is a
single string or sequence, both frames join on those columns. When
``left_on`` / ``right_on`` are supplied separately, they may differ.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsJoin(Knot):
    """Binary join over two :class:`PolarsDataBatch` parents."""

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
        allowed_how = ("inner", "left", "right", "full", "semi", "anti", "cross")
        if how not in allowed_how:
            raise ValueError(
                f"PolarsJoin: how must be one of {list(allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError(
                    "PolarsJoin: cross join takes no on/left_on/right_on"
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
        self, left: PolarsDataBatch, right: PolarsDataBatch, **_: Any
    ) -> PolarsDataBatch:
        kwargs: dict[str, Any] = {"how": self._how, "suffix": self._suffix}
        if self._how == "cross":
            joined = left.frame.join(right.frame, **kwargs)
        elif self._on is not None:
            joined = left.frame.join(right.frame, on=list(self._on), **kwargs)
        else:
            assert self._left_on is not None and self._right_on is not None
            joined = left.frame.join(
                right.frame,
                left_on=list(self._left_on),
                right_on=list(self._right_on),
                **kwargs,
            )
        return left.with_frame(joined)

    def _validate_keys(
        self,
        on: str | Sequence[str] | None,
        left_on: str | Sequence[str] | None,
        right_on: str | Sequence[str] | None,
    ) -> None:
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError(
                "PolarsJoin: pass either on= or left_on/right_on, not both"
            )
        if on is None and (left_on is None or right_on is None):
            raise TypeError(
                "PolarsJoin: provide on= for matching columns, or both "
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
