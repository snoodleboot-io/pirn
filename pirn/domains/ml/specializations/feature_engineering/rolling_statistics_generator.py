"""``RollingStatisticsGenerator`` — compute rolling statistics for time
series features over configurable windows.

Appends ``<column>_roll<window>_<stat>`` feature names for each
(column, window, statistic) combination. Supported statistics:
``mean``, ``std``, ``min``, ``max``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class RollingStatisticsGenerator(Knot):
    """Append rolling statistic feature names to a time-series DataSplit."""

    valid_statistics: ClassVar[frozenset[str]] = frozenset(
        {"mean", "std", "min", "max"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        columns: Sequence[str],
        windows: Sequence[int] = (7, 14),
        statistics: Sequence[str] = ("mean", "std"),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError(
                "RollingStatisticsGenerator: split must be a Knot"
            )
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError(
                "RollingStatisticsGenerator: columns must be non-empty"
            )
        for col in column_tuple:
            if not isinstance(col, str) or not col:
                raise ValueError(
                    "RollingStatisticsGenerator: every column name must be a "
                    "non-empty string"
                )
        window_tuple = tuple(windows)
        if not window_tuple:
            raise ValueError(
                "RollingStatisticsGenerator: windows must be non-empty"
            )
        for w in window_tuple:
            if not isinstance(w, int):
                raise TypeError(
                    "RollingStatisticsGenerator: every window must be an int"
                )
            if w < 1:
                raise ValueError(
                    "RollingStatisticsGenerator: every window must be >= 1"
                )
        stat_tuple = tuple(statistics)
        if not stat_tuple:
            raise ValueError(
                "RollingStatisticsGenerator: statistics must be non-empty"
            )
        for stat in stat_tuple:
            if stat not in self.valid_statistics:
                raise ValueError(
                    f"RollingStatisticsGenerator: statistic {stat!r} must be "
                    f"one of {sorted(self.valid_statistics)}"
                )
        self._columns = column_tuple
        self._windows = window_tuple
        self._statistics = stat_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Append rolling statistic feature names for each (column, window, stat) combination.

        Args:
            split: DataSplit whose partitions receive the rolling feature names.

        Returns:
            DataSplit with ``<column>_roll<window>_<stat>`` feature names appended.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_rolling_features(split.train, now),
            test=self._add_rolling_features(split.test, now),
            validation=(
                self._add_rolling_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_rolling_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        features = list(dataset.feature_names)
        for col in self._columns:
            for window in self._windows:
                for stat in self._statistics:
                    name = f"{col}_roll{window}_{stat}"
                    if name not in features:
                        features.append(name)
        return MLDataset(
            name=f"{dataset.name}:rolling_stats",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
