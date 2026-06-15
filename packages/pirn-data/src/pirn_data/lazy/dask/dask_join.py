"""``DaskJoin`` — Tier-3 binary join that extends the deferred graph
with ``left.merge(right, on=..., how=...)``.

The merge is fully deferred: Dask plans the join across partitions but
nothing is executed until the terminal sink calls ``.compute()``.

Algorithm:
    1. Validate that ``how`` is one of the allowed join types.
    2. If ``how == "cross"``: validate that no key columns are supplied,
       then call ``left.merge(right, how="cross")``.
    3. Otherwise: validate that either ``on`` or both ``left_on`` and
       ``right_on`` are supplied (mutually exclusive).
    4. Call ``left.merge(right, on=..., how=...)`` with the resolved keys.
    5. Return a new ``DaskDataFrame`` wrapping the merged deferred graph.

    ```text
    if how == "cross":
        out = left.merge(right, how="cross")
    elif on:
        out = left.merge(right, on=on, how=how)
    else:
        out = left.merge(right, left_on=left_on, right_on=right_on, how=how)
    return DaskDataFrame(out)
    ```

References:
    [1] Dask DataFrame.merge — deferred binary join:
        https://docs.dask.org/en/stable/generated/dask.dataframe.DataFrame.merge.html
    [2] pandas DataFrame.merge — underlying merge semantics:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskJoin(Knot):
    """Binary merge over two :class:`DaskDataFrame` parents."""

    _allowed_how: tuple[str, ...] = (
        "inner",
        "left",
        "right",
        "outer",
        "cross",
    )

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        _config: KnotConfig,
        on: Knot | str | Sequence[str] | None = None,
        left_on: Knot | str | Sequence[str] | None = None,
        right_on: Knot | str | Sequence[str] | None = None,
        how: Knot | str = "inner",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            left=left,
            right=right,
            on=on,
            left_on=left_on,
            right_on=right_on,
            how=how,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        left: DaskDataFrame,
        right: DaskDataFrame,
        on: Any,
        left_on: Any,
        right_on: Any,
        how: Any,
        **_: Any,
    ) -> DaskDataFrame:
        """Merge the left and right deferred Dask frames on the configured keys.

        Args:
            left: The left-side DaskDataFrame.
            right: The right-side DaskDataFrame to merge against.
            on: Column name(s) common to both sides, or None.
            left_on: Left-side key column(s), or None.
            right_on: Right-side key column(s), or None.
            how: Join type — inner/left/right/outer/cross.

        Returns:
            A new DaskDataFrame containing the merged deferred graph.
        """
        if how not in self._allowed_how:
            raise ValueError(f"DaskJoin: how must be one of {list(self._allowed_how)}, got {how!r}")
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError("DaskJoin: cross join takes no on / left_on / right_on")
            joined = left.frame.merge(right.frame, how="cross")
        else:
            if on is None and (left_on is None or right_on is None):
                raise TypeError("DaskJoin: must supply on=... OR both left_on= and right_on=")
            if on is not None and (left_on is not None or right_on is not None):
                raise TypeError("DaskJoin: on is mutually exclusive with left_on/right_on")
            if on is not None:
                resolved_on = on if isinstance(on, str) else list(on)
                joined = left.frame.merge(right.frame, on=resolved_on, how=how)
            else:
                assert left_on is not None and right_on is not None
                resolved_left_on = left_on if isinstance(left_on, str) else list(left_on)
                resolved_right_on = right_on if isinstance(right_on, str) else list(right_on)
                joined = left.frame.merge(
                    right.frame,
                    left_on=resolved_left_on,
                    right_on=resolved_right_on,
                    how=how,
                )
        return left.with_frame(joined)
