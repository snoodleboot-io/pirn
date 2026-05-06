"""``DatafusionJoin`` — Tier-2 binary join via
:meth:`datafusion.DataFrame.join`.

The caller supplies either:

* ``on=``: a column name (or sequence of names) shared by both sides, or
* ``left_on=`` / ``right_on=``: differently-named keys on the two sides.

Supports the standard DataFusion join strategies: ``inner``, ``left``,
``right``, ``full``, ``semi``, ``anti``.

When the two parents come from independent
:class:`datafusion.SessionContext` instances, DataFusion rebinds the right
frame's logical plan onto the left's context implicitly. Both batches'
provenance metadata is preserved on the left side.

Algorithm:
    1. Validate ``how`` and that exactly one of ``on`` or
       ``left_on`` / ``right_on`` is supplied.
    2. Coerce column names to ``tuple[str, ...]`` and validate identifiers.
    3. Dispatch to ``left.frame.join()`` with the appropriate key form.
    4. Return the result wrapped in a new :class:`DatafusionDataBatch`.

References:
    [1] Apache DataFusion Python — DataFrame.join:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.DataFrame.join
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class DatafusionJoin(Knot):
    """Binary join over two :class:`DatafusionDataBatch` parents."""

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
        left: DatafusionDataBatch,
        right: DatafusionDataBatch,
        on: str | Sequence[str] | None,
        left_on: str | Sequence[str] | None,
        right_on: str | Sequence[str] | None,
        how: str,
        **_: Any,
    ) -> DatafusionDataBatch:
        """Join the left and right DataFusion batches on the configured keys.

        Args:
            left: The left-side DatafusionDataBatch.
            right: The right-side DatafusionDataBatch.
            on: Shared column name(s), or None when using ``left_on``/``right_on``.
            left_on: Left-side key column(s) for differently-named keys.
            right_on: Right-side key column(s) for differently-named keys.
            how: Join strategy — one of ``inner``, ``left``, ``right``,
                ``full``, ``semi``, ``anti``.

        Returns:
            A new DatafusionDataBatch containing the joined result.
        """
        allowed_how = ("inner", "left", "right", "full", "semi", "anti")
        if how not in allowed_how:
            raise ValueError(f"DatafusionJoin: how must be one of {list(allowed_how)}, got {how!r}")
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError("DatafusionJoin: pass either on= or left_on/right_on, not both")
        if on is None and (left_on is None or right_on is None):
            if left_on is not None or right_on is not None:
                raise TypeError(
                    "DatafusionJoin: provide both left_on= and right_on= for differently-named keys"
                )
            raise TypeError(
                "DatafusionJoin: provide on=<column(s)> for matching keys, "
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
            raise ValueError("DatafusionJoin: left_on and right_on must have the same length")

        if norm_on is not None:
            joined = left.frame.join(right.frame, on=list(norm_on), how=how)
        else:
            assert norm_left_on is not None and norm_right_on is not None
            joined = left.frame.join(
                right.frame,
                how=how,
                left_on=list(norm_left_on),
                right_on=list(norm_right_on),
            )
        return left.with_frame(joined)

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
                f"DatafusionJoin: {label}= must be a column name or a sequence of column names"
            )
        IdentifierValidator.validate_columns(f"DatafusionJoin: {label}=", keys)
        return keys
