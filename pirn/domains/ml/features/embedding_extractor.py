"""``EmbeddingExtractor`` — append an embedding-derived feature to every
:class:`MLDataset` in a :class:`DataSplit`.

The actual texts are not embedded here. The knot calls the configured
:class:`EmbeddingProvider` once with the column name as a probe (so
provider configuration can fail loudly at run time) and emits a split
whose feature lists carry an extra entry named ``<column>_embedding``.

Algorithm:
    1. Receive ``split`` (DataSplit), ``text_column`` (str), and
       ``embedding_provider`` (EmbeddingProvider) via process().
    2. Validate text_column is non-empty and embedding_provider is the right type.
    3. Probe the provider with the column name to catch misconfiguration early.
    4. Append ``<text_column>_embedding`` to the feature list of each partition.
    5. Return the updated DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class EmbeddingExtractor(Knot):
    """Append a ``<text_column>_embedding`` feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        text_column: Knot | str,
        embedding_provider: Knot | EmbeddingProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            text_column=text_column,
            embedding_provider=embedding_provider,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        text_column: str,
        embedding_provider: EmbeddingProvider,
        **_: Any,
    ) -> DataSplit:
        """Probe the embedding provider, append the text-column embedding feature to each split partition, and return the updated DataSplit.

        Args:
            split: DataSplit whose partitions receive the new embedding feature.
            text_column: Non-empty name of the text column to embed.
            embedding_provider: EmbeddingProvider used to probe and embed the column.

        Returns:
            DataSplit with ``<text_column>_embedding`` appended to every partition's feature list.

        Raises:
            ValueError: If text_column is empty.
            TypeError: If embedding_provider is not an EmbeddingProvider.
        """
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "EmbeddingExtractor: text_column must be a non-empty string"
            )
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError(
                "EmbeddingExtractor: embedding_provider must be an "
                "EmbeddingProvider"
            )
        # Touch the provider so misconfigured providers fail loudly at
        # planning time. We embed the column name as a single probe text
        # rather than the full column (we don't have rows here).
        await embedding_provider.embed([text_column])
        feature = f"{text_column}_embedding"
        now = datetime.now(UTC)
        return DataSplit(
            train=self._add_feature(split.train, feature, now),
            test=self._add_feature(split.test, feature, now),
            validation=(
                self._add_feature(split.validation, feature, now)
                if split.validation is not None
                else None
            ),
        )

    def _add_feature(
        self,
        dataset: MLDataset,
        feature: str,
        fetched_at: datetime,
    ) -> MLDataset:
        if feature in dataset.feature_names:
            features = dataset.feature_names
        else:
            features = (*dataset.feature_names, feature)
        return MLDataset(
            name=f"{dataset.name}:embedded",
            feature_names=features,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
