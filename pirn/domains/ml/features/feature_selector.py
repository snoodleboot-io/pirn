"""``FeatureSelector`` — keep the top-K features in a :class:`DataSplit`.

The actual scoring is deferred to a later runtime phase. At this layer
the knot reduces the logical feature list and emits a renamed split so
downstream knots see a smaller feature schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class FeatureSelector(Knot):
    """Truncate feature list to ``k`` entries via a stable scoring method."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"mutual_information", "variance", "rfe"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        k: int,
        method: str = "mutual_information",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(k, int):
            raise TypeError("FeatureSelector: k must be an int")
        if k < 1:
            raise ValueError("FeatureSelector: k must be >= 1")
        if method not in self.valid_methods:
            raise ValueError(
                f"FeatureSelector: method must be one of "
                f"{sorted(self.valid_methods)}"
            )
        self._k = k
        self._method = method
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    @property
    def k(self) -> int:
        return self._k

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Truncate the feature list to the top k entries using the configured method and return the reduced DataSplit.

        Args:
            split: DataSplit whose feature lists are truncated to k entries.

        Returns:
            DataSplit with each partition's feature list capped at k features.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._reduce(split.train, now),
            test=self._reduce(split.test, now),
            validation=(
                self._reduce(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _reduce(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        kept = dataset.feature_names[: self._k]
        return MLDataset(
            name=f"{dataset.name}:selected_{self._method}",
            feature_names=kept,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
