"""``ImageEmbeddingExtractor`` — append an image-encoder-derived feature
to every :class:`DatasetManifest` in a :class:`SplitManifest`.

The actual image bytes are not embedded here. The knot calls the
configured :class:`ImageEncoderProvider` once with the column name as a
single byte probe (so provider configuration can fail loudly at run
time) and emits a split whose feature lists carry an extra entry named
``<column>_embedding``.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``image_column`` (str), and
       ``image_encoder`` (ImageEncoderProvider) via process().
    2. Validate image_column is non-empty and image_encoder has the right type.
    3. Probe the encoder with the column name as bytes to catch misconfiguration early.
    4. Append ``<image_column>_embedding`` to the feature list of each partition.
    5. Return the updated SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class ImageEmbeddingExtractor(Knot):
    """Append a ``<image_column>_embedding`` feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        image_column: Knot | str,
        image_encoder: Knot | ImageEncoderProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            image_column=image_column,
            image_encoder=image_encoder,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        image_column: str,
        image_encoder: ImageEncoderProvider,
        **_: Any,
    ) -> SplitManifest:
        """Probe the image encoder, append the image-column embedding feature to each split partition, and return the updated SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the new image embedding feature.
            image_column: Non-empty name of the image column to embed.
            image_encoder: ImageEncoderProvider used to probe and encode the column.

        Returns:
            SplitManifest with ``<image_column>_embedding`` appended to every partition's feature list.

        Raises:
            ValueError: If image_column is empty.
            TypeError: If image_encoder is not an ImageEncoderProvider.
        """
        if not isinstance(image_column, str) or not image_column:
            raise ValueError("ImageEmbeddingExtractor: image_column must be a non-empty string")
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "ImageEmbeddingExtractor: image_encoder must be an ImageEncoderProvider"
            )
        # Touch the encoder so misconfigured providers fail loudly at
        # planning time. We feed the column name encoded as bytes as a
        # single probe rather than the full image column.
        await image_encoder.encode([image_column.encode("utf-8")])
        feature = f"{image_column}_embedding"
        now = datetime.now(UTC)
        return SplitManifest(
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
        dataset: DatasetManifest,
        feature: str,
        fetched_at: datetime,
    ) -> DatasetManifest:
        if feature in dataset.feature_names:
            features = dataset.feature_names
        else:
            features = (*dataset.feature_names, feature)
        return DatasetManifest(
            name=f"{dataset.name}:image-embedded",
            feature_names=features,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
