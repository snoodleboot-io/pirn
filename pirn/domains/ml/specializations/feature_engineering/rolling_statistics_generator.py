"""``RollingStatisticsGenerator`` — compute rolling statistics for time
series features over configurable windows.

Appends ``<column>_roll<window>_<stat>`` feature names for each
(column, window, statistic) combination. Supported statistics:
``mean``, ``std``, ``min``, ``max``.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``columns``, ``windows``, and
       ``statistics`` via process().
    2. Validate all inputs.
    3. Append rolling statistic feature names for each (column, window, stat).
    4. Return updated SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class RollingStatisticsGenerator(Knot):
    """Append rolling statistic feature names to a time-series SplitManifest."""

    valid_statistics: ClassVar[frozenset[str]] = frozenset({"mean", "std", "min", "max"})

    def __init__(
        self,
        *,
        split: Knot,
        columns: Knot | Sequence[str],
        windows: Knot | Sequence[int] = (7, 14),
        statistics: Knot | Sequence[str] = ("mean", "std"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            columns=columns,
            windows=windows,
            statistics=statistics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        columns: Sequence[str] = (),
        windows: Sequence[int] = (7, 14),
        statistics: Sequence[str] = ("mean", "std"),
        **_: Any,
    ) -> SplitManifest:
        """Append rolling statistic feature names for each (column, window, stat) combination.

        Args:
            split: SplitManifest whose partitions receive the rolling feature names.
            columns: Non-empty sequence of column names.
            windows: Non-empty sequence of window sizes; each must be an int >= 1.
            statistics: Non-empty sequence of statistic names from the valid set.

        Returns:
            SplitManifest with ``<column>_roll<window>_<stat>`` feature names appended.

        Raises:
            ValueError: If any input fails validation.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("RollingStatisticsGenerator: columns must be non-empty")
        for col in column_tuple:
            if not isinstance(col, str) or not col:
                raise ValueError(
                    "RollingStatisticsGenerator: every column name must be a non-empty string"
                )
        window_tuple = tuple(windows)
        if not window_tuple:
            raise ValueError("RollingStatisticsGenerator: windows must be non-empty")
        for w in window_tuple:
            if not isinstance(w, int):
                raise TypeError("RollingStatisticsGenerator: every window must be an int")
            if w < 1:
                raise ValueError("RollingStatisticsGenerator: every window must be >= 1")
        stat_tuple = tuple(statistics)
        if not stat_tuple:
            raise ValueError("RollingStatisticsGenerator: statistics must be non-empty")
        for stat in stat_tuple:
            if stat not in self.valid_statistics:
                raise ValueError(
                    f"RollingStatisticsGenerator: statistic {stat!r} must be "
                    f"one of {sorted(self.valid_statistics)}"
                )
        now = datetime.now(UTC)
        return SplitManifest(
            train=self._add_rolling_features(
                split.train, column_tuple, window_tuple, stat_tuple, now
            ),
            test=self._add_rolling_features(
                split.test, column_tuple, window_tuple, stat_tuple, now
            ),
            validation=(
                self._add_rolling_features(
                    split.validation, column_tuple, window_tuple, stat_tuple, now
                )
                if split.validation is not None
                else None
            ),
        )

    def _add_rolling_features(
        self,
        dataset: DatasetManifest,
        columns: tuple[str, ...],
        windows: tuple[int, ...],
        statistics: tuple[str, ...],
        fetched_at: datetime,
    ) -> DatasetManifest:
        features = list(dataset.feature_names)
        for col in columns:
            for window in windows:
                for stat in statistics:
                    name = f"{col}_roll{window}_{stat}"
                    if name not in features:
                        features.append(name)
        return DatasetManifest(
            name=f"{dataset.name}:rolling_stats",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
