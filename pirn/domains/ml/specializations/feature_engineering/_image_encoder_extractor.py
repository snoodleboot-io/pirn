"""``_ImageEncoderExtractor`` — append a ``<image_column>_embedding``
feature to every partition of a :class:`DataSplit` via an
:class:`ImageEncoderProvider`.

Mirrors :class:`EmbeddingExtractor` but operates over image bytes
through :class:`ImageEncoderProvider`. Single-underscore name marks
this knot as a private composition detail used by
:class:`ImageEmbeddingExtractor`.

Algorithm:
    1. Receive ``split``, ``image_column``, and ``image_encoder`` via process().
    2. Validate inputs.
    3. Probe the encoder with column-name bytes.
    4. Append ``<image_column>_embedding`` to every partition and return the extended DataSplit.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class _ImageEncoderExtractor(Knot):
    """Append a ``<image_column>_embedding`` feature to every partition."""

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
        split: DataSplit,
        image_column: str = "",
        image_encoder: ImageEncoderProvider | None = None,
        **_: Any,
    ) -> DataSplit:
        """Probe the image encoder, append the image-column embedding feature to each partition, and return the updated DataSplit.

        Args:
            split: DataSplit whose partitions receive the new image embedding feature.
            image_column: Non-empty name of the image column.
            image_encoder: ImageEncoderProvider to probe.

        Returns:
            DataSplit with ``<image_column>_embedding`` appended to every partition's feature list.

        Raises:
            ValueError: If image_column is not a non-empty string.
            TypeError: If image_encoder is not an ImageEncoderProvider.
        """
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "_ImageEncoderExtractor: image_column must be a non-empty string"
            )
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "_ImageEncoderExtractor: image_encoder must be an ImageEncoderProvider"
            )
        # Touch the provider with a single probe so misconfigured providers
        # fail loudly at run time. The probe uses the column-name bytes as
        # a placeholder image; the orchestration layer doesn't have rows.
        await image_encoder.encode([image_column.encode("utf-8")])
        feature = f"{image_column}_embedding"
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
            name=f"{dataset.name}:image_embedded",
            feature_names=features,
            target_name=dataset.target_name,
            row_count=dataset.row_count,
            source_uri=dataset.source_uri,
            fetched_at=fetched_at,
        )
