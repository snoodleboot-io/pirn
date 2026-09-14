"""``Profiler`` — emits a :class:`DataProfile` describing the input
:class:`DataBatch`.

Not a pass/fail check. The profile is a side-channel observation that
audit, drift detection, and operator dashboards consume. To enforce a
threshold based on the profile, follow the profiler with a downstream
knot or use the dedicated quality gates (:class:`RowCountCheck`,
:class:`NullRateCheck`, …).

Algorithm:
    1. Resolve the target column list: use the caller-supplied ``columns``
       if provided; otherwise fall back to the batch's declared schema
       column names; otherwise union the keys observed across all rows.
    2. For each target column, scan ``batch.rows`` once and accumulate:

       - ``observed_count`` — rows where the column key is present.
       - ``null_count`` — present rows where the value is ``None``.
       - ``distinct_count`` — count of distinct non-null values.
       - ``min_value`` / ``max_value`` — for orderable scalar types
         (``int``, ``float``, ``str``, ``bool``).
       - ``top_value`` / ``top_value_count`` — most frequent non-null value.

    3. Return a :class:`DataProfile` containing row count, column count,
       and one :class:`ColumnProfile` per target column.

Math:
    Let :math:`R` be ``batch.rows`` and, for a target column :math:`c`,
    let :math:`P = \\{ r \\in R : c \\in r \\}` be the rows where the key is
    present:

    $$
    \\text{observed\\_count} = |P|
    $$

    $$
    \\text{null\\_count} = |\\{ r \\in P : r[c] = \\text{None} \\}|
    $$

    Let :math:`V = \\{ r[c] : r \\in P, r[c] \\neq \\text{None} \\}` be the
    multiset of non-null values:

    $$
    \\text{distinct\\_count} = |\\text{set}(V)|
    $$

    $$
    \\text{top\\_value} = \\underset{v \\in \\text{set}(V)}{\\arg\\max}\\ |\\{ x \\in V : x = v \\}|,
    \\qquad
    \\text{top\\_value\\_count} = \\max_{v \\in \\text{set}(V)} |\\{ x \\in V : x = v \\}|
    $$

    ``min_value``/``max_value`` are the ordinary minimum and maximum of
    :math:`V`, computed only when every element is one of ``int``,
    ``float``, ``str``, ``bool``; otherwise both are ``None``.

References:
    [1] Descriptive statistics for data profiling:
        Rahm & Do, "Data Cleaning: Problems and Current Approaches",
        IEEE Data Engineering Bulletin 23(4), 2000.
    [2] :class:`pirn_data.data_profile.DataProfile` and
        :class:`pirn_data.data_profile.ColumnProfile` — output
        value objects.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data._value_shape import (
    _ValueShape,  # pyright: ignore[reportPrivateUsage]  # package-internal helper
)
from pirn_data.data_batch import DataBatch
from pirn_data.data_profile import ColumnProfile, DataProfile


class Profiler(Knot):
    """Compute per-column descriptive statistics for a :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        columns: Knot | tuple[str, ...] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, columns=columns, _config=_config, **kwargs)

    async def process(
        self,
        *,
        batch: DataBatch,
        columns: Any = None,
        **_: Any,
    ) -> DataProfile:
        if columns is not None and (
            not _ValueShape.is_tuple(columns) or not all(isinstance(c, str) for c in columns)
        ):
            raise TypeError("Profiler: columns must be a tuple of strings")

        target_columns = Profiler._target_columns(batch, columns)
        column_profiles = tuple(
            Profiler._profile_column(batch, column) for column in target_columns
        )
        return DataProfile(
            row_count=batch.row_count,
            column_count=len(target_columns),
            columns=column_profiles,
        )

    @staticmethod
    def _target_columns(batch: DataBatch, columns: tuple[str, ...] | None) -> tuple[str, ...]:
        if columns is not None:
            return columns
        if batch.schema.column_names:
            return batch.schema.column_names
        seen: dict[str, None] = {}
        for row in batch.rows:
            for key in row.keys():
                seen.setdefault(key, None)
        return tuple(seen)

    @staticmethod
    def _profile_column(batch: DataBatch, column: str) -> ColumnProfile:
        observed = 0
        nulls = 0
        non_null_values: list[Any] = []

        for row in batch.rows:
            if column not in row:
                continue
            observed += 1
            value = row[column]
            if value is None:
                nulls += 1
                continue
            non_null_values.append(value)

        distinct_count = len(set(non_null_values))
        min_value: Any | None = None
        max_value: Any | None = None
        if non_null_values and isinstance(non_null_values[0], (int, float, str, bool)):
            try:
                min_value = min(non_null_values)
                max_value = max(non_null_values)
            except TypeError:
                min_value = None
                max_value = None

        top_value: Any | None = None
        top_count = 0
        if non_null_values:
            counter = Counter(Profiler._hashable(v) for v in non_null_values)
            top_value, top_count = counter.most_common(1)[0]

        return ColumnProfile(
            name=column,
            observed_count=observed,
            null_count=nulls,
            distinct_count=distinct_count,
            min_value=min_value,
            max_value=max_value,
            top_value=top_value,
            top_value_count=top_count,
        )

    @staticmethod
    def _hashable(value: Any) -> Any:
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
