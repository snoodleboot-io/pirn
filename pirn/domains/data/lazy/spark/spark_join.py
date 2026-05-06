"""``SparkJoin`` — Tier-3 binary join that extends the deferred plan
with ``left.join(right, on=..., how=...)``.

The join is fully deferred: Spark plans the join across partitions but
nothing is executed until the terminal sink materialises the plan.

Algorithm:
    1. Validate ``how`` against the allowed set.
    2. Cross join: reject any ``on`` / ``left_on`` / ``right_on`` keys
       and call ``left.crossJoin(right)``.
    3. Equi-join with ``on``: reject any ``left_on`` / ``right_on`` and
       call ``left.join(right, on=<resolved>, how=how)``.
    4. Asymmetric-key join: require both ``left_on`` and ``right_on``,
       build a boolean column condition, and call
       ``left.join(right, on=condition, how=how)``.
    5. Return the result wrapped in a new :class:`SparkDataFrame`.

    ```text
    if how == "cross":
        joined = left.crossJoin(right)
    elif on:
        joined = left.join(right, on=on, how=how)
    else:
        cond = left[left_on[0]] == right[right_on[0]] & ...
        joined = left.join(right, on=cond, how=how)
    return SparkDataFrame(frame=joined)
    ```

References:
    [1] PySpark — DataFrame.join:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.join.html
    [2] PySpark — DataFrame.crossJoin:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.crossJoin.html
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

    @staticmethod
    def _validate_columns(label: str, columns: str | Sequence[str] | None) -> None:
        if columns is None:
            return
        if isinstance(columns, str):
            IdentifierValidator.validate_column(f"SparkJoin: {label}", columns)
            return
        if not isinstance(columns, Sequence):
            raise TypeError(f"SparkJoin: {label} must be a string or sequence of strings")
        IdentifierValidator.validate_columns(f"SparkJoin: {label}", columns)

    @staticmethod
    def _sequence_length(columns: str | Sequence[str]) -> int:
        return 1 if isinstance(columns, str) else len(columns)

    async def process(
        self,
        left: Any,  # SparkDataFrame — pydantic can't schema pyspark types
        right: Any,
        on: Any,  # str | Sequence[str] | None
        left_on: Any,
        right_on: Any,
        how: str,
        **_: Any,
    ) -> SparkDataFrame:
        """Join the left and right deferred Spark frames on the configured keys.

        Returns the joined result as a new :class:`SparkDataFrame`.

        Args:
            left: The left-side SparkDataFrame.
            right: The right-side SparkDataFrame to join against.
            on: Shared column name(s) to join on.
            left_on: Left-side column name(s) when keys differ.
            right_on: Right-side column name(s) when keys differ.
            how: Join type (inner, left, right, outer, leftsemi, leftanti, cross).

        Returns:
            A new SparkDataFrame containing the joined deferred Spark plan.
        """
        if how not in self._allowed_how:
            raise ValueError(
                f"SparkJoin: how must be one of {list(self._allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if on is not None or left_on is not None or right_on is not None:
                raise TypeError("SparkJoin: cross join takes no on / left_on / right_on")
        else:
            if on is None and (left_on is None or right_on is None):
                raise TypeError("SparkJoin: must supply on=... OR both left_on= and right_on=")
            if on is not None and (left_on is not None or right_on is not None):
                raise TypeError("SparkJoin: on is mutually exclusive with left_on/right_on")
        self._validate_columns("on", on)
        self._validate_columns("left_on", left_on)
        self._validate_columns("right_on", right_on)
        if (
            left_on is not None
            and right_on is not None
            and self._sequence_length(left_on) != self._sequence_length(right_on)
        ):
            raise ValueError("SparkJoin: left_on and right_on must have the same length")
        left_frame = left.frame
        right_frame = right.frame
        if how == "cross":
            joined = left_frame.crossJoin(right_frame)
        elif on is not None:
            resolved_on = on if isinstance(on, str) else list(on)
            joined = left_frame.join(right_frame, on=resolved_on, how=how)
        else:
            assert left_on is not None and right_on is not None
            left_cols = [left_on] if isinstance(left_on, str) else list(left_on)
            right_cols = [right_on] if isinstance(right_on, str) else list(right_on)
            condition = left_frame[left_cols[0]] == right_frame[right_cols[0]]
            for lc, rc in zip(left_cols[1:], right_cols[1:], strict=True):
                condition = condition & (left_frame[lc] == right_frame[rc])
            joined = left_frame.join(right_frame, on=condition, how=how)
        return left.with_frame(joined)
