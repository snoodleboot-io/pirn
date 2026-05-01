"""``DaskJoin`` — Tier-3 binary join that extends the deferred graph
with ``left.merge(right, on=..., how=...)``.

The merge is fully deferred: Dask plans the join across partitions but
nothing is executed until the terminal sink calls ``.compute()``.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskJoin(Knot):
    """Binary merge over two :class:`DaskDataFrame` parents."""

    _ALLOWED_HOW: tuple[str, ...] = (
        "inner", "left", "right", "outer", "cross",
    )

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        _config: KnotConfig,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        how: str = "inner",
        **kwargs: Any,
    ) -> None:
        if how not in self._ALLOWED_HOW:
            raise ValueError(
                f"DaskJoin: how must be one of {list(self._ALLOWED_HOW)}, "
                f"got {how!r}"
            )
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError(
                    "DaskJoin: cross join takes no on / left_on / right_on"
                )
        else:
            if on is None and (left_on is None or right_on is None):
                raise TypeError(
                    "DaskJoin: must supply on=... OR both left_on= and right_on="
                )
            if on is not None and (left_on is not None or right_on is not None):
                raise TypeError(
                    "DaskJoin: on is mutually exclusive with left_on/right_on"
                )
        self._on = on
        self._left_on = left_on
        self._right_on = right_on
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: DaskDataFrame, right: DaskDataFrame, **_: Any
    ) -> DaskDataFrame:
        if self._how == "cross":
            joined = left.frame.merge(right.frame, how="cross")
        elif self._on is not None:
            on = self._on if isinstance(self._on, str) else list(self._on)
            joined = left.frame.merge(right.frame, on=on, how=self._how)
        else:
            assert self._left_on is not None and self._right_on is not None
            left_on = (
                self._left_on if isinstance(self._left_on, str)
                else list(self._left_on)
            )
            right_on = (
                self._right_on if isinstance(self._right_on, str)
                else list(self._right_on)
            )
            joined = left.frame.merge(
                right.frame, left_on=left_on, right_on=right_on, how=self._how,
            )
        return left.with_frame(joined)
