"""``FourierFeatureGenerator`` — add sin/cos features for periodic time series.

Appends ``<column>_sin_<period>`` and ``<column>_cos_<period>`` feature names
for each (column, period) combination. Typical periods: hour-of-day (24),
day-of-week (7), month-of-year (12).

Algorithm:
    1. Receive ``split`` (SplitManifest), ``columns`` (Sequence[str]), and
       ``periods`` (Sequence[int]) via process().
    2. Validate columns and periods.
    3. For each (column, period) pair, append sin and cos feature names.
    4. Return updated SplitManifest.

Math:
    For column x and period P:
        x_sin_P = sin(2 * pi * x / P)
        x_cos_P = cos(2 * pi * x / P)

    Typical periods: 24 (hour-of-day), 7 (day-of-week), 12 (month-of-year).

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class FourierFeatureGenerator(Knot):
    """Append sin/cos Fourier feature names for periodic columns."""

    def __init__(
        self,
        *,
        split: Knot,
        columns: Knot | Sequence[str],
        periods: Knot | Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            columns=columns,
            periods=periods,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        columns: Sequence[str] = (),
        periods: Sequence[int] = (),
        **_: Any,
    ) -> SplitManifest:
        """Append sin/cos feature names for each (column, period) combination to every partition.

        Args:
            split: SplitManifest whose partitions receive the Fourier feature names.
            columns: Non-empty sequence of column names to generate features for.
            periods: Non-empty sequence of integer periods; each must be >= 2.

        Returns:
            SplitManifest with ``<column>_sin_<period>`` and ``<column>_cos_<period>``
            feature names appended to every partition.

        Raises:
            ValueError: If columns or periods are invalid.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("FourierFeatureGenerator: columns must be non-empty")
        for col in column_tuple:
            if not isinstance(col, str) or not col:
                raise ValueError(
                    "FourierFeatureGenerator: every column name must be a non-empty string"
                )
        period_tuple = tuple(periods)
        if not period_tuple:
            raise ValueError("FourierFeatureGenerator: periods must be non-empty")
        for period in period_tuple:
            if not isinstance(period, int):
                raise TypeError("FourierFeatureGenerator: every period must be an int")
            if period < 2:
                raise ValueError("FourierFeatureGenerator: every period must be >= 2")
        now = datetime.now(UTC)
        return SplitManifest(
            train=self._add_fourier_features(split.train, column_tuple, period_tuple, now),
            test=self._add_fourier_features(split.test, column_tuple, period_tuple, now),
            validation=(
                self._add_fourier_features(split.validation, column_tuple, period_tuple, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_fourier_features(
        self,
        dataset: DatasetManifest,
        columns: tuple[str, ...],
        periods: tuple[int, ...],
        fetched_at: datetime,
    ) -> DatasetManifest:
        features = list(dataset.feature_names)
        for col in columns:
            for period in periods:
                sin_name = f"{col}_sin_{period}"
                cos_name = f"{col}_cos_{period}"
                if sin_name not in features:
                    features.append(sin_name)
                if cos_name not in features:
                    features.append(cos_name)
        return DatasetManifest(
            name=f"{dataset.name}:fourier",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
