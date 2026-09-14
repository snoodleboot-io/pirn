"""``FeatureStore`` — write feature rows from a :class:`SplitManifest` to a
:class:`FeatureStoreProvider`.

The knot writes one summary row per partition (train / validation /
test) using the partition's metadata. Concrete provider implementations
that need full row payloads should subclass and override the row
generation.

Algorithm:
    1. Receive ``split`` (SplitManifest) and ``provider`` (FeatureStoreProvider) via process().
    2. Build one metadata row dict per partition (train, optional validation, test).
    3. Call provider.write_features(rows) and return the write count.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.feature_store_provider import FeatureStoreProvider
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class FeatureStore(Knot):
    """Persist a :class:`SplitManifest`'s feature metadata to a feature store."""

    def __init__(
        self,
        *,
        split: Knot,
        provider: Knot | FeatureStoreProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(split=split, provider=provider, _config=_config, **kwargs)

    async def process(self, split: SplitManifest, provider: FeatureStoreProvider, **_: Any) -> int:
        """Write partition metadata rows from the SplitManifest to the feature store provider and return the write count.

        Args:
            split: SplitManifest whose train, test, and optional validation partitions are written.
            provider: FeatureStoreProvider used to persist the partition metadata rows.

        Returns:
            Number of rows written to the feature store provider.
        """
        if not isinstance(provider, FeatureStoreProvider):
            raise TypeError("FeatureStore: provider must be a FeatureStoreProvider")
        rows: list[dict[str, Any]] = []
        rows.append(self._row(split.train, "train"))
        if split.validation is not None:
            rows.append(self._row(split.validation, "validation"))
        rows.append(self._row(split.test, "test"))
        return await provider.write_features(rows)

    def _row(self, dataset: DatasetManifest, partition: str) -> dict[str, Any]:
        return {
            "partition": partition,
            "dataset_name": dataset.name,
            "feature_names": list(dataset.feature_names),
            "target_name": dataset.target_name,
            "row_count": dataset.row_count,
            "source_uri": dataset.source_uri,
        }
