"""``SparkJoin`` — Tier-3 binary join that extends the deferred plan
with ``left.join(right, on=..., how=...)``.

The join is fully deferred: Spark plans the join across partitions but
nothing is executed until the terminal sink materialises the plan.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


class SparkJoin(Knot):
    """Binary join over two :class:`SparkDataFrame` parents."""

    _allowed_how: ClassVar[tuple[str, ...]] = (
        "inner",
        "left",
        "right",
        "outer",
        "leftsemi",
        "leftanti",
        "cross",
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
        try:
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkJoin requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if how not in self._allowed_how:
            raise ValueError(
                f"SparkJoin: how must be one of {list(self._allowed_how)}, "
                f"got {how!r}"
            )
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError(
                    "SparkJoin: cross join takes no on / left_on / right_on"
                )
        else:
            if on is None and (left_on is None or right_on is None):
                raise TypeError(
                    "SparkJoin: must supply on=... OR both left_on= and right_on="
                )
            if on is not None and (left_on is not None or right_on is not None):
                raise TypeError(
                    "SparkJoin: on is mutually exclusive with left_on/right_on"
                )
        self._validate_columns("on", on)
        self._validate_columns("left_on", left_on)
        self._validate_columns("right_on", right_on)
        if (
            left_on is not None
            and right_on is not None
            and self._sequence_length(left_on) != self._sequence_length(right_on)
        ):
            raise ValueError(
                "SparkJoin: left_on and right_on must have the same length"
            )
        self._on = on
        self._left_on = left_on
        self._right_on = right_on
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @staticmethod
    def _validate_columns(
        label: str, columns: str | Sequence[str] | None
    ) -> None:
        if columns is None:
            return
        if isinstance(columns, str):
            IdentifierValidator.validate_column(f"SparkJoin: {label}", columns)
            return
        if not isinstance(columns, Sequence):
            raise TypeError(
                f"SparkJoin: {label} must be a string or sequence of strings"
            )
        IdentifierValidator.validate_columns(f"SparkJoin: {label}", columns)

    @staticmethod
    def _sequence_length(columns: str | Sequence[str]) -> int:
        return 1 if isinstance(columns, str) else len(columns)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: SparkDataFrame, right: SparkDataFrame, **_: Any
    ) -> SparkDataFrame:
        """Join the left and right deferred Spark frames on the configured keys and return the result.

        Args:
            left: The left-side SparkDataFrame.
            right: The right-side SparkDataFrame to join against.

        Returns:
            A new SparkDataFrame containing the joined deferred Spark plan.
        """
        left_frame = left.frame
        right_frame = right.frame
        if self._how == "cross":
            joined = left_frame.crossJoin(right_frame)
        elif self._on is not None:
            on = self._on if isinstance(self._on, str) else list(self._on)
            joined = left_frame.join(right_frame, on=on, how=self._how)
        else:
            assert self._left_on is not None and self._right_on is not None
            left_cols = (
                [self._left_on]
                if isinstance(self._left_on, str)
                else list(self._left_on)
            )
            right_cols = (
                [self._right_on]
                if isinstance(self._right_on, str)
                else list(self._right_on)
            )
            condition = left_frame[left_cols[0]] == right_frame[right_cols[0]]
            for left_col, right_col in zip(
                left_cols[1:], right_cols[1:], strict=True
            ):
                condition = condition & (
                    left_frame[left_col] == right_frame[right_col]
                )
            joined = left_frame.join(right_frame, on=condition, how=self._how)
        return left.with_frame(joined)
