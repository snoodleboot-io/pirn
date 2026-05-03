"""``FourierFeatureGenerator`` — add sin/cos features for periodic time series.

Appends ``<column>_sin_<period>`` and ``<column>_cos_<period>`` feature names
for each (column, period) combination. Typical periods: hour-of-day (24),
day-of-week (7), month-of-year (12).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class FourierFeatureGenerator(Knot):
    """Append sin/cos Fourier feature names for periodic columns."""

    def __init__(
        self,
        *,
        split: Knot,
        columns: Sequence[str],
        periods: Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("FourierFeatureGenerator: split must be a Knot")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError(
                "FourierFeatureGenerator: columns must be non-empty"
            )
        for col in column_tuple:
            if not isinstance(col, str) or not col:
                raise ValueError(
                    "FourierFeatureGenerator: every column name must be a "
                    "non-empty string"
                )
        period_tuple = tuple(periods)
        if not period_tuple:
            raise ValueError(
                "FourierFeatureGenerator: periods must be non-empty"
            )
        for period in period_tuple:
            if not isinstance(period, int):
                raise TypeError(
                    "FourierFeatureGenerator: every period must be an int"
                )
            if period < 2:
                raise ValueError(
                    "FourierFeatureGenerator: every period must be >= 2"
                )
        self._columns = column_tuple
        self._periods = period_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Append sin/cos feature names for each (column, period) combination to every partition.

        Args:
            split: DataSplit whose partitions receive the Fourier feature names.

        Returns:
            DataSplit with ``<column>_sin_<period>`` and ``<column>_cos_<period>``
            feature names appended to every partition.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_fourier_features(split.train, now),
            test=self._add_fourier_features(split.test, now),
            validation=(
                self._add_fourier_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_fourier_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        features = list(dataset.feature_names)
        for col in self._columns:
            for period in self._periods:
                sin_name = f"{col}_sin_{period}"
                cos_name = f"{col}_cos_{period}"
                if sin_name not in features:
                    features.append(sin_name)
                if cos_name not in features:
                    features.append(cos_name)
        return MLDataset(
            name=f"{dataset.name}:fourier",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
