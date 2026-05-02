"""``_FeatureStoreReaderKnot`` — internal core knot that pulls feature
rows from a :class:`FeatureStoreProvider` keyed by entity primary keys
and joins the resulting feature names onto every partition of a
:class:`DataSplit`.

The orchestration layer issues a single ``get_features`` probe to the
provider so misconfigured stores fail loudly. Concrete subclasses
materialise the row-level join using the keys + feature names recorded
on the upstream :class:`MLDataset`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

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
        feature_store: FeatureStoreProvider,
        entity_keys: Sequence[str],
        feature_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._feature_store = feature_store
        self._entity_keys = tuple(entity_keys)
        self._feature_names = tuple(feature_names)
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        # Probe the store with a synthetic single-key request so misconfigured
        # providers fail loudly at run time. The probe payload uses the
        # configured entity keys with empty values; concrete subclasses
        # supply actual keys from the materialised dataset.
        probe_keys = [{key: "" for key in self._entity_keys}]
        await self._feature_store.get_features(
            probe_keys, self._feature_names
        )
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._extend(split.train, now),
            test=self._extend(split.test, now),
            validation=(
                self._extend(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _extend(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        existing = list(dataset.feature_names)
        for name in self._feature_names:
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
