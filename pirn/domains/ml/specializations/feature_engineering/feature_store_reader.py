"""``FeatureStoreReader`` — fetch features from a
:class:`FeatureStoreProvider` and join the feature names onto every
partition of a :class:`DataSplit`.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.specializations.feature_engineering._feature_store_reader_knot import (
    _FeatureStoreReaderKnot,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class FeatureStoreReader(SubTapestry):
    """Read features from a feature store; join names onto every partition."""

    def __init__(
        self,
        *,
        split: Knot,
        feature_store: FeatureStoreProvider,
        entity_keys: Sequence[str],
        feature_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("FeatureStoreReader: split must be a Knot")
        if not isinstance(feature_store, FeatureStoreProvider):
            raise TypeError(
                "FeatureStoreReader: feature_store must be a "
                "FeatureStoreProvider"
            )
        key_tuple = tuple(entity_keys)
        if not key_tuple:
            raise ValueError(
                "FeatureStoreReader: entity_keys must be non-empty"
            )
        for key in key_tuple:
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "FeatureStoreReader: every entity key must be a "
                    "non-empty string"
                )
        name_tuple = tuple(feature_names)
        if not name_tuple:
            raise ValueError(
                "FeatureStoreReader: feature_names must be non-empty"
            )
        for name in name_tuple:
            if not isinstance(name, str) or not name:
                raise ValueError(
                    "FeatureStoreReader: every feature name must be a "
                    "non-empty string"
                )
        self._feature_store = feature_store
        self._entity_keys = key_tuple
        self._feature_names = name_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            _FeatureStoreReaderKnot(
                split=split_node,
                feature_store=self._feature_store,
                entity_keys=self._entity_keys,
                feature_names=self._feature_names,
                _config=KnotConfig(id="read"),
            )
        result = await self._run_inner(inner)
        joined = result.outputs["read"]
        if not isinstance(joined, DataSplit):
            raise TypeError(
                "FeatureStoreReader: inner reader did not return a DataSplit"
            )
        return joined
