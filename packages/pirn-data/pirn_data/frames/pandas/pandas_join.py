"""``PandasJoin`` — Tier-2 binary join via :meth:`pandas.DataFrame.merge`.

Mirrors the parameter shape of
:class:`pirn_data.frames.polars.polars_join.PolarsJoin` but uses
pandas's join vocabulary (``inner``, ``left``, ``right``, ``outer``,
``cross``). Pandas does not natively support ``semi`` or ``anti`` joins,
so those values are rejected in ``process()`` with a clear error message.

Algorithm:
    1. Validate ``how`` against allowed values; reject ``semi`` and ``anti``
       with an explanatory message.
    2. Normalise ``on``, ``left_on``, and ``right_on`` to ``tuple[str, ...]``
       via :meth:`_coerce_keys`.
    3. For cross joins, assert no key columns are provided.
    4. For other joins, validate that exactly one of ``on`` or
       ``(left_on, right_on)`` is provided via :meth:`_validate_keys`.
    5. Call ``left.frame.merge(right.frame, ...)`` with the resolved keys
       and the ``suffixes=("", suffix)`` convention for overlapping columns.
    6. Reset the integer index and return the result wrapped in a new
       :class:`PandasDataBatch`.

References:
    [1] pandas — DataFrame.merge:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html
    [2] Alternative: pandas DataFrame.join (index-based); chosen merge here
        for column-key joins consistent with the Polars/SQL convention:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.join.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasJoin(Knot):
    """Binary join over two :class:`PandasDataBatch` parents."""

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        on: Knot | str | Sequence[str] | None = None,
        left_on: Knot | str | Sequence[str] | None = None,
        right_on: Knot | str | Sequence[str] | None = None,
        how: Knot | str = "inner",
        suffix: Knot | str = "_right",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            left=left,
            right=right,
            on=on,
            left_on=left_on,
            right_on=right_on,
            how=how,
            suffix=suffix,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        left: PandasDataBatch,
        right: PandasDataBatch,
        on: Any,
        left_on: Any,
        right_on: Any,
        how: Any,
        suffix: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Merge the left and right Pandas batches on the configured keys and return the result.

        Args:
            left: The left-side PandasDataBatch.
            right: The right-side PandasDataBatch.
            on: Column(s) shared by both frames to join on, or None.
            left_on: Left-side key column(s), or None.
            right_on: Right-side key column(s), or None.
            how: Join strategy (inner/left/right/outer/cross).
            suffix: Suffix applied to overlapping right-side columns.

        Returns:
            A new PandasDataBatch containing the merged result.
        """
        allowed_how = ("inner", "left", "right", "outer", "cross")
        if how in ("semi", "anti"):
            raise ValueError(
                "PandasJoin: pandas does not natively support "
                f"{how!r} joins; use a filter/anti-pattern with isin() instead"
            )
        if how not in allowed_how:
            raise ValueError(f"PandasJoin: how must be one of {list(allowed_how)}, got {how!r}")
        on_coerced = self._coerce_keys(on)
        left_on_coerced = self._coerce_keys(left_on)
        right_on_coerced = self._coerce_keys(right_on)
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError("PandasJoin: cross join takes no on/left_on/right_on")
        else:
            self._validate_keys(on, left_on, right_on)
        suffixes = ("", suffix)
        if how == "cross":
            joined = left.frame.merge(right.frame, how="cross", suffixes=suffixes)
        elif on_coerced is not None:
            joined = left.frame.merge(
                right.frame,
                on=list(on_coerced),
                how=how,
                suffixes=suffixes,
            )
        else:
            assert left_on_coerced is not None and right_on_coerced is not None
            joined = left.frame.merge(
                right.frame,
                left_on=list(left_on_coerced),
                right_on=list(right_on_coerced),
                how=how,
                suffixes=suffixes,
            )
        return left.with_frame(joined.reset_index(drop=True))

    def _validate_keys(
        self,
        on: Any,
        left_on: Any,
        right_on: Any,
    ) -> None:
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError("PandasJoin: pass either on= or left_on/right_on, not both")
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
