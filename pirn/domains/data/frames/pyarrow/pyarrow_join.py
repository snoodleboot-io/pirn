"""``PyarrowJoin`` — Tier-2 binary join via :meth:`pyarrow.Table.join`.

The caller supplies either:

* ``on=``: a column name (or sequence of names) shared by both sides, or
* ``left_on=`` / ``right_on=``: differently-named keys on the two sides.

Supports the full set of PyArrow join strategies — ``inner``,
``left outer``, ``right outer``, ``full outer``, ``left semi``,
``right semi``, ``left anti``, ``right anti``. Both batches' provenance
metadata is preserved on the left side via :meth:`PyarrowDataBatch.with_table`.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowJoin(Knot):
    """Binary join over two :class:`PyarrowDataBatch` parents."""

    _ALLOWED_HOW: ClassVar[tuple[str, ...]] = (
        "inner",
        "left outer",
        "right outer",
        "full outer",
        "left semi",
        "right semi",
        "left anti",
        "right anti",
    )
    _IDENTIFIER_PATTERN: ClassVar[str] = r"^[A-Za-z_][A-Za-z0-9_]*$"

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
        if how not in self._ALLOWED_HOW:
            raise ValueError(
                f"PyarrowJoin: how must be one of {list(self._ALLOWED_HOW)}, got {how!r}"
            )
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError(
                "PyarrowJoin: pass either on= or left_on/right_on, not both"
            )
        if on is None and (left_on is None or right_on is None):
            if left_on is not None or right_on is not None:
                raise TypeError(
                    "PyarrowJoin: provide both left_on= and right_on= "
                    "for differently-named keys"
                )
            raise TypeError(
                "PyarrowJoin: provide on=<column(s)> for matching keys, "
                "or both left_on= and right_on= for differently-named keys"
            )
        identifier_re = re.compile(self._IDENTIFIER_PATTERN)
        self._on = self._coerce_keys("on", on, identifier_re)
        self._left_on = self._coerce_keys("left_on", left_on, identifier_re)
        self._right_on = self._coerce_keys("right_on", right_on, identifier_re)
        if (
            self._left_on is not None
            and self._right_on is not None
            and len(self._left_on) != len(self._right_on)
        ):
            raise ValueError(
                "PyarrowJoin: left_on and right_on must have the same length"
            )
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self,
        left: PyarrowDataBatch,
        right: PyarrowDataBatch,
        **_: Any,
    ) -> PyarrowDataBatch:
        if self._on is not None:
            joined = left.table.join(
                right.table,
                keys=list(self._on),
                join_type=self._how,
            )
        else:
            assert self._left_on is not None and self._right_on is not None
            joined = left.table.join(
                right.table,
                keys=list(self._left_on),
                right_keys=list(self._right_on),
                join_type=self._how,
            )
        return left.with_table(joined)

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
                f"PyarrowJoin: {label}= must be a column name or a sequence of column names"
            )
        if not keys:
            raise ValueError(f"PyarrowJoin: {label}= must be non-empty")
        for column in keys:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    f"PyarrowJoin: every column in {label}= must be a non-empty string"
                )
            if not identifier_re.match(column):
                raise ValueError(
                    f"PyarrowJoin: {label}= column {column!r} is not a plain identifier"
                )
        return keys
