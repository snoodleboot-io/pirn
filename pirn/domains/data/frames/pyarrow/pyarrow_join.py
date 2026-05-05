"""``PyarrowJoin`` — Tier-2 binary join via :meth:`pyarrow.Table.join`.

The caller supplies either:

* ``on=``: a column name (or sequence of names) shared by both sides, or
* ``left_on=`` / ``right_on=``: differently-named keys on the two sides.

Supports the full set of PyArrow join strategies — ``inner``,
``left outer``, ``right outer``, ``full outer``, ``left semi``,
``right semi``, ``left anti``, ``right anti``. Both batches' provenance
metadata is preserved on the left side via :meth:`PyarrowDataBatch.with_table`.

Algorithm:
    1. Validate ``how`` against the allowed strategy set.
    2. Validate that exactly one of ``on`` or ``left_on`` / ``right_on`` is supplied.
    3. Coerce column names to ``tuple[str, ...]`` and validate each identifier.
    4. For shared keys: call ``left.table.join(right.table, keys=..., join_type=how)``.
    5. For differently-named keys: call with ``keys=left_on, right_keys=right_on``.
    6. Return the joined table wrapped in a new :class:`PyarrowDataBatch`.

References:
    [1] PyArrow — Table.join:
        https://arrow.apache.org/docs/python/generated/pyarrow.Table.html#pyarrow.Table.join
    [2] Alternative: DataFusion DataFrame.join (chosen PyArrow here for in-memory
        eager execution without a session context):
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.DataFrame.join
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class PyarrowJoin(Knot):
    """Binary join over two :class:`PyarrowDataBatch` parents."""

    _allowed_how: ClassVar[tuple[str, ...]] = (
        "inner",
        "left outer",
        "right outer",
        "full outer",
        "left semi",
        "right semi",
        "left anti",
        "right anti",
    )

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        on: Knot | str | Sequence[str] | None = None,
        left_on: Knot | str | Sequence[str] | None = None,
        right_on: Knot | str | Sequence[str] | None = None,
        how: Knot | str = "inner",
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
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        left: PyarrowDataBatch,
        right: PyarrowDataBatch,
        on: str | Sequence[str] | None,
        left_on: str | Sequence[str] | None,
        right_on: str | Sequence[str] | None,
        how: str,
        **_: Any,
    ) -> PyarrowDataBatch:
        """Join the left and right PyArrow tables on the configured keys.

        Args:
            left: The left-side PyarrowDataBatch.
            right: The right-side PyarrowDataBatch to join against.
            on: Shared column name(s), or None when using ``left_on``/``right_on``.
            left_on: Left-side key column(s) for differently-named keys.
            right_on: Right-side key column(s) for differently-named keys.
            how: Join strategy — one of the PyArrow join type strings.

        Returns:
            A new PyarrowDataBatch containing the joined table.
        """
        if how not in self._allowed_how:
            raise ValueError(
                f"PyarrowJoin: how must be one of {list(self._allowed_how)}, got {how!r}"
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

        norm_on = self._coerce_keys("on", on)
        norm_left_on = self._coerce_keys("left_on", left_on)
        norm_right_on = self._coerce_keys("right_on", right_on)

        if (
            norm_left_on is not None
            and norm_right_on is not None
            and len(norm_left_on) != len(norm_right_on)
        ):
            raise ValueError(
                "PyarrowJoin: left_on and right_on must have the same length"
            )

        if norm_on is not None:
            joined = left.table.join(
                right.table,
                keys=list(norm_on),
                join_type=how,
            )
        else:
            assert norm_left_on is not None and norm_right_on is not None
            joined = left.table.join(
                right.table,
                keys=list(norm_left_on),
                right_keys=list(norm_right_on),
                join_type=how,
            )
        return left.with_table(joined)

    @staticmethod
    def _coerce_keys(
        label: str,
        value: str | Sequence[str] | None,
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
        IdentifierValidator.validate_columns(f"PyarrowJoin: {label}=", keys)
        return keys
