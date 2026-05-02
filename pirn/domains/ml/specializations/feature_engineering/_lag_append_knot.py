"""``_LagAppendKnot`` — internal core knot used by
:class:`LagFeatureGenerator` to append lag-feature names to every
partition of a :class:`DataSplit`.

Single-underscore name marks this knot as a private composition
detail. The orchestration layer touches feature-name metadata only;
concrete subclasses materialise the row-level shifting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class _LagAppendKnot(Knot):
    """Append ``<column>_lag_<N>`` feature names to every partition."""

    def __init__(
        self,
        *,
        split: Knot,
        time_column: str,
        columns: Sequence[str],
        lags: Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._time_column = time_column
        self._columns = tuple(columns)
        self._lags = tuple(lags)
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_lag_features(split.train, now),
            test=self._add_lag_features(split.test, now),
            validation=(
                self._add_lag_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_lag_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        features = list(dataset.feature_names)
        for column in self._columns:
            for lag in self._lags:
                name = f"{column}_lag_{lag}"
                if name not in features:
                    features.append(name)
        return MLDataset(
            name=f"{dataset.name}:lagged",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
