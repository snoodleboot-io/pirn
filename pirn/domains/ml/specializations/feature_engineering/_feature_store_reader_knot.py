"""``_FeatureStoreReaderKnot`` — internal core knot that pulls feature
rows from a :class:`FeatureStoreProvider` keyed by entity primary keys
and joins the resulting feature names onto every partition of a
:class:`DataSplit`.

The orchestration layer issues a single ``get_features`` probe to the
provider so misconfigured stores fail loudly. Concrete subclasses
materialise the row-level join using the keys + feature names recorded
on the upstream :class:`MLDataset`.

Algorithm:
    1. Receive ``split``, ``feature_store``, ``entity_keys``, and
       ``feature_names`` via process().
    2. Validate inputs.
    3. Probe the feature store with a synthetic request.
    4. Append feature names to every partition and return the extended DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class _FeatureStoreReaderKnot(Knot):
    """Read features from a feature store and join names onto a split."""

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
        split: DataSplit,
        feature_store: FeatureStoreProvider | None = None,
        entity_keys: Sequence[str] = (),
        feature_names: Sequence[str] = (),
        **_: Any,
    ) -> DataSplit:
        """Probe the feature store, join the configured feature names onto each partition, and return the extended DataSplit.

        Args:
            split: DataSplit whose partitions receive the joined feature names.
            feature_store: FeatureStoreProvider to probe.
            entity_keys: Non-empty sequence of entity key names.
            feature_names: Non-empty sequence of feature names to join.

        Returns:
            DataSplit with the configured feature names appended to every partition's feature list.

        Raises:
            TypeError: If feature_store is not a FeatureStoreProvider.
            ValueError: If entity_keys or feature_names are empty.
        """
        if not isinstance(feature_store, FeatureStoreProvider):
            raise TypeError(
                "_FeatureStoreReaderKnot: feature_store must be a FeatureStoreProvider"
            )
        entity_key_tuple = tuple(entity_keys)
        if not entity_key_tuple:
            raise ValueError("_FeatureStoreReaderKnot: entity_keys must be non-empty")
        feature_name_tuple = tuple(feature_names)
        if not feature_name_tuple:
            raise ValueError("_FeatureStoreReaderKnot: feature_names must be non-empty")
        # Probe the store with a synthetic single-key request so misconfigured
        # providers fail loudly at run time.
        probe_keys = [{key: "" for key in entity_key_tuple}]
        await feature_store.get_features(probe_keys, feature_name_tuple)
        now = datetime.now(UTC)
        return DataSplit(
            train=self._extend(split.train, feature_name_tuple, now),
            test=self._extend(split.test, feature_name_tuple, now),
            validation=(
                self._extend(split.validation, feature_name_tuple, now)
                if split.validation is not None
                else None
            ),
        )

    def _extend(
        self,
        dataset: MLDataset,
        feature_names: tuple[str, ...],
        fetched_at: datetime,
    ) -> MLDataset:
        existing = list(dataset.feature_names)
        for name in feature_names:
            if name not in existing:
                existing.append(name)
        return MLDataset(
            name=f"{dataset.name}:fs_joined",
            feature_names=tuple(existing),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
