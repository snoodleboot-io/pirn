"""``_LagAppendKnot`` — internal core knot used by
:class:`LagFeatureGenerator` to append lag-feature names to every
partition of a :class:`DataSplit`.

Single-underscore name marks this knot as a private composition
detail. The orchestration layer touches feature-name metadata only;
concrete subclasses materialise the row-level shifting.

Algorithm:
    1. Receive ``split``, ``time_column``, ``columns``, and ``lags`` via process().
    2. Validate inputs.
    3. For each partition, append ``<column>_lag_<N>`` feature names.
    4. Return the extended DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

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
        time_column: Knot | str,
        columns: Knot | Sequence[str],
        lags: Knot | Sequence[int],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            time_column=time_column,
            columns=columns,
            lags=lags,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        time_column: str = "",
        columns: Sequence[str] = (),
        lags: Sequence[int] = (),
        **_: Any,
    ) -> DataSplit:
        """Append lag feature names for each configured (column, lag) pair to every partition and return the extended DataSplit.

        Args:
            split: DataSplit whose partitions receive the new lag feature names.
            time_column: Non-empty name of the time column (passed through for provenance).
            columns: Non-empty sequence of column names to lag.
            lags: Non-empty sequence of lag integers.

        Returns:
            DataSplit with ``<column>_lag_<N>`` feature names appended to every partition.

        Raises:
            ValueError: If time_column, columns, or lags are invalid.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError("_LagAppendKnot: time_column must be a non-empty string")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("_LagAppendKnot: columns must be non-empty")
        lag_tuple = tuple(lags)
        if not lag_tuple:
            raise ValueError("_LagAppendKnot: lags must be non-empty")
        now = datetime.now(UTC)
        return DataSplit(
            train=self._add_lag_features(split.train, column_tuple, lag_tuple, now),
            test=self._add_lag_features(split.test, column_tuple, lag_tuple, now),
            validation=(
                self._add_lag_features(split.validation, column_tuple, lag_tuple, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_lag_features(
        self,
        dataset: MLDataset,
        columns: tuple[str, ...],
        lags: tuple[int, ...],
        fetched_at: datetime,
    ) -> MLDataset:
        features = list(dataset.feature_names)
        for column in columns:
            for lag in lags:
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
