"""``InteractionFeatureGenerator`` — create pairwise interaction (product)
features for specified column pairs.

Appends ``<col_a>_x_<col_b>`` feature names for every pair in
``column_pairs``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class InteractionFeatureGenerator(Knot):
    """Append pairwise product feature names to a DataSplit."""

    def __init__(
        self,
        *,
        split: Knot,
        column_pairs: Sequence[tuple[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError(
                "InteractionFeatureGenerator: split must be a Knot"
            )
        pairs_tuple = tuple(column_pairs)
        if not pairs_tuple:
            raise ValueError(
                "InteractionFeatureGenerator: column_pairs must be non-empty"
            )
        for pair in pairs_tuple:
            if (
                not isinstance(pair, (tuple, list))
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not pair[0]
                or not isinstance(pair[1], str)
                or not pair[1]
            ):
                raise ValueError(
                    "InteractionFeatureGenerator: each column pair must be a "
                    "tuple of two non-empty strings"
                )
        self._column_pairs = tuple(
            (str(a), str(b)) for a, b in pairs_tuple
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Append interaction feature names for each column pair to every partition.

        Args:
            split: DataSplit whose partitions receive the interaction feature names.

        Returns:
            DataSplit with ``<col_a>_x_<col_b>`` feature names appended to every
            partition.
        """
        now = datetime.now(timezone.utc)
        return DataSplit(
            train=self._add_interaction_features(split.train, now),
            test=self._add_interaction_features(split.test, now),
            validation=(
                self._add_interaction_features(split.validation, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_interaction_features(
        self, dataset: MLDataset, fetched_at: datetime
    ) -> MLDataset:
        features = list(dataset.feature_names)
        for col_a, col_b in self._column_pairs:
            name = f"{col_a}_x_{col_b}"
            if name not in features:
                features.append(name)
        return MLDataset(
            name=f"{dataset.name}:interactions",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
