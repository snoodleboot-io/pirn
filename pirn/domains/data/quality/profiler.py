"""``Profiler`` — emits a :class:`DataProfile` describing the input
:class:`DataBatch`.

Not a pass/fail check. The profile is a side-channel observation that
audit, drift detection, and operator dashboards consume. To enforce a
threshold based on the profile, follow the profiler with a downstream
knot or use the dedicated quality gates (:class:`RowCountGate`,
:class:`NullRateGate`, …).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_profile import ColumnProfile, DataProfile


class Profiler(Knot):
    """Compute per-column descriptive statistics for a :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        columns: tuple[str, ...] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if columns is not None and not all(isinstance(c, str) for c in columns):
            raise TypeError("Profiler: columns must be a tuple of strings")
        self._columns = tuple(columns) if columns is not None else None
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def columns(self) -> tuple[str, ...] | None:
        return self._columns

    async def process(self, batch: DataBatch, **_: Any) -> DataProfile:
        """Compute per-column descriptive statistics for the batch and return a DataProfile.

        Args:
            batch: The DataBatch to profile.

        Returns:
            A DataProfile containing row count, column count, and per-column statistics.
        """
        target_columns = self._target_columns(batch)
        column_profiles = tuple(
            self._profile_column(batch, column) for column in target_columns
        )
        return DataProfile(
            row_count=batch.row_count,
            column_count=len(target_columns),
            columns=column_profiles,
        )

    def _target_columns(self, batch: DataBatch) -> tuple[str, ...]:
        if self._columns is not None:
            return self._columns
        # Default: every column declared on the batch's schema, with stable order.
        if batch.schema.column_names:
            return batch.schema.column_names
        # Fallback: union of keys observed across rows.
        seen: dict[str, None] = {}
        for row in batch.rows:
            for key in row.keys():
                seen.setdefault(key, None)
        return tuple(seen)

    def _profile_column(
        self, batch: DataBatch, column: str
    ) -> ColumnProfile:
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
        if non_null_values and self._is_orderable(non_null_values[0]):
            try:
                min_value = min(non_null_values)
                max_value = max(non_null_values)
            except TypeError:
                # Mixed types — surrender on min/max rather than crash.
                min_value = None
                max_value = None

        top_value: Any | None = None
        top_count = 0
        if non_null_values:
            counter = Counter(self._hashable(v) for v in non_null_values)
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
    def _is_orderable(value: Any) -> bool:
        return isinstance(value, (int, float, str, bool))

    @staticmethod
    def _hashable(value: Any) -> Any:
        # ``Counter`` requires hashable keys; collapse common unhashables.
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)
