"""``HashEncoder`` — hash categorical values into a fixed-size binary vector.

Implements the feature-hashing trick: each category is hashed into one
of ``n_components`` buckets. No vocabulary is required, making this
encoder safe for high-cardinality and out-of-vocabulary categories.

Algorithm:
    1. Receive ``split`` (DataSplit), ``categorical_column`` (str), and
       ``n_components`` (int) via process().
    2. Validate categorical_column and n_components.
    3. Remove the original column and append n_components hash feature names.
    4. Return updated DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
        categorical_column: Knot | str,
        n_components: Knot | int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            categorical_column=categorical_column,
            n_components=n_components,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        categorical_column: str = "",
        n_components: int = 8,
        **_: Any,
    ) -> DataSplit:
        """Apply hash encoding and append n_components hash feature names to every partition.

        Args:
            split: DataSplit whose partitions receive the new hash feature names.
            categorical_column: Non-empty name of the categorical column to encode.
            n_components: Number of hash buckets; must be an int >= 1.

        Returns:
            DataSplit with ``<column>_hash_<i>`` feature names added to every
            partition, and the original column removed from the feature list.

        Raises:
            ValueError: If categorical_column is empty or n_components < 1.
        """
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError("HashEncoder: categorical_column must be a non-empty string")
        if not isinstance(n_components, int):
            raise TypeError("HashEncoder: n_components must be an int")
        if n_components < 1:
            raise ValueError("HashEncoder: n_components must be >= 1")
        now = datetime.now(UTC)
        return DataSplit(
            train=self._add_hash_features(split.train, categorical_column, n_components, now),
            test=self._add_hash_features(split.test, categorical_column, n_components, now),
            validation=(
                self._add_hash_features(split.validation, categorical_column, n_components, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_hash_features(
        self,
        dataset: MLDataset,
        categorical_column: str,
        n_components: int,
        fetched_at: datetime,
    ) -> MLDataset:
        existing = [f for f in dataset.feature_names if f != categorical_column]
        hash_features = [f"{categorical_column}_hash_{i}" for i in range(n_components)]
        return MLDataset(
            name=f"{dataset.name}:hash_encoded",
            feature_names=tuple(existing + hash_features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
