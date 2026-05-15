"""``FeatureStoreWriter`` — write computed features to a
:class:`FeatureStoreProvider`.

Wraps the core :class:`FeatureStore` knot. Returns the count of rows
written by the underlying provider.

Algorithm:
    1. Receive ``split`` (SplitManifest) and ``feature_store`` (FeatureStoreProvider) via process().
    2. Validate feature_store type.
    3. Wire FeatureStore in an inner Tapestry.
    4. Run via _run_inner() and return the count of rows written.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.features.feature_store import FeatureStore
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class FeatureStoreWriter(SubTapestry):
    """Persist a :class:`SplitManifest`'s feature metadata to a feature store."""

    def __init__(
        self,
        *,
        split: Knot,
        feature_store: Knot | FeatureStoreProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            feature_store=feature_store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        feature_store: FeatureStoreProvider | None = None,
        **_: Any,
    ) -> Any:
        """Write the SplitManifest's partition metadata to the feature store and return the count of rows written.

        Args:
            split: SplitManifest whose train, test, and optional validation partitions are written.
            feature_store: FeatureStoreProvider to write to.

        Returns:
            Number of rows written to the feature store provider.

        Raises:
            TypeError: If feature_store is not a FeatureStoreProvider or inner writer fails.
        """
        if not isinstance(split, SplitManifest):
            raise TypeError("FeatureStoreWriter: split must be a SplitManifest")
        if not isinstance(feature_store, FeatureStoreProvider):
            raise TypeError("FeatureStoreWriter: feature_store must be a FeatureStoreProvider")
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return FeatureStore(
            split=split_node,
            provider=feature_store,
            _config=KnotConfig(id="write"),
        )
