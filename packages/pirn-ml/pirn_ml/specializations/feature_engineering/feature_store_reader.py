"""``FeatureStoreReader`` — fetch features from a
:class:`FeatureStoreProvider` and join the feature names onto every
partition of a :class:`SplitManifest`.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``feature_store`` (FeatureStoreProvider),
       ``entity_keys`` (Sequence[str]), and ``feature_names`` (Sequence[str]) via process().
    2. Validate all sequence inputs.
    3. Wire _FeatureStoreReaderKnot in an inner Tapestry.
    4. Run via _run_inner() and return the extended SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.feature_store_provider import FeatureStoreProvider
from pirn_ml.specializations.feature_engineering._feature_store_reader_knot import (
    _FeatureStoreReaderKnot,
)
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


class FeatureStoreReader(SubTapestry):
    """Read features from a feature store; join names onto every partition."""

    def __init__(
        self,
        *,
        split: Knot,
        feature_store: Knot | FeatureStoreProvider,
        entity_keys: Knot | Sequence[str],
        feature_names: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            feature_store=feature_store,
            entity_keys=entity_keys,
            feature_names=feature_names,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        feature_store: FeatureStoreProvider | None = None,
        entity_keys: Sequence[str] = (),
        feature_names: Sequence[str] = (),
        **_: Any,
    ) -> Any:
        """Fetch features from the store, join them onto each partition of the split, and return the extended SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the joined feature names.
            feature_store: FeatureStoreProvider to read from.
            entity_keys: Non-empty sequence of entity key column names.
            feature_names: Non-empty sequence of feature names to fetch.

        Returns:
            SplitManifest with the configured feature names appended to every partition.

        Raises:
            TypeError: If feature_store is not a FeatureStoreProvider or inner reader fails.
            ValueError: If entity_keys or feature_names are empty or contain invalid names.
        """
        if not isinstance(feature_store, FeatureStoreProvider):
            raise TypeError("FeatureStoreReader: feature_store must be a FeatureStoreProvider")
        key_tuple = tuple(entity_keys)
        if not key_tuple:
            raise ValueError("FeatureStoreReader: entity_keys must be non-empty")
        for key in key_tuple:
            if not isinstance(key, str) or not key:
                raise ValueError("FeatureStoreReader: every entity key must be a non-empty string")
        name_tuple = tuple(feature_names)
        if not name_tuple:
            raise ValueError("FeatureStoreReader: feature_names must be non-empty")
        for name in name_tuple:
            if not isinstance(name, str) or not name:
                raise ValueError(
                    "FeatureStoreReader: every feature name must be a non-empty string"
                )
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return _FeatureStoreReaderKnot(
            split=split_node,
            feature_store=feature_store,
            entity_keys=key_tuple,
            feature_names=name_tuple,
            _config=KnotConfig(id="read"),
        )
