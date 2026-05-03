"""``FeatureStore`` — write feature rows from a :class:`DataSplit` to a
:class:`FeatureStoreProvider`.

The knot writes one summary row per partition (train / validation /
test) using the partition's metadata. Concrete provider implementations
that need full row payloads should subclass and override the row
generation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class FeatureStore(Knot):
    """Persist a :class:`DataSplit`'s feature metadata to a feature store."""

    def __init__(
        self,
        *,
        split: Knot,
        provider: FeatureStoreProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(provider, FeatureStoreProvider):
            raise TypeError(
                "FeatureStore: provider must be a FeatureStoreProvider"
            )
        self._provider = provider
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> int:
        """Write partition metadata rows from the DataSplit to the feature store provider and return the write count.

        Args:
            split: DataSplit whose train, test, and optional validation partitions are written.

        Returns:
            Number of rows written to the feature store provider.
        """
        rows: list[dict[str, Any]] = []
        rows.append(self._row(split.train, "train"))
        if split.validation is not None:
            rows.append(self._row(split.validation, "validation"))
        rows.append(self._row(split.test, "test"))
        return await self._provider.write_features(rows)

    def _row(self, dataset: MLDataset, partition: str) -> dict[str, Any]:
        return {
            "partition": partition,
            "dataset_name": dataset.name,
            "feature_names": list(dataset.feature_names),
            "target_name": dataset.target_name,
            "row_count": dataset.row_count,
            "source_uri": dataset.source_uri,
        }
