"""``InteractionFeatureGenerator`` — create pairwise interaction (product)
features for specified column pairs.

Appends ``<col_a>_x_<col_b>`` feature names for every pair in
``column_pairs``.

Algorithm:
    1. Receive ``split`` (SplitManifest) and ``column_pairs`` (Sequence[tuple[str,str]]) via process().
    2. Validate column_pairs is non-empty with valid two-element string tuples.
    3. Append interaction feature names to each partition.
    4. Return updated SplitManifest.

Math:
    Pairwise product interaction:
        x_{a_x_b} = x_a * x_b

    For M pairs this adds M features to the feature set.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class InteractionFeatureGenerator(Knot):
    """Append pairwise product feature names to a SplitManifest."""

    def __init__(
        self,
        *,
        split: Knot,
        column_pairs: Knot | Sequence[tuple[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            column_pairs=column_pairs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        column_pairs: Sequence[tuple[str, str]] = (),
        **_: Any,
    ) -> SplitManifest:
        """Append interaction feature names for each column pair to every partition.

        Args:
            split: SplitManifest whose partitions receive the interaction feature names.
            column_pairs: Non-empty sequence of (col_a, col_b) string pairs.

        Returns:
            SplitManifest with ``<col_a>_x_<col_b>`` feature names appended to every
            partition.

        Raises:
            ValueError: If column_pairs is empty or contains invalid entries.
        """
        pairs_tuple = tuple(column_pairs)
        if not pairs_tuple:
            raise ValueError("InteractionFeatureGenerator: column_pairs must be non-empty")
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
        cleaned_pairs = tuple((str(a), str(b)) for a, b in pairs_tuple)
        now = datetime.now(UTC)
        return SplitManifest(
            train=self._add_interaction_features(split.train, cleaned_pairs, now),
            test=self._add_interaction_features(split.test, cleaned_pairs, now),
            validation=(
                self._add_interaction_features(split.validation, cleaned_pairs, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_interaction_features(
        self,
        dataset: DatasetManifest,
        column_pairs: tuple[tuple[str, str], ...],
        fetched_at: datetime,
    ) -> DatasetManifest:
        features = list(dataset.feature_names)
        for col_a, col_b in column_pairs:
            name = f"{col_a}_x_{col_b}"
            if name not in features:
                features.append(name)
        return DatasetManifest(
            name=f"{dataset.name}:interactions",
            feature_names=tuple(features),
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
