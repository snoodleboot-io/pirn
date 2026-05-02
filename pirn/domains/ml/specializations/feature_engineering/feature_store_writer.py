"""``FeatureStoreWriter`` — write computed features to a
:class:`FeatureStoreProvider`.

Wraps the core :class:`FeatureStore` knot. Returns the count of rows
written by the underlying provider.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.features.feature_store import FeatureStore
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class FeatureStoreWriter(SubTapestry):
    """Persist a :class:`DataSplit`'s feature metadata to a feature store."""

    def __init__(
        self,
        *,
        split: Knot,
        feature_store: FeatureStoreProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("FeatureStoreWriter: split must be a Knot")
        if not isinstance(feature_store, FeatureStoreProvider):
            raise TypeError(
                "FeatureStoreWriter: feature_store must be a "
                "FeatureStoreProvider"
            )
        self._feature_store = feature_store
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> int:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            FeatureStore(
                split=split_node,
                provider=self._feature_store,
                _config=KnotConfig(id="write"),
            )
        result = await self._run_inner(inner)
        written = result.outputs["write"]
        if not isinstance(written, int):
            raise TypeError(
                "FeatureStoreWriter: inner writer did not return an int"
            )
        return written
