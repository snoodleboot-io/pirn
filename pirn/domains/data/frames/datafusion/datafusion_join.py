"""``DatafusionJoin`` — Tier-2 binary join via
:meth:`datafusion.DataFrame.join`.

The caller supplies either:

* ``on=``: a column name (or sequence of names) shared by both sides, or
* ``left_on=`` / ``right_on=``: differently-named keys on the two sides.

Supports the standard DataFusion join strategies: ``inner``, ``left``,
``right``, ``full``, ``semi``, ``anti``.

When the two parents come from independent
:class:`datafusion.SessionContext` instances, DataFusion is happy to
execute the join — the right frame's logical plan is rebound onto the
left's context implicitly. Both batches' provenance metadata is
preserved on the left side.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class DatafusionJoin(Knot):
    """Binary join over two :class:`DatafusionDataBatch` parents."""

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        how: str = "inner",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed_how = ("inner", "left", "right", "full", "semi", "anti")
        if how not in allowed_how:
            raise ValueError(
                f"DatafusionJoin: how must be one of {list(allowed_how)}, got {how!r}"
            )
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError(
                "DatafusionJoin: pass either on= or left_on/right_on, not both"
            )
        if on is None and (left_on is None or right_on is None):
            if left_on is not None or right_on is not None:
                raise TypeError(
                    "DatafusionJoin: provide both left_on= and right_on= "
                    "for differently-named keys"
                )
            raise TypeError(
                "DatafusionJoin: provide on=<column(s)> for matching keys, "
                "or both left_on= and right_on= for differently-named keys"
            )
        identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        self._on = self._coerce_keys("on", on, identifier_re)
        self._left_on = self._coerce_keys("left_on", left_on, identifier_re)
        self._right_on = self._coerce_keys("right_on", right_on, identifier_re)
        if (
            self._left_on is not None
            and self._right_on is not None
            and len(self._left_on) != len(self._right_on)
        ):
            raise ValueError(
                "DatafusionJoin: left_on and right_on must have the same length"
            )
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: DatafusionDataBatch, right: DatafusionDataBatch, **_: Any
    ) -> DatafusionDataBatch:
        if self._on is not None:
            joined = left.frame.join(
                right.frame, on=list(self._on), how=self._how
            )
        else:
            assert self._left_on is not None and self._right_on is not None
            joined = left.frame.join(
                right.frame,
                how=self._how,
                left_on=list(self._left_on),
                right_on=list(self._right_on),
            )
        return left.with_frame(joined)

    @staticmethod
    def _coerce_keys(
        label: str,
        value: str | Sequence[str] | None,
        identifier_re: re.Pattern[str],
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, str):
            keys: tuple[str, ...] = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, bytes):
            keys = tuple(value)
        else:
            raise TypeError(
                f"DatafusionJoin: {label}= must be a column name or a sequence of column names"
            )
        if not keys:
            raise ValueError(f"DatafusionJoin: {label}= must be non-empty")
        for column in keys:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    f"DatafusionJoin: every column in {label}= must be a non-empty string"
                )
            if not identifier_re.match(column):
                raise ValueError(
                    f"DatafusionJoin: {label}= column {column!r} is not a plain identifier"
                )
        return keys
