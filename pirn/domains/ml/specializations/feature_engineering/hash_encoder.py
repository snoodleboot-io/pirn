"""``HashEncoder`` — hash categorical values into a fixed-size binary vector.

Implements the feature-hashing trick: each category is hashed into one
of ``n_components`` buckets. No vocabulary is required, making this
encoder safe for high-cardinality and out-of-vocabulary categories.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class HashEncoder(Knot):
    """Hash a categorical column into a fixed-size binary feature vector."""

    def __init__(
        self,
        *,
        split: Knot,
        categorical_column: str,
        n_components: int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError(
                "HashEncoder: categorical_column must be a non-empty string"
            )
        if not isinstance(n_components, int):
            raise TypeError("HashEncoder: n_components must be an int")
        if n_components < 1:
            raise ValueError("HashEncoder: n_components must be >= 1")
        self._categorical_column = categorical_column
        self._n_components = n_components
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def n_components(self) -> int:
        return self._n_components

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Apply hash encoding and append n_components hash feature names to every partition.

        Args:
            split: DataSplit whose partitions receive the new hash feature names.

        Returns:
            DataSplit with ``<column>_hash_<i>`` feature names added to every
            partition, and the original column removed from the feature list.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_hash_features(split.train, now),
            test=self._add_hash_features(split.test, now),
            validation=(
                self._add_hash_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_hash_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        existing = [
            f for f in dataset.feature_names if f != self._categorical_column
        ]
        hash_features = [
            f"{self._categorical_column}_hash_{i}"
            for i in range(self._n_components)
        ]
        return MLDataset(
            name=f"{dataset.name}:hash_encoded",
            feature_names=tuple(existing + hash_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
