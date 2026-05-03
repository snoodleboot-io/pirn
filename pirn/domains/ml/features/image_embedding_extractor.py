"""``ImageEmbeddingExtractor`` — append an image-encoder-derived feature
to every :class:`MLDataset` in a :class:`DataSplit`.

The actual image bytes are not embedded here. The knot calls the
configured :class:`ImageEncoderProvider` once with the column name as a
single byte probe (so provider configuration can fail loudly at run
time) and emits a split whose feature lists carry an extra entry named
``<column>_embedding``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class ImageEmbeddingExtractor(Knot):
    """Append a ``<image_column>_embedding`` feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        image_column: str,
        image_encoder: ImageEncoderProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "ImageEmbeddingExtractor: image_column must be a non-empty string"
            )
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "ImageEmbeddingExtractor: image_encoder must be an "
                "ImageEncoderProvider"
            )
        self._image_column = image_column
        self._image_encoder = image_encoder
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Probe the image encoder, append the image-column embedding feature to each split partition, and return the updated DataSplit.

        Args:
            split: DataSplit whose partitions receive the new image embedding feature.

        Returns:
            DataSplit with ``<image_column>_embedding`` appended to every partition's feature list.
        """
        # Touch the encoder so misconfigured providers fail loudly at
        # planning time. We feed the column name encoded as bytes as a
        # single probe rather than the full image column.
        await self._image_encoder.encode([self._image_column.encode("utf-8")])
        feature = f"{self._image_column}_embedding"
        now = datetime.now(timezone.utc)
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
            features = dataset.feature_names + (feature,)
        return MLDataset(
            name=f"{dataset.name}:image-embedded",
            feature_names=features,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
