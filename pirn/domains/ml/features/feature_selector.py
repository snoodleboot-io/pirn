"""``FeatureSelector`` — keep the top-K features in a :class:`DataSplit`.

The actual scoring is deferred to a later runtime phase. At this layer
the knot reduces the logical feature list and emits a renamed split so
downstream knots see a smaller feature schema.

Algorithm:
    1. Receive ``split`` (DataSplit), ``k`` (int >= 1), and ``method`` (str) via process().
    2. Validate k >= 1 and method is in valid_methods.
    3. Truncate each partition's feature_names list to the first k entries.
    4. Return the renamed DataSplit with the reduced feature schema.

Math:
    kept_features = feature_names[:k]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class FeatureSelector(Knot):
    """Truncate feature list to ``k`` entries via a stable scoring method."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"mutual_information", "variance", "rfe"})

    def __init__(
        self,
        *,
        split: Knot,
        k: Knot | int,
        method: Knot | str = "mutual_information",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(split=split, k=k, method=method, _config=_config, **kwargs)

    async def process(
        self,
        split: DataSplit,
        k: int,
        method: str = "mutual_information",
        **_: Any,
    ) -> DataSplit:
        """Truncate the feature list to the top k entries using the configured method and return the reduced DataSplit.

        Args:
            split: DataSplit whose feature lists are truncated to k entries.
            k: Number of features to keep; must be an int >= 1.
            method: Feature scoring method; must be one of ``valid_methods``.

        Returns:
            DataSplit with each partition's feature list capped at k features.

        Raises:
            TypeError: If k is not an int.
            ValueError: If k < 1 or method is invalid.
        """
        if not isinstance(k, int):
            raise TypeError("FeatureSelector: k must be an int")
        if k < 1:
            raise ValueError("FeatureSelector: k must be >= 1")
        if method not in self.valid_methods:
            raise ValueError(f"FeatureSelector: method must be one of {sorted(self.valid_methods)}")
        now = datetime.now(UTC)
        return DataSplit(
            train=self._reduce(split.train, k, method, now),
            test=self._reduce(split.test, k, method, now),
            validation=(
                self._reduce(split.validation, k, method, now)
                if split.validation is not None
                else None
            ),
        )

    def _reduce(self, dataset: MLDataset, k: int, method: str, fetched_at: datetime) -> MLDataset:
        kept = dataset.feature_names[:k]
        return MLDataset(
            name=f"{dataset.name}:selected_{method}",
            feature_names=kept,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
