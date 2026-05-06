"""``PolarsJoin`` — Tier-2 binary join via :meth:`polars.DataFrame.join`.

This is the first transform that exists *only* at Tier 2 — joining
``tuple[dict, ...]`` row lists at Tier 1 would be O(n²) without
indexing, so we deliberately do not provide a Tier-1 implementation per
the ARD efficiency mandate.

Supports the standard Polars join strategies (``inner``, ``left``,
``right``, ``full``, ``semi``, ``anti``, ``cross``). When ``on`` is a
single string or sequence, both frames join on those columns. When
``left_on`` / ``right_on`` are supplied separately, they may differ.

Algorithm:
    1. Validate ``how`` against the allowed set.
    2. Normalise ``on``, ``left_on``, ``right_on`` to
       ``tuple[str, ...]`` via :meth:`_coerce_keys`, which also
       validates each column name via :class:`IdentifierValidator`.
    3. For cross joins, assert no key columns are provided.
    4. For other joins, validate that exactly one of ``on`` or
       ``(left_on, right_on)`` is provided via :meth:`_validate_keys`.
    5. Call ``left.frame.join(right.frame, ...)`` with the resolved
       keys, strategy, and suffix.
    6. Return the joined frame wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.join:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join.html
    [2] Polars — join strategies:
        https://docs.pola.rs/user-guide/transformations/joins/
    [3] Alternative: pandas DataFrame.merge (chosen Polars here for
        vectorised, lazy-compatible execution):
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class PolarsJoin(Knot):
    """Binary join over two :class:`PolarsDataBatch` parents."""

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
        left: PolarsDataBatch,
        right: PolarsDataBatch,
        on: Any,
        left_on: Any,
        right_on: Any,
        how: Any,
        suffix: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Join the left and right Polars batches on the configured keys and return the result.

        Args:
            left: The left-side PolarsDataBatch.
            right: The right-side PolarsDataBatch to join against.
            on: Column(s) shared by both frames, or None.
            left_on: Left-side key column(s), or None.
            right_on: Right-side key column(s), or None.
            how: Join strategy.
            suffix: Suffix applied to overlapping right-side columns.

        Returns:
            A new PolarsDataBatch containing the joined frame.
        """
        allowed_how = ("inner", "left", "right", "full", "semi", "anti", "cross")
        if how not in allowed_how:
            raise ValueError(f"PolarsJoin: how must be one of {list(allowed_how)}, got {how!r}")
        on_coerced = self._coerce_keys("on", on)
        left_on_coerced = self._coerce_keys("left_on", left_on)
        right_on_coerced = self._coerce_keys("right_on", right_on)
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError("PolarsJoin: cross join takes no on/left_on/right_on")
        else:
            self._validate_keys(on, left_on, right_on)
        join_kwargs: dict[str, Any] = {"how": how, "suffix": suffix}
        if how == "cross":
            joined = left.frame.join(right.frame, **join_kwargs)
        elif on_coerced is not None:
            joined = left.frame.join(right.frame, on=list(on_coerced), **join_kwargs)
        else:
            assert left_on_coerced is not None and right_on_coerced is not None
            joined = left.frame.join(
                right.frame,
                left_on=list(left_on_coerced),
                right_on=list(right_on_coerced),
                **join_kwargs,
            )
        return left.with_frame(joined)

    def _validate_keys(
        self,
        on: Any,
        left_on: Any,
        right_on: Any,
    ) -> None:
        if on is not None and (left_on is not None or right_on is not None):
            raise TypeError("PolarsJoin: pass either on= or left_on/right_on, not both")
        if on is None and (left_on is None or right_on is None):
            raise TypeError(
                "PolarsJoin: provide on= for matching columns, or both "
                "left_on= and right_on= for differently-named keys"
            )

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
                f"PolarsJoin: {label}= must be a column name or a sequence of column names"
            )
        IdentifierValidator.validate_columns(f"PolarsJoin: {label}=", keys)
        return keys
